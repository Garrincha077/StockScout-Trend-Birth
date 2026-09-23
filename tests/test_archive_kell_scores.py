import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).parents[1] / "scripts" / "archive_kell_scores.py"
spec = importlib.util.spec_from_file_location("archive_kell_scores", MODULE)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


class ArchiveKellScoresTests(unittest.TestCase):
    def test_archive_keeps_point_in_time_score_fields_without_charts(self):
        payload = {
            "source": {"sessionDate": "2026-09-22", "runId": "r1"},
            "kellScoring": {"modelVersion": "kell-overlay-v5-quality-readiness-context"},
            "kellCandidates": [{
                "ticker": "AAA",
                "unifiedSources": ["next"],
                "kell_score": 82.0,
                "kell_quality_score": 90.0,
                "kell_readiness_score": 84.0,
                "kell_context_score": 60.0,
                "kell_evidence_coverage": 95.0,
                "kell_stage_cap": 100.0,
                "kell_stage": {"primary": "ema_crossback"},
                "score_breakdown": {"legacy_v4_score": 55.0},
                "chartBars": [["2026-09-22", 1, 2, 1, 2, 100]],
            }],
        }
        out = archive.build_archive(payload)
        self.assertEqual(out["schemaVersion"], "kell-score-history-v1")
        self.assertEqual(out["candidateCount"], 1)
        item = out["candidates"][0]
        self.assertEqual(item["legacy_v4_score"], 55.0)
        self.assertEqual(item["stage"], "ema_crossback")
        self.assertNotIn("chartBars", item)


if __name__ == "__main__":
    unittest.main()
