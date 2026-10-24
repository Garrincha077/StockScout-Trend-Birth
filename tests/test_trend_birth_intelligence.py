import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "trend_birth_intelligence",
    Path(__file__).parents[1] / "scripts" / "trend_birth_intelligence.py",
)
intel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intel)


def item(ticker, stage, checks=None, available=True, readiness=40):
    return {
        "ticker": ticker,
        "trendBirth": {"available": available, "stage": stage,
                       "checks": checks or {}, "missingFor4": []},
        "weeklyBirth": {"metrics": {"baseWeeks": 25, "runwayPct": 80}},
        "kell_readiness_score": readiness, "kell_score": 55,
    }


def snapshot(day="2026-10-23", rows=None):
    rows = rows if rows is not None else [
        item("AAA", 4, {"sma50Rising": True, "sma30wRising": True}),
        item("BBB", 3, {"sma50Rising": True}),
        item("CCC", 0),
        item("DDD", 0, available=False),
    ]
    counts = {str(i): 0 for i in range(5)}
    unavailable = 0
    for row in rows:
        tb = row["trendBirth"]
        if tb["available"]:
            counts[str(tb["stage"])] += 1
        else:
            unavailable += 1
    return {
        "source": {"sessionDate": day, "runId": day + "-eod-1"},
        "trendBirthRadar": {"schemaVersion": intel.RADAR_SCHEMA, "scope": intel.SCOPE,
                            "stageCounts": counts,
                            "evaluatedCount": sum(counts.values()),
                            "unavailableCount": unavailable},
        "trendBirthCandidateIndex": rows,
    }


