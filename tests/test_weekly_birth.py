import unittest
from datetime import date, timedelta

from scripts.weekly_birth import completed_weekly_bars, evaluate_weekly_birth, weekly_shortlist


def base_rows(count=180, *, breakout=False, older_resistance=None):
    first_friday = date(2023, 1, 6)
    rows = []
    for index in range(count):
        close = 103 if breakout and index == count - 1 else 100
        high = 102
        if older_resistance and index == 35:
            high = older_resistance
        rows.append({
            "time": (first_friday + timedelta(weeks=index)).isoformat(),
            "open": 100, "high": max(close, high), "low": 98,
            "close": close, "volume": 1_000_000,
        })
    return rows


class WeeklyBirthTests(unittest.TestCase):
    def test_long_base_is_ready_before_breakout(self):
        result = evaluate_weekly_birth(base_rows())
        self.assertEqual(3, result["stage"])
        self.assertTrue(result["eligible"])
        self.assertGreaterEqual(result["metrics"]["baseWeeks"], 52)
        self.assertLessEqual(result["metrics"]["weeklyMaClusterPct"], 6)

    def test_first_breakout_is_trigger(self):
        result = evaluate_weekly_birth(base_rows(breakout=True))
        self.assertEqual(4, result["stage"])
        self.assertEqual(0, result["metrics"]["weeksSinceBreakout"])

    def test_dense_long_base_can_be_watched_before_sma30_turn(self):
        rows = base_rows()
        for row in rows[-6:]:
            row["close"] = 99
        result = evaluate_weekly_birth(rows)
        self.assertEqual("Long Base", result["stageLabel"])
        self.assertTrue(result["checks"]["stage1Watch"])
        self.assertTrue(result["eligible"])

    def test_nearby_prior_resistance_excludes_shortlist(self):
        result = evaluate_weekly_birth(base_rows(older_resistance=108))
        self.assertFalse(result["checks"]["clearRunway"])
        self.assertFalse(result["eligible"])
        self.assertIn("clearRunway", result["rejectReasons"])

    def test_unfinished_week_does_not_create_trigger(self):
        rows = base_rows()
        monday = date.fromisoformat(rows[-1]["time"]) + timedelta(days=3)
        rows.append({**rows[-1], "time": monday.isoformat(), "close": 110, "high": 110})
        self.assertEqual(180, len(completed_weekly_bars(rows)))
        self.assertEqual(3, evaluate_weekly_birth(rows)["stage"])

    def test_history_and_shortlist_limit(self):
        self.assertEqual(0, evaluate_weekly_birth(base_rows(80))["stage"])
        items = [{"ticker": f"T{index:02d}", "weeklyBirth": {"eligible": True, "stage": 2, "score": 90 - index}} for index in range(20)]
        self.assertEqual(15, len(weekly_shortlist(items)))
        self.assertEqual("T00", weekly_shortlist(items)[0]["ticker"])

    def test_steady_mature_uptrend_is_not_a_long_base(self):
        rows = base_rows()
        for index, row in enumerate(rows):
            close = 75 + index * 0.15
            row.update(open=close - 0.5, high=close + 1, low=close - 1, close=close)
        result = evaluate_weekly_birth(rows)
        self.assertFalse(result["eligible"])
        self.assertIn("no_recent_52_to_104_week_base", result["rejectReasons"])


if __name__ == "__main__":
    unittest.main()
