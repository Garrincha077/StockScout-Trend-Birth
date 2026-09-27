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
                {"ticker": "BBB", "weeklyBirth": {"eligible": False, "rejectReasons": ["clearRunway"]}},
            ],
        }
        previous = {"sessionDate": "2026-09-24", "selected": [{"ticker": "CCC"}]}
        report = build_report(snapshot, previous)
        self.assertEqual(1, report["eligibleCount"])
        self.assertEqual({"clearRunway": 1}, report["rejectionReasonCounts"])
        self.assertEqual(["AAA"], report["added"])
        self.assertEqual(["CCC"], report["removed"])
        self.assertFalse(report["manualChartReviewComplete"])

    def test_old_snapshot_cannot_claim_v2_shadow_session(self):
        with self.assertRaisesRegex(ValueError, "unavailable"):
            build_report({"source": {"sessionDate": "2026-09-25"}})


if __name__ == "__main__":
    unittest.main()
