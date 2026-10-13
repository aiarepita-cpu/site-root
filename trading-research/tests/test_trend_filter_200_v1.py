import unittest

from strategies import trend_filter_200_v1 as s


def series(last, base=100.0, n=200):
    return [base] * (n - 1) + [last]


class Metadata(unittest.TestCase):
    def test_version_and_hypothesis(self):
        self.assertEqual(s.VERSION, 1)
        self.assertTrue(s.__doc__.startswith("Hypothesis:"))


class Entry(unittest.TestCase):
    def test_enters_when_close_above_sma(self):
        self.assertTrue(s.entry_signal(series(101), in_position=False))

    def test_no_entry_when_close_equals_sma(self):
        self.assertFalse(s.entry_signal(series(100), in_position=False))

    def test_no_entry_when_close_below_sma(self):
        self.assertFalse(s.entry_signal(series(99), in_position=False))

    def test_no_entry_with_199_bars(self):
        self.assertFalse(s.entry_signal(series(150, n=199), in_position=False))

    def test_no_entry_when_already_long(self):
        self.assertFalse(s.entry_signal(series(101), in_position=True))

    def test_only_last_200_bars_count(self):
        # A huge old value outside the window must not raise the SMA.
        closes = [10_000.0] + series(101)
        self.assertTrue(s.entry_signal(closes, in_position=False))


class Exit(unittest.TestCase):
    def test_exits_when_close_below_sma(self):
        self.assertTrue(s.exit_signal(series(99), in_position=True))

    def test_holds_when_close_equals_sma(self):
        self.assertFalse(s.exit_signal(series(100), in_position=True))

    def test_holds_when_close_above_sma(self):
        self.assertFalse(s.exit_signal(series(101), in_position=True))

    def test_no_exit_when_flat(self):
        self.assertFalse(s.exit_signal(series(99), in_position=False))

    def test_no_exit_with_199_bars(self):
        self.assertFalse(s.exit_signal(series(50, n=199), in_position=True))


class Sizing(unittest.TestCase):
    def test_capped_by_global_limit(self):
        self.assertEqual(s.position_size(100_000, 100, max_position_pct=0.05), 50)

    def test_uses_target_weight_when_below_cap(self):
        self.assertEqual(s.position_size(100_000, 100, max_position_pct=1.0), 333)

    def test_zero_on_bad_inputs(self):
        self.assertEqual(s.position_size(100_000, 0, 0.05), 0)
        self.assertEqual(s.position_size(0, 100, 0.05), 0)


if __name__ == "__main__":
    unittest.main()
