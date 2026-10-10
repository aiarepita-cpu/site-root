import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "memory"))
import ledger  # noqa: E402


class Ledger(unittest.TestCase):
    def setUp(self):
        self.c = ledger.connect(":memory:")
        self.h = ledger.add(self.c, "idea", "momentum analyst", "SPY,QQQ,IWM",
                            strategy_file="strategies/x_v1.py", strategy_version=1)

    def tearDown(self):
        self.c.close()

    def test_defaults(self):
        r = ledger.search(self.c)[0]
        self.assertEqual((r["status"], r["variations_tried"]), ("untested", 0))

    def test_every_backtest_counts_a_variation(self):
        ledger.record_backtest(self.c, self.h, "fail 1", "failed")
        ledger.record_backtest(self.c, self.h, "fail 2", "failed", regime="choppy")
        r = ledger.search(self.c)[0]
        self.assertEqual((r["variations_tried"], r["backtest_result"], r["market_regime"]), (2, "fail 2", "choppy"))

    def test_search_filters(self):
        ledger.add(self.c, "other", "macro", "TLT")
        self.assertEqual(len(ledger.search(self.c, market="QQQ")), 1)
        self.assertEqual(len(ledger.search(self.c, status="untested")), 2)
        self.assertEqual(len(ledger.search(self.c, status="failed")), 0)

    def test_invalid_status_and_regime_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            ledger.update(self.c, self.h, status="great")
        with self.assertRaises(sqlite3.IntegrityError):
            ledger.update(self.c, self.h, market_regime="sideways")

    def test_variations_cannot_be_overwritten(self):
        with self.assertRaises(ValueError):
            ledger.update(self.c, self.h, variations_tried=0)

    def test_lessons_append(self):
        ledger.add_lesson(self.c, self.h, "a")
        ledger.add_lesson(self.c, self.h, "b")
        lessons = ledger.search(self.c)[0]["lessons_learned"].splitlines()
        self.assertEqual([l.split("] ")[1] for l in lessons], ["a", "b"])

    def test_paper_eligibility_requires_sealed_result(self):
        ledger.update(self.c, self.h, status="passed backtest only")
        self.assertEqual(ledger.eligible_for_paper(self.c), [])
        ledger.update(self.c, self.h, sealed_test_result="passed")
        self.assertEqual(len(ledger.eligible_for_paper(self.c)), 1)
        ledger.update(self.c, self.h, status="paused")
        self.assertEqual(ledger.eligible_for_paper(self.c), [])


if __name__ == "__main__":
    unittest.main()
