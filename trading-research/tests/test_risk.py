import json
import tempfile
import unittest
from pathlib import Path

import risk

LIMITS = {"max_daily_loss_pct": 2.0, "max_drawdown_pct": 8.0,
          "max_position_pct": 10.0, "max_open_positions": 2}


def acct(**kw):
    a = {"equity": 100_000, "daily_loss_pct": 0.0, "drawdown_pct": 0.0, "positions": {}}
    a.update(kw)
    return a


def buy(symbol="SPY", qty=10, price=100):
    return {"symbol": symbol, "side": "buy", "qty": qty, "price": price}


class Limits(unittest.TestCase):
    def test_daily_loss_at_limit_blocks(self):
        self.assertEqual(risk.check_order(buy(), acct(daily_loss_pct=2.0), LIMITS),
                         (False, "Daily loss limit hit. Trading stopped."))

    def test_daily_loss_just_below_limit_passes(self):
        self.assertTrue(risk.check_order(buy(), acct(daily_loss_pct=1.99), LIMITS)[0])

    def test_drawdown_at_limit_blocks(self):
        self.assertEqual(risk.check_order(buy(), acct(drawdown_pct=8.0), LIMITS),
                         (False, "Max drawdown hit. Trading stopped."))

    def test_position_exactly_at_limit_passes(self):
        self.assertTrue(risk.check_order(buy(qty=100, price=100), acct(), LIMITS)[0])  # 10%

    def test_position_over_limit_blocks(self):
        ok, why = risk.check_order(buy(qty=101, price=100), acct(), LIMITS)
        self.assertFalse(ok)
        self.assertIn("above the 10.0% limit", why)

    def test_existing_position_counts_toward_limit(self):
        a = acct(positions={"SPY": {"qty": 50, "market_value": 5_000}})
        self.assertFalse(risk.check_order(buy(qty=51, price=100), a, LIMITS)[0])

    def test_too_many_open_positions_blocks_new_symbol(self):
        a = acct(positions={"SPY": {"qty": 1, "market_value": 100}, "QQQ": {"qty": 1, "market_value": 100}})
        self.assertEqual(risk.check_order(buy("IWM"), a, LIMITS), (False, "Too many open positions."))

    def test_adding_to_existing_symbol_not_counted_as_new_position(self):
        a = acct(positions={"SPY": {"qty": 1, "market_value": 100}, "QQQ": {"qty": 1, "market_value": 100}})
        self.assertTrue(risk.check_order(buy("SPY"), a, LIMITS)[0])


class Sells(unittest.TestCase):
    def test_closing_sell_allowed_even_after_loss_limit(self):
        a = acct(daily_loss_pct=5, drawdown_pct=20, positions={"SPY": {"qty": 10, "market_value": 1000}})
        order = {"symbol": "SPY", "side": "sell", "qty": 10, "price": 100}
        self.assertTrue(risk.check_order(order, a, LIMITS)[0])

    def test_short_sell_blocked(self):
        order = {"symbol": "SPY", "side": "sell", "qty": 1, "price": 100}
        self.assertFalse(risk.check_order(order, acct(), LIMITS)[0])


class FailsClosed(unittest.TestCase):
    def test_missing_limit_blocks(self):
        limits = dict(LIMITS)
        del limits["max_drawdown_pct"]
        self.assertFalse(risk.check_order(buy(), acct(), limits)[0])

    def test_missing_account_field_blocks(self):
        a = acct()
        del a["drawdown_pct"]
        self.assertFalse(risk.check_order(buy(), a, LIMITS)[0])

    def test_zero_or_fractional_qty_blocks(self):
        self.assertFalse(risk.check_order(buy(qty=0), acct(), LIMITS)[0])
        self.assertFalse(risk.check_order(buy(qty=1.5), acct(), LIMITS)[0])

    def test_unknown_side_blocks(self):
        self.assertFalse(risk.check_order({**buy(), "side": "short"}, acct(), LIMITS)[0])

    def test_missing_limits_file_blocks(self):
        orig = risk.LIMITS_PATH
        risk.LIMITS_PATH = Path("/nonexistent/risk.json")
        try:
            ok, why = risk.check_order(buy(), acct())  # no explicit limits: reads the file
            self.assertFalse(ok)
            self.assertIn("Order blocked", why)
        finally:
            risk.LIMITS_PATH = orig

    def test_example_config_is_valid(self):
        # config/risk.json is gitignored; the tracked example must always load.
        risk.load_limits(risk.LIMITS_PATH.with_name("risk.example.json"))

    def test_load_limits_rejects_bad_values(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "risk.json"
            for bad in ({**LIMITS, "max_position_pct": -1}, {**LIMITS, "max_open_positions": "5"}):
                p.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    risk.load_limits(p)


if __name__ == "__main__":
    unittest.main()
