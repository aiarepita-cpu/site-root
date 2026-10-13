"""Runner tests with fake Alpaca clients. No network, no orders."""
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS

from alpaca.common.enums import BaseURL

from src import runner
from src.broker import LiveTradingRefused

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "memory"))
import ledger  # noqa: E402

LIMITS = {"max_daily_loss_pct": 2.0, "max_drawdown_pct": 8.0,
          "max_position_pct": 10.0, "max_open_positions": 5}
NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
UNIVERSE = ("SPY", "QQQ", "IWM")


class FakeTrading:
    def __init__(self, equity=100_000, last_equity=100_000, positions=None, open_orders=(),
                 base_url=BaseURL.TRADING_PAPER, calendar_next=date(2026, 10, 12)):
        self._base_url = base_url
        self._acct = NS(equity=str(equity), last_equity=str(last_equity),
                        trading_blocked=False, account_blocked=False)
        self._positions = [NS(symbol=s, qty=str(q), market_value=str(q * 100))
                           for s, q in (positions or {}).items()]
        self._open = [NS(symbol=s) for s in open_orders]
        self._next = calendar_next
        self.submitted = []

    def get_account(self): return self._acct
    def get_all_positions(self): return self._positions
    def get_orders(self, req): return self._open
    def get_calendar(self, req): return [NS(date=self._next)]
    def get_clock(self): return NS(is_open=self.is_open, timestamp=NOW)
    is_open = False

    def submit_order(self, order_data):
        self.submitted.append(order_data)
        return NS(id=f"paper-{len(self.submitted)}")


class FakeData:
    def __init__(self, closes_by_symbol, last_date=date(2026, 10, 9)):
        self.c, self.last = closes_by_symbol, last_date

    def get_stock_bars(self, req):
        out = {}
        for s, closes in self.c.items():
            n = len(closes)
            out[s] = [NS(timestamp=datetime.combine(self.last - timedelta(days=n - 1 - i), datetime.min.time()),
                         close=c, volume=1000.0) for i, c in enumerate(closes)]
        return NS(data=out)


def flat_then(last, n=200):
    return [100.0] * (n - 1) + [last]


