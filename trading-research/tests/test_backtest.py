"""Backtester tests on synthetic data. No market data, no network."""
import csv
import random
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

from src import backtest as bt
from src import data as dm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "memory"))
import ledger  # noqa: E402


def write_csvs(d, n=1500, seed=1, sealed_override=None):
    rng = random.Random(seed)
    start = date(2010, 1, 4)
    for s, drift in (("SPY", 0.0004), ("QQQ", 0.0006), ("IWM", 0.0002)):
        px, rows = 100.0, []
        for i in range(n):
            o = px * (1 + rng.gauss(0, 0.003))
            px = o * (1 + drift + rng.gauss(0, 0.01))
            if sealed_override is not None and i >= dm.split_index(n):
                o, px = sealed_override, sealed_override
            rows.append({"date": (start + timedelta(days=i)).isoformat(), "open": o, "close": px,
                         "volume": 1e6 * (1 + rng.random())})
        with open(Path(d) / f"{s}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["date", "open", "close", "volume"])
            w.writeheader()
            w.writerows(rows)


def bars_from(closes, opens=None):
    n = len(closes)
    return {"SPY": {"dates": [date(2020, 1, 1) + timedelta(days=i) for i in range(n)],
                    "open": opens or list(closes), "close": list(closes), "volume": [1.0] * n}}


class Split(unittest.TestCase):
    def test_sealed_fraction_is_30_percent(self):
        self.assertEqual(dm.CONFIG["sealed_fraction"], 0.30)
        self.assertEqual(dm.split_index(1000), 700)

    def test_dev_data_excludes_sealed(self):
        b = bars_from([float(i) for i in range(1000)])
        dev = dm.dev_data(b)
        self.assertEqual(len(dev["SPY"]["close"]), 700)
        self.assertEqual(dev["SPY"]["close"][-1], 699.0)

    def test_sealed_data_usable_once(self):
        conn = ledger.connect(":memory:")
        hid = ledger.add(conn, "x", "a", "SPY")
        b = bars_from([1.0] * 10)
        _, start = dm.sealed_data(b, conn, hid)
        self.assertEqual(start, 7)
        with self.assertRaises(dm.SealedPeriodError):
            dm.sealed_data(b, conn, hid)
        conn.close()


class Metrics(unittest.TestCase):
    def test_max_drawdown(self):
        self.assertAlmostEqual(bt.max_drawdown([100, 120, 60, 130]), 0.5)

    def test_dsr_single_trial_zero_sharpe_is_half(self):
        self.assertAlmostEqual(bt.deflated_sharpe(0.0, 1000, 0.0, 3.0, 1), 0.5)

    def test_dsr_falls_as_trials_rise(self):
        vals = [bt.deflated_sharpe(0.05, 2000, 0.0, 3.0, n) for n in (1, 2, 5, 20, 100)]
        self.assertEqual(vals, sorted(vals, reverse=True))
        self.assertLess(vals[-1], vals[0])

    def test_worst_periods(self):
        closes = [100, 90, 100, 50, 100, 80, 110]
        self.assertEqual([(p, t) for p, t, _ in bt.worst_periods(closes, 2)], [(2, 3), (4, 5)])

    def test_worst_period_starting_in_warmup_is_clipped_not_dropped(self):
        closes = [100, 120, 90, 60, 70, 130]
        self.assertEqual([(p, t) for p, t, _ in bt.worst_periods(closes, 1, min_start=2)], [(2, 3)])
        self.assertEqual(bt.worst_periods(closes, 1, min_start=4), [])  # trough before tradable bars


class Simulation(unittest.TestCase):
    def strat(self, entry_at, exit_at=None):
        return NS(STRATEGY_NAME="fake", UNIVERSE=("SPY",),
                  entry_signal=lambda c, held: not held and len(c) - 1 == entry_at,
                  exit_signal=lambda c, held: held and exit_at is not None and len(c) - 1 == exit_at,
                  position_size=lambda e, p, f: 10)

    def test_fills_at_next_open_with_costs_no_lookahead(self):
        closes = [100.0] * 6
        opens = [100.0, 100.0, 100.0, 200.0, 100.0, 100.0]  # signal at t=2, fill at open of t=3
        sim = bt.simulate(self.strat(2, exit_at=4), bars_from(closes, opens), 0, 6)
        cost = (bt.CONFIG["cost_bps_per_side"] + bt.CONFIG["slippage_bps_per_side"]) / 1e4
        trade = sim["trades"][0]
        self.assertEqual(trade["entry"], "2020-01-04")
        self.assertAlmostEqual(trade["pnl"], 10 * 100 * (1 - cost) - 10 * 200 * (1 + cost))

    def test_delay_shifts_fill_one_day(self):
        sim = bt.simulate(self.strat(2), bars_from([100.0] * 6), 0, 6, delay=1)
        self.assertEqual(sim["open_trades"], 1)
        self.assertEqual(sim["equity"][3], 100_000)  # not filled yet on day 3

    def test_double_costs_lower_return(self):
        b = bars_from([100.0] * 8)
        one = bt.simulate(self.strat(1, exit_at=4), b, 0, 8)["equity"][-1]
        two = bt.simulate(self.strat(1, exit_at=4), b, 0, 8, cost_mult=2)["equity"][-1]
        self.assertLess(two, one)


class FullRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        (self.d / "data").mkdir()
        (self.d / "bt").mkdir()
        self.conn = ledger.connect(":memory:")
        self.hid = ledger.add(self.conn, "trend", "momentum analyst", "SPY,QQQ,IWM",
                              strategy_file="strategies/trend_filter_200_v1.py", strategy_version=1)
        (self.d / "bt" / "trend_filter_200_v1-prediction.md").write_text("I expect Sharpe > 0.5.\n")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def go(self):
        return bt.run("trend_filter_200_v1", self.hid, self.conn, data_dir=self.d / "data",
                      bt_dir=self.d / "bt", max_pos_frac=1 / 3)

    def test_refuses_without_prediction(self):
        write_csvs(self.d / "data")
        (self.d / "bt" / "trend_filter_200_v1-prediction.md").unlink()
        with self.assertRaises(SystemExit):
            self.go()

    def test_refuses_if_prediction_edited_after_lock(self):
        write_csvs(self.d / "data")
        self.go()
        (self.d / "bt" / "trend_filter_200_v1-prediction.md").write_text("I expect Sharpe > 0.1.\n")
        with self.assertRaises(SystemExit):
            self.go()

    def test_sealed_data_does_not_affect_results(self):
        write_csvs(self.d / "data", seed=7)
        r1, _ = self.go()
        write_csvs(self.d / "data", seed=7, sealed_override=1e6)  # garbage in the sealed 30%
        r2, _ = self.go()
        for k in ("total_return_pct", "sharpe", "trades", "max_drawdown_pct"):
            self.assertEqual(r1["development"][k], r2["development"][k])
        self.assertEqual(r1["walk_forward"], r2["walk_forward"])

    def test_each_run_counts_a_variation_and_writes_report(self):
        write_csvs(self.d / "data")
        r1, stem1 = self.go()
        r2, stem2 = self.go()
        self.assertEqual((r1["variation_number"], r2["variation_number"]), (1, 2))
        self.assertLess(r2["development"]["deflated_sharpe"], r1["development"]["deflated_sharpe"])
        md = (self.d / "bt" / f"{stem2}.md").read_text()
        for s in ("Deflated Sharpe", "Walk-forward", "Worst periods", "costs 2x", "I expect Sharpe > 0.5."):
            self.assertIn(s, md)
        self.assertEqual(len(r1["walk_forward"]), 5)
        self.assertGreaterEqual(len(r1["stress"]["worst_periods"]), 1)


if __name__ == "__main__":
    unittest.main()


class SealedRun(FullRun):
    def sealed(self):
        return bt.run_sealed("trend_filter_200_v1", self.hid, self.conn, data_dir=self.d / "data",
                             bt_dir=self.d / "bt")

    def test_requires_dev_backtest_first(self):
        write_csvs(self.d / "data")
        with self.assertRaises(SystemExit):
            self.sealed()
        self.assertIsNone(ledger.search(self.conn)[0]["sealed_test_result"])  # not burned

    def test_runs_once_only_and_does_not_count_a_variation(self):
        write_csvs(self.d / "data")
        self.go()
        r, stem = self.sealed()
        row = ledger.search(self.conn)[0]
        self.assertEqual(row["variations_tried"], 1)
        self.assertTrue(row["sealed_test_result"].startswith("Sharpe"))
        self.assertTrue((self.d / "bt" / f"{stem}.md").exists())
        with self.assertRaises(dm.SealedPeriodError):
            self.sealed()

    def test_covers_exactly_the_sealed_dates(self):
        write_csvs(self.d / "data", n=1500)
        self.go()
        r, _ = self.sealed()
        full = dm.align({s: dm.load_csv(s, self.d / "data") for s in ("SPY", "QQQ", "IWM")})
        dates = full["SPY"]["dates"]
        self.assertEqual(r["period"]["start"], dates[dm.split_index(len(dates))].isoformat())
        self.assertEqual(r["period"]["end"], dates[-1].isoformat())

    def test_refuses_if_prediction_changed(self):
        write_csvs(self.d / "data")
        self.go()
        (self.d / "bt" / "trend_filter_200_v1-prediction.md").write_text("changed")
        with self.assertRaises(SystemExit):
            self.sealed()
        self.assertIsNone(ledger.search(self.conn)[0]["sealed_test_result"])
