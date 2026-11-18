from datetime import date, timedelta
from math import log
import unittest

from scripts.early_trend_birth import HISTORY, MODEL, evaluate, priority
from scripts.early_trend_outcomes import matched_outcomes, pair_signals, report


def days(count):
    return [(date(2025, 1, 2) + timedelta(days=offset)).isoformat() for offset in range(count)]


class EarlyTrendBirthTest(unittest.TestCase):
    def setUp(self):
        self.dates = days(HISTORY + 1)
        self.bars = []
        for index, day in enumerate(self.dates):
            close = max(10.1, 18 - index * 0.12)
            spread = 0.2 if index < 117 else 0.06
            self.bars.append([day, close, close + spread, close - spread, close, 1000])
        self.bars[92][3] = self.bars[103][3] = 9.6
        self.bars[-1][1:5] = [10.4, 10.44, 10.32, 10.4]
        self.spy = dict.fromkeys(self.dates, 100)

    def test_repaired_base_has_levels_and_attributed_evidence(self):
        plan = evaluate(self.bars, self.dates[-1], self.spy, 2, {"stage": 2, "metrics": {"baseWeeks": 35}})
        self.assertEqual(plan["phase"], "reclaim")
        self.assertEqual(plan["baseSupport"], 9.6)
        self.assertLess(plan["invalidation"], plan["baseSupport"])
        self.assertEqual(plan["weeklyBaseWeeks"], 35)
        self.assertGreater(plan["relativeStrength20Pct"], 0)
        self.assertIn("relative_strength_turn", plan["evidence"])
        self.assertIn("range_compression", plan["evidence"])
        confirmed = evaluate(self.bars, self.dates[-1], self.spy, 4)
        self.assertEqual(confirmed["phase"], "confirmed")
        self.assertLess(priority({"ticker": "A", "earlyTrend": confirmed}), priority({"ticker": "A", "earlyTrend": plan}))

    def test_wrong_session_invalidated_support_or_missing_rs(self):
        self.assertIsNone(evaluate(self.bars, self.dates[-2], self.spy))
        self.assertIsNone(evaluate(self.bars[:-1], self.dates[-1], self.spy))
        without_benchmark = evaluate(self.bars, self.dates[-1], {})
        self.assertIsNone(without_benchmark["relativeStrength20Pct"])
        self.assertNotIn("relative_strength_turn", without_benchmark["evidence"])
        self.bars[-1][1:5] = [9.2, 9.4, 9.1, 9.2]
        self.assertIsNone(evaluate(self.bars, self.dates[-1], self.spy))


class EarlyTrendOutcomesTest(unittest.TestCase):
    def test_long_horizons_mature_automatically_and_report_lead_and_coverage(self):
        calendar = days(270)
        names = [f"T{i:02}" for i in range(25)]
        leader = names[-1]
        points = []
        for index, day in enumerate(calendar[:9]):
            points.append({
                "sessionDate": day,
                "stages": {name: [4 if index >= 3 and name == leader else 2] for name in names},
                "earlyTrend": {"model": MODEL, "shortlist": [leader] if index >= 1 else [],
                               "weekly": [leader] if index >= 6 else []},
            })
        prices = {name: {day: 100 + index * (i + 1) / 100 for index, day in enumerate(calendar)}
                  for i, name in enumerate(names)}
        pending = report(points, prices, calendar[:30], [])
        self.assertEqual(pending["lead"]["daily4"], {"matched": 1, "earlier": 1, "same": 0, "later": 0, "medianSessions": 2})
        self.assertEqual(pending["lead"]["weekly"]["medianSessions"], 5)
        self.assertEqual(pending["horizons"]["252"]["early"]["pending"], 1)
        mature = report(points, prices, calendar, [])
        for horizon in ("63", "126", "252"):
            status = mature["horizons"][horizon]["early"]
            self.assertEqual(status["matured"], 1)
            self.assertEqual(status["leadersCaptured"], 1)
            self.assertEqual(status["leadersMissed"], 8)
            self.assertEqual(status["belowUniverseMedian"], 0)
            self.assertGreater(status["excessPct"], 0)
        del prices[leader][calendar[254]]
        incomplete = report(points, prices, calendar, [])
        self.assertEqual(incomplete["horizons"]["252"]["early"]["missingMatured"], 1)

    def test_matches_respect_both_calipers_and_use_each_control_once(self):
        prices = [("A", 100, 0, 2), ("B", 100, 0, 2), ("PEER", 100, 0, 2),
                  ("LOW", 49, 0, 2), ("FAST", 100, 11, 2), ("OTHER_STAGE", 100, 0, 3)]
        features = {ticker: (stage, log(price), momentum) for ticker, price, momentum, stage in prices}
        self.assertEqual(pair_signals({"A", "B"}, set(), features), [("A", "PEER")])

    def test_frozen_control_is_not_replaced_when_its_exit_price_is_missing(self):
        calendar = days(45)
        prior, signal_day, entry, exit_day = calendar[21:24] + [calendar[28]]
        names = {"A": 100, "B": 101, "FAR": 145, "ANOTHER_SIGNAL": 100, "OTHER_STAGE": 100}
        stages = {ticker: [3 if ticker == "OTHER_STAGE" else 2] for ticker in names}
        points = [
            {"sessionDate": prior, "stages": stages, "earlyTrend": {"model": MODEL, "shortlist": [], "weekly": []}},
            {"sessionDate": signal_day, "stages": stages, "earlyTrend": {
                "model": MODEL, "shortlist": ["A"], "weekly": [], "candidates": {"A": 99, "ANOTHER_SIGNAL": 99}}},
        ]
        prices = {ticker: dict.fromkeys(calendar, price) for ticker, price in names.items()}
        # These signal-day values are not available to the matching algorithm.
        prices["B"][signal_day] = 1000
        prices["A"][exit_day] = 110
        prices["B"][entry], prices["B"][exit_day] = 100, 95
        outcome = matched_outcomes(points, prices, calendar, [])["groups"]["early"]
        self.assertEqual((outcome["signals"], outcome["paired"], outcome["unmatched"]), (1, 1, 0))
        self.assertEqual(outcome["outcomes"]["5"]["differencePp"], 15)
        self.assertEqual(outcome["outcomes"]["20"]["pending"], 0)
        self.assertEqual(outcome["outcomes"]["63"]["pending"], 1)
        del prices["B"][exit_day]
        outcome = matched_outcomes(points, prices, calendar, [])["groups"]["early"]["outcomes"]["5"]
        self.assertEqual((outcome["observed"], outcome["missingPairPrices"]), (0, 1))
        self.assertIsNone(outcome["differencePp"])

    def test_daily_reference_uses_archived_stages_and_first_early_day_establishes_baseline(self):
        calendar = days(31)
        points = [
            {"sessionDate": calendar[21], "stages": {"A": [2], "B": [2]}},
            {"sessionDate": calendar[22], "stages": {"A": [4], "B": [2]},
             "earlyTrend": {"model": MODEL, "shortlist": ["A"], "weekly": []}},
        ]
        prices = {"A": dict.fromkeys(calendar, 100), "B": dict.fromkeys(calendar, 100)}
        grouped = matched_outcomes(points, prices, calendar, [])["groups"]
        self.assertEqual(grouped["early"]["signals"], 0)
        self.assertEqual(grouped["daily4"]["outcomes"]["5"]["observed"], 1)
        self.assertEqual(grouped["daily4"]["outcomes"]["5"]["differencePp"], 0)