class RunnerTest(unittest.TestCase):
    def test_partial_bar_ignored_while_market_open(self):
        self.clear("trend_filter_200")
        t = FakeTrading()
        t.is_open = True
        # Completed bars end flat at 100 (no entry); today's partial bar (101) would trigger one.
        self.run_(t, FakeData({s: flat_then(100, 200) + [101.0] for s in UNIVERSE}, last_date=NOW.date()))
        self.assertEqual(t.submitted, [])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.conn = ledger.connect(":memory:")
        self.ids = {}
        for name in ("trend_filter_200", "relative_strength_rotation", "volume_breakout"):
            self.ids[name] = ledger.add(self.conn, name, "momentum analyst", "SPY,QQQ,IWM",
                                        strategy_file=f"strategies/{name}_v1.py", strategy_version=1)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def clear(self, name):
        ledger.update(self.conn, self.ids[name], status="passed backtest only", sealed_test_result="passed")

    def run_(self, trading, data):
        runner.run_once(trading, data, self.conn, now=NOW, limits=LIMITS,
                        journal_dir=self.dir, state_path=self.dir / "peak.json")
        return [json.loads(l) for l in (self.dir / "decisions.jsonl").read_text().splitlines()]

    def test_nothing_cleared_means_no_orders(self):
        t = FakeTrading()
        entries = self.run_(t, FakeData({s: flat_then(101) for s in UNIVERSE}))
        self.assertEqual(t.submitted, [])
        self.assertEqual([e["decision"] for e in entries], ["SKIPPED"] * 3)
        self.assertIn("untested", entries[0]["reasoning"])

    def test_two_cleared_strategies_refused(self):
        self.clear("trend_filter_200")
        self.clear("volume_breakout")
        t = FakeTrading()
        entries = self.run_(t, FakeData({s: flat_then(101) for s in UNIVERSE}))
        self.assertEqual(t.submitted, [])
        self.assertEqual(entries[-1]["decision"], "ERROR")

    def test_entries_pass_risk_and_are_submitted_and_journaled(self):
        self.clear("trend_filter_200")
        t = FakeTrading()
        entries = self.run_(t, FakeData({s: flat_then(101) for s in UNIVERSE}))
        self.assertEqual([o.symbol for o in t.submitted], list(UNIVERSE))
        self.assertEqual({o.qty for o in t.submitted}, {99})  # floor(100k * 10% / 101)
        buys = [e for e in entries if e["decision"] == "BUY"]
        self.assertEqual(len(buys), 3)
        e = buys[0]
        self.assertEqual((e["strategy"], e["version"], e["order_id"]), ("trend_filter_200", 1, "paper-1"))
        self.assertEqual(e["timestamp"], NOW.isoformat(timespec="seconds"))
        self.assertIn("vs_sma200_pct", e["market_conditions"])
        self.assertTrue(e["reasoning"])
        md = (self.dir / f"{NOW.date()}.md").read_text()
        self.assertIn("trend_filter_200 v1 | BUY", md)

    def test_kill_switch_blocks_and_logs_reason(self):
        self.clear("trend_filter_200")
        t = FakeTrading(equity=97_000, last_equity=100_000)  # -3% today
        entries = self.run_(t, FakeData({s: flat_then(101) for s in UNIVERSE}))
        self.assertEqual(t.submitted, [])
        blocked = [e for e in entries if e["decision"] == "BLOCKED"]
        self.assertEqual(len(blocked), 3)
        self.assertEqual(blocked[0]["risk_check"], "Daily loss limit hit. Trading stopped.")

    def test_exit_sells_full_position(self):
        self.clear("trend_filter_200")
        t = FakeTrading(positions={"SPY": 40})
        closes = {"SPY": flat_then(99), "QQQ": flat_then(100), "IWM": flat_then(100)}
        entries = self.run_(t, FakeData(closes))
        self.assertEqual([(o.symbol, o.side.value, o.qty) for o in t.submitted], [("SPY", "sell", 40)])
        self.assertEqual([e["decision"] for e in entries if e["strategy"] == "trend_filter_200"],
                         ["SELL", "HOLD", "HOLD"])

    def test_open_order_prevents_duplicate(self):
        self.clear("trend_filter_200")
        t = FakeTrading(open_orders=["SPY"])
        self.run_(t, FakeData({s: flat_then(101) for s in UNIVERSE}))
        self.assertEqual([o.symbol for o in t.submitted], ["QQQ", "IWM"])

    def test_non_paper_client_refused(self):
        self.clear("trend_filter_200")
        t = FakeTrading(base_url=BaseURL.TRADING_LIVE)
        with self.assertRaises(LiveTradingRefused):
            self.run_(t, FakeData({s: flat_then(101) for s in UNIVERSE}))
        self.assertEqual(t.submitted, [])

    def test_rotation_buys_leader_on_month_end(self):
        self.clear("relative_strength_rotation")
        # last bar Oct 30 (month-end), next trading day Nov 2
        t = FakeTrading(calendar_next=date(2026, 11, 2))
        closes = {"SPY": flat_then(105, 127), "QQQ": flat_then(110, 127), "IWM": flat_then(102, 127)}
        self.run_(t, FakeData(closes, last_date=date(2026, 10, 30)))
        self.assertEqual([(o.symbol, o.side.value) for o in t.submitted], [("QQQ", "buy")])

    def test_rotation_holds_mid_month(self):
        self.clear("relative_strength_rotation")
        t = FakeTrading(calendar_next=date(2026, 10, 12))
        closes = {"SPY": flat_then(105, 127), "QQQ": flat_then(110, 127), "IWM": flat_then(102, 127)}
        entries = self.run_(t, FakeData(closes))
        self.assertEqual(t.submitted, [])
        self.assertEqual(entries[-1]["decision"], "HOLD")


if __name__ == "__main__":
    unittest.main()
