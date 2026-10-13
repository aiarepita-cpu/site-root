import datetime as dt
import unittest

from strategies import relative_strength_rotation_v1 as s

N = s.PARAMS["lookback_days"]


def path(ret):
    """127 closes whose 126-day trailing return is exactly `ret`."""
    return [100.0] * N + [100.0 * (1 + ret)]


def universe(spy, qqq, iwm):
    return {"SPY": path(spy), "QQQ": path(qqq), "IWM": path(iwm)}


class Metadata(unittest.TestCase):
    def test_version_and_hypothesis(self):
        self.assertEqual(s.VERSION, 1)
        self.assertTrue(s.__doc__.startswith("Hypothesis:"))


class RebalanceDay(unittest.TestCase):
    def test_last_trading_day_of_month(self):
        self.assertTrue(s.is_rebalance_day(dt.date(2026, 10, 30), dt.date(2026, 11, 2)))

    def test_year_end(self):
        self.assertTrue(s.is_rebalance_day(dt.date(2026, 12, 31), dt.date(2027, 1, 4)))

    def test_mid_month(self):
        self.assertFalse(s.is_rebalance_day(dt.date(2026, 10, 15), dt.date(2026, 10, 16)))


class Selection(unittest.TestCase):
    def test_picks_highest_positive(self):
        self.assertEqual(s.select_target(universe(0.05, 0.10, 0.02)), "QQQ")

    def test_cash_when_all_negative(self):
        self.assertIsNone(s.select_target(universe(-0.01, -0.02, -0.03)))

    def test_cash_when_best_is_exactly_zero(self):
        self.assertIsNone(s.select_target(universe(0.0, -0.02, -0.03)))

    def test_tie_broken_by_universe_order(self):
        self.assertEqual(s.select_target(universe(0.05, 0.05, 0.05)), "SPY")

    def test_none_with_insufficient_history(self):
        u = universe(0.05, 0.10, 0.02)
        u["IWM"] = u["IWM"][1:]  # 126 closes, one short
        self.assertIsNone(s.select_target(u))

    def test_lookback_uses_close_126_days_ago(self):
        # Reference close is exactly 126 bars back (100). Neighbours differ so an off-by-one
        # (1.0 one bar earlier, 200.0 one bar later) gives a different answer.
        closes = [1.0, 100.0] + [200.0] * (N - 1) + [110.0]
        self.assertAlmostEqual(s.trailing_return(closes), 0.10)


class Entry(unittest.TestCase):
    def test_enters_target_on_rebalance_day(self):
        self.assertEqual(s.entry_signal(universe(0.05, 0.10, 0.02), None, True), "QQQ")

    def test_switches_into_new_leader(self):
        self.assertEqual(s.entry_signal(universe(0.05, 0.10, 0.02), "SPY", True), "QQQ")

    def test_no_entry_off_rebalance_day(self):
        self.assertIsNone(s.entry_signal(universe(0.05, 0.10, 0.02), None, False))

    def test_no_entry_when_already_holding_target(self):
        self.assertIsNone(s.entry_signal(universe(0.05, 0.10, 0.02), "QQQ", True))

    def test_no_entry_when_target_is_cash(self):
        self.assertIsNone(s.entry_signal(universe(-0.05, -0.10, -0.02), None, True))


class Exit(unittest.TestCase):
    def test_exits_when_leader_changes(self):
        self.assertTrue(s.exit_signal(universe(0.05, 0.10, 0.02), "SPY", True))

    def test_exits_to_cash_when_all_negative(self):
        self.assertTrue(s.exit_signal(universe(-0.05, -0.10, -0.02), "SPY", True))

    def test_holds_when_still_leader(self):
        self.assertFalse(s.exit_signal(universe(0.05, 0.10, 0.02), "QQQ", True))

    def test_no_exit_off_rebalance_day(self):
        self.assertFalse(s.exit_signal(universe(-0.05, -0.10, -0.02), "SPY", False))

    def test_no_exit_when_flat(self):
        self.assertFalse(s.exit_signal(universe(0.05, 0.10, 0.02), None, True))


class Sizing(unittest.TestCase):
    def test_capped_by_global_limit(self):
        self.assertEqual(s.position_size(100_000, 100, max_position_pct=0.05), 50)

    def test_full_allocation_when_uncapped(self):
        self.assertEqual(s.position_size(100_000, 100, max_position_pct=1.0), 1000)


if __name__ == "__main__":
    unittest.main()