class IntelligenceTests(unittest.TestCase):
    def test_full_universe_reconciles_missing_separately(self):
        point = intel.point_from_snapshot(snapshot())
        self.assertEqual(point["counts"], {"0": 1, "1": 0, "2": 0, "3": 1, "4": 1})
        self.assertEqual(point["unavailable"], ["DDD"])
        self.assertEqual(point["stages"]["AAA"][1], 3)
        self.assertNotIn("DDD", point["stages"])

    def test_legacy_radar_is_not_fabricated(self):
        self.assertIsNone(intel.point_from_snapshot({"source": {"sessionDate": "2026-09-17"}}))

    def test_radar_reconciliation_and_duplicate_ticker_fail(self):
        value = snapshot()
        value["trendBirthRadar"]["stageCounts"]["4"] = 7
        with self.assertRaisesRegex(ValueError, "reconcile"):
            intel.point_from_snapshot(value)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            intel.point_from_snapshot(snapshot(rows=[item("AAA", 4), item("AAA", 3)]))

    def test_baseline_does_not_invent_new_triggers(self):
        current = snapshot()
        point = intel.point_from_snapshot(current)
        summary = intel.build_summary(current, [point])
        self.assertTrue(summary["baselineOnly"])
        self.assertEqual((summary["newFour"], summary["toReady"], summary["upgrades"]), (0, 0, 0))
        self.assertIsNone(summary["newCoverage"])

    def test_transitions_use_only_common_valid_tickers(self):
        previous = snapshot("2026-10-22", [
            item("AAA", 3, {"sma50Rising": True}),
            item("BBB", 4, {"sma50Rising": True}),
            item("CCC", 0),
            item("DDD", 0, available=False),
            item("OLD", 1),
        ])
        current = snapshot("2026-10-23", [
            item("AAA", 4, {"sma50Rising": True, "sma30wRising": True}),
            item("BBB", 3, {"sma50Rising": True}),
            item("CCC", 0),
            item("DDD", 4),  # first valid observation: not a transition
            item("NEW", 4),  # newly screened name: not a transition
        ])
        points = [intel.point_from_snapshot(previous), intel.point_from_snapshot(current)]
        summary = intel.build_summary(current, points)
        self.assertEqual(summary["commonEvaluated"], 3)
        self.assertEqual(summary["newFourTickers"], ["AAA"])
        self.assertEqual(summary["readyTickers"], [])
        self.assertEqual(summary["downgradeTickers"], ["BBB"])
        self.assertEqual((summary["upgrades"], summary["downgrades"], summary["netImprovement"]), (1, 1, 0))
        self.assertEqual(summary["newCoverage"], 2)
        row = next(row for row in summary["topOpportunities"] if row["ticker"] == "AAA")
        self.assertEqual(row["newChecks"], ["30W SMA raste"])
        self.assertEqual((row["previousStage"], row["stage"]), (3, 4))

    def test_stability_counts_only_observed_consecutive_eod_and_paired_tickers(self):
        days = [
            snapshot("2026-10-20", [item("AAA", 4), item("BBB", 3),
                                   item("UUU", 0, available=False)]),
            snapshot("2026-10-21", [item("AAA", 4), item("BBB", 3), item("UUU", 4)]),
            snapshot("2026-10-22", [item("AAA", 4), item("BBB", 2), item("UUU", 4)]),
            snapshot("2026-10-23", [item("AAA", 4), item("BBB", 3), item("UUU", 1)]),
        ]
        summary = intel.build_summary(days[-1], [intel.point_from_snapshot(day) for day in days])
        stable = summary["stability"]
        self.assertEqual((stable["observedSessions"], stable["transitionPairs"]), (4, 3))
        self.assertEqual((stable["quality"]["current"], stable["quality"]["atLeast3"],
                          stable["quality"]["oneSession"]), (2, 1, 1))
        self.assertEqual((stable["four"]["current"], stable["four"]["atLeast3"]), (1, 1))
        self.assertEqual((stable["quality"]["latestDropouts"], stable["four"]["latestDropouts"]), (1, 1))
        self.assertEqual(stable["quality"]["retention"],
                         {"kept": 5, "eligible": 7, "percent": 71.4})
        self.assertEqual(stable["four"]["retention"],
                         {"kept": 4, "eligible": 5, "percent": 80.0})
        featured = {row["ticker"]: row for row in summary["topOpportunities"]}
        self.assertEqual((featured["AAA"]["qualityStreak"], featured["AAA"]["fourStreak"]), (4, 4))
        self.assertEqual((featured["BBB"]["qualityStreak"], featured["BBB"]["fourStreak"]), (1, 0))

    def test_stability_new_and_missing_eod_break_streak_without_counting_dropout(self):
        a = intel.point_from_snapshot(snapshot("2026-10-20", [item("AAA", 4)]))
        b = intel.point_from_snapshot(snapshot("2026-10-21", [item("AAA", 0, available=False)]))
        c = intel.point_from_snapshot(snapshot("2026-10-22", [item("AAA", 4)]))
        d = intel.point_from_snapshot(snapshot("2026-10-23", [item("BBB", 4)]))
        stable, ticker_streaks = intel.calculate_stability([a, b, c, d])
        self.assertEqual(ticker_streaks["BBB"], (1, 1))
        self.assertEqual(stable["quality"]["retention"]["eligible"], 0)
        self.assertEqual(stable["quality"]["latestDropouts"], 0)
        self.assertIsNone(stable["four"]["retention"]["percent"])

    def test_merging_is_append_only_and_detects_conflicts(self):
        months = {}
        prev = intel.point_from_snapshot(snapshot("2026-09-30"))
        now = intel.point_from_snapshot(snapshot("2026-10-23"))
        intel.merge_point(months, prev)
        intel.merge_point(months, now)
        intel.merge_point(months, now)
        self.assertEqual(len(months["2026-10"]["sessions"]), 1)
        self.assertEqual([x["sessionDate"] for x in intel.all_points(months)],
                         ["2026-09-30", "2026-10-23"])
        modified = dict(now)
        modified["runId"] = "other-run"
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            intel.merge_point(months, modified)

    def test_stale_or_mismatched_latest_fails_closed(self):
        current = snapshot("2026-10-22")
        points = [intel.point_from_snapshot(current), intel.point_from_snapshot(snapshot("2026-10-23"))]
        with self.assertRaisesRegex(ValueError, "newest"):
            intel.build_summary(current, points)

    def test_incremental_monthly_files_retain_old_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            latest = root / "latest.json"
            history = root / "history"
            months = root / "months"
            summary = root / "summary.json"
            history.mkdir()
            early = snapshot("2026-09-30")
            current = snapshot("2026-10-23")
            (history / "2026-09-30.json").write_text(json.dumps(early))
            (history / "2026-09-17.json").write_text("{}")
            latest.write_text(json.dumps(current))
            result = intel.build(latest, history, months, summary)
            self.assertEqual((result["sessions"], result["months"]), (2, 2))
            previous = json.loads((months / "2026-09.json").read_text())
            self.assertEqual(previous["sessions"][0]["sessionDate"], "2026-09-30")
            (history / "2026-09-30.json").unlink()
            same = intel.build(latest, history, months, summary)
            self.assertEqual(same["sessions"], 2)
            self.assertEqual(previous, json.loads((months / "2026-09.json").read_text()))


if __name__ == "__main__":
    unittest.main()
