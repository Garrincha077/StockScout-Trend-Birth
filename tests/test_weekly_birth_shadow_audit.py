import unittest

from scripts.weekly_birth_shadow_audit import build_report


class WeeklyBirthShadowAuditTests(unittest.TestCase):
    def test_report_counts_reasons_and_membership_change_without_certifying_review(self):
        snapshot = {
            "source": {"sessionDate": "2026-09-25", "runId": "run-1", "unifiedManifestSha256": "abc"},
            "shortlists": {"schemaVersion": "stockscout-shortlists-v2", "weeklyTrendBirth": [
                {"ticker": "AAA", "weeklyBirth": {"stageLabel": "Ready", "score": 88, "metrics": {"baseWeeks": 70}}},
            ]},
            "trendBirthCandidateIndex": [
                {"ticker": "AAA", "weeklyBirth": {"eligible": True, "rejectReasons": []}},
                {"ticker": "BBB", "weeklyBirth": {"eligible": False, "stage": 1, "stageLabel": "Long Base", "score": 72, "rejectReasons": ["clearRunway"], "metrics": {"mansfieldRsPct": 1.2}}},
            ],
        }
        previous = {"sessionDate": "2026-09-24", "selected": [{"ticker": "CCC"}]}
        report = build_report(snapshot, previous)
        self.assertEqual(1, report["eligibleCount"])
        self.assertEqual({"clearRunway": 1}, report["rejectionReasonCounts"])
        self.assertEqual(["AAA"], report["added"])
        self.assertEqual(["CCC"], report["removed"])
        self.assertFalse(report["manualChartReviewComplete"])
        self.assertEqual("BBB", report["nearMissReviewQueue"][0]["ticker"])
        self.assertEqual(["clearRunway"], report["nearMissReviewQueue"][0]["rejectReasons"])
        self.assertEqual({"unavailable": 2}, report["chartSourceCounts"])

    def test_old_snapshot_cannot_claim_v2_shadow_session(self):
        with self.assertRaisesRegex(ValueError, "unavailable"):
            build_report({"source": {"sessionDate": "2026-09-25"}})

    def test_chart_review_queue_prefers_inspectable_near_miss(self):
        snapshot = {
            "source": {"sessionDate": "2026-09-25"},
            "shortlists": {"schemaVersion": "stockscout-shortlists-v2", "weeklyTrendBirth": []},
            "trendBirthCandidateIndex": [
                {"ticker": "NOCHART", "weeklyBirth": {"stage": 1, "score": 90, "rejectReasons": ["mansfieldRsImproving"]}},
                {"ticker": "CHART", "weeklyBirth": {"stage": 1, "score": 70, "rejectReasons": ["mansfieldRsImproving", "maSlopeTurn"]}},
            ],
            "kellCandidates": [{"ticker": "CHART", "weeklyChartBars": [["2026-09-25", 1, 1, 1, 1, 1]]}],
        }
        queue = build_report(snapshot)["nearMissReviewQueue"]
        self.assertEqual(["CHART", "NOCHART"], [item["ticker"] for item in queue])
        self.assertTrue(queue[0]["chartAvailable"])

    def test_bottom_crash_evidence_is_counted_without_promoting_a_reject(self):
        snapshot = {
            "source": {"sessionDate": "2026-09-25"},
            "shortlists": {"schemaVersion": "stockscout-shortlists-v2", "weeklyTrendBirth": []},
            "trendBirthCandidateIndex": [{
                "ticker": "CRASH", "metrics": {"crashBaseTriggered": True},
                "weeklyBirth": {"eligible": False, "chartSource": "bottom-fishing",
                                "rejectReasons": ["clearRunway"], "metrics": {}},
            }],
        }
        report = build_report(snapshot)
        self.assertEqual(1, report["bottomCrashTriggeredCount"])
        self.assertEqual(0, report["bottomCrashEligibleCount"])
        self.assertEqual({"bottom-fishing": 1}, report["chartSourceCounts"])
        self.assertEqual("CRASH", report["bottomCrashReviewQueue"][0]["ticker"])
        self.assertEqual(["clearRunway"], report["bottomCrashReviewQueue"][0]["rejectReasons"])

    def test_research_watch_is_reported_but_cannot_be_a_selection(self):
        item = {"ticker": "BASE", "weeklyBirth": {"eligible": False,
                "stageLabel": "Long Base", "rejectReasons": ["mansfieldRsImproving"],
                "metrics": {"baseWeeks": 89, "weeklyMaClusterPct": 3}}}
        snapshot = {"source": {"sessionDate": "2026-09-25"},
                    "shortlists": {"schemaVersion": "stockscout-shortlists-v2",
                                   "weeklyTrendBirth": [], "weeklyResearchWatch": [item]},
                    "trendBirthCandidateIndex": [item]}
        report = build_report(snapshot)
        self.assertEqual(0, report["selectedCount"])
        self.assertEqual(1, report["researchWatchCount"])
        self.assertEqual("BASE", report["researchWatch"][0]["ticker"])
        item["weeklyBirth"]["eligible"] = True
        with self.assertRaisesRegex(ValueError, "cannot contain"):
            build_report(snapshot)


if __name__ == "__main__":
    unittest.main()
