import unittest
from datetime import date, datetime, timedelta, timezone

from scripts.trend_birth_radar import evaluate_trend_birth


def business_days(count, start=date(2025, 1, 2)):
    days = []
    current = start
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def rows_from_closes(closes):
    days = business_days(len(closes))
    return [
        {
            "time": day.isoformat(),
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000_000,
        }
        for day, close in zip(days, closes)
    ]


def staged_closes(end_slope):
    first = [50.0 + index * 0.15 for index in range(180)]
    peak = first[-1]
    pullback = [peak - (index + 1) * 0.10 for index in range(8)]
    start = pullback[-1]
    ending = [start + (index + 1) * end_slope for index in range(15)]
    return first + pullback + ending


class TrendBirthRadarTests(unittest.TestCase):
    def test_insufficient_history_is_unavailable(self):
        result = evaluate_trend_birth(rows_from_closes([50 + i * 0.1 for i in range(80)]))
        self.assertEqual(result["stage"], 0)
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "insufficient_daily_history")

    def test_watch_closely_stage_two(self):
        result = evaluate_trend_birth(rows_from_closes(staged_closes(-0.05)))
        self.assertEqual(result["stage"], 2)
        self.assertTrue(result["checks"]["sma50Rising"])
        self.assertTrue(result["checks"]["sma30wRising"])
        self.assertTrue(result["checks"]["priceNearSma50"])
        self.assertTrue(result["checks"]["emaCompressed"])
        self.assertFalse(result["checks"]["ema10Rising"])

    def test_ready_stage_three(self):
        result = evaluate_trend_birth(rows_from_closes(staged_closes(0.0)))
        self.assertEqual(result["stage"], 3)
        self.assertTrue(result["checks"]["ema10FlatteningOrRising"])
        self.assertTrue(result["checks"]["ema20FlatteningOrRising"])
        self.assertTrue(result["checks"]["oneShortEmaRising"])
        self.assertFalse(result["checks"]["bullishReexpansion"])

    def test_trigger_stage_four(self):
        result = evaluate_trend_birth(rows_from_closes(staged_closes(0.04)))
        self.assertEqual(result["stage"], 4)
        self.assertEqual(result["stageLabel"], "TRIGGER")
        self.assertTrue(result["checks"]["recentPullbackCompression"])
        self.assertTrue(result["checks"]["ema10Rising"])
        self.assertTrue(result["checks"]["ema20NonFalling"])
        self.assertTrue(result["checks"]["ema10AboveEma20"])
        self.assertTrue(result["checks"]["closeAboveShortEmas"])
        self.assertTrue(result["checks"]["bullishReexpansion"])
        self.assertEqual(result["missingFor4"], [])


    def test_epoch_second_timestamps_keep_weekly_history_available(self):
        rows = rows_from_closes(staged_closes(0.0))
        for row in rows:
            day = datetime.strptime(row["time"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            row["time"] = int(day.timestamp())
        result = evaluate_trend_birth(rows)
        self.assertTrue(result["available"])
        self.assertNotEqual(result.get("reason"), "insufficient_weekly_history")

    def test_downtrend_is_invalidated(self):
        closes = [120.0 - index * 0.20 for index in range(210)]
        result = evaluate_trend_birth(rows_from_closes(closes))
        self.assertEqual(result["stage"], 0)
        self.assertTrue(result["available"])
        self.assertFalse(result["checks"]["sma50Rising"])
        self.assertFalse(result["checks"]["sma30wRising"])


if __name__ == "__main__":
    unittest.main()
