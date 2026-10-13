import unittest

from strategies import volume_breakout_v1 as s


def closes_with_prior_high(today, prior_high=105.0):
    # 20 prior closes, max = prior_high, then today
    return [100.0] * 19 + [prior_high] + [today]


def volumes(today, avg=1000.0):
    return [avg] * 20 + [today]


class Metadata(unittest.TestCase):
    def test_version_and_hypothesis(self):
        self.assertEqual(s.VERSION, 1)
        self.assertTrue(s.__doc__.startswith("Hypothesis:"))


class Breakout(unittest.TestCase):
    def test_above_prior_high(self):
        self.assertTrue(s.is_breakout(closes_with_prior_high(105.01)))

    def test_equal_to_prior_high_is_not_breakout(self):
        self.assertFalse(s.is_breakout(closes_with_prior_high(105.0)))

    def test_high_21_days_ago_is_outside_window(self):
        self.assertTrue(s.is_breakout([110.0] + [100.0] * 20 + [101.0]))

    def test_insufficient_history(self):
        self.assertFalse(s.is_breakout([100.0] * 19 + [200.0]))


class Volume(unittest.TestCase):
    def test_exactly_1_5x_counts(self):
        self.assertTrue(s.is_high_volume(volumes(1500)))

    def test_just_below_1_5x(self):
        self.assertFalse(s.is_high_volume(volumes(1499)))

    def test_todays_volume_excluded_from_average(self):
        # If today were included the average would rise above 1000 and 1500 would fail.
        self.assertTrue(s.is_high_volume(volumes(1500)))

    def test_old_spike_outside_window_ignored(self):
        self.assertTrue(s.is_high_volume([1_000_000.0] + volumes(1500)))

    def test_insufficient_history(self):
        self.assertFalse(s.is_high_volume([1000.0] * 19 + [5000.0]))


class Entry(unittest.TestCase):
    def test_enters_on_breakout_with_volume(self):
        self.assertTrue(s.entry_signal(closes_with_prior_high(106), volumes(1500), in_position=False))

    def test_no_entry_breakout_without_volume(self):
        self.assertFalse(s.entry_signal(closes_with_prior_high(106), volumes(1499), in_position=False))

    def test_no_entry_volume_without_breakout(self):
        self.assertFalse(s.entry_signal(closes_with_prior_high(104), volumes(5000), in_position=False))

    def test_no_entry_when_already_long(self):
        self.assertFalse(s.entry_signal(closes_with_prior_high(106), volumes(1500), in_position=True))


def closes_with_prior_low(today, prior_low=95.0):
    # 10 prior closes, min = prior_low, then today
    return [100.0] * 9 + [prior_low] + [today]


class Exit(unittest.TestCase):
    def test_exits_below_prior_10_day_low(self):
        self.assertTrue(s.exit_signal(closes_with_prior_low(94.99), in_position=True))

    def test_holds_at_prior_low(self):
        self.assertFalse(s.exit_signal(closes_with_prior_low(95.0), in_position=True))

    def test_low_11_days_ago_is_outside_window(self):
        self.assertTrue(s.exit_signal([90.0] + [100.0] * 10 + [99.0], in_position=True))

    def test_no_exit_when_flat(self):
        self.assertFalse(s.exit_signal(closes_with_prior_low(90.0), in_position=False))

    def test_insufficient_history(self):
        self.assertFalse(s.exit_signal([100.0] * 9 + [50.0], in_position=True))


class Sizing(unittest.TestCase):
    def test_capped_by_global_limit(self):
        self.assertEqual(s.position_size(100_000, 100, max_position_pct=0.05), 50)

    def test_uses_target_weight_when_below_cap(self):
        self.assertEqual(s.position_size(100_000, 100, max_position_pct=1.0), 333)


if __name__ == "__main__":
    unittest.main()
