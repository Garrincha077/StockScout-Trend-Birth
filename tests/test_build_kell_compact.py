import importlib.util
import json
import pathlib
import tempfile
import unittest

MODULE = pathlib.Path(__file__).parents[1] / "scripts" / "build_kell_compact.py"
spec = importlib.util.spec_from_file_location("build_kell_compact", MODULE)
compact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compact)


class KellCompactTests(unittest.TestCase):
    def test_compact_source_preserves_universe_counts(self):
        source = {
            "source": {
                "runId": "r1",
                "sessionDate": "2026-09-21",
                "unifiedManifestSha256": "b" * 64,
                "modeUniverseCounts": {
                    "bottom-fishing": 2045,
                    "next": 1989,
                    "ryan-original": 1989,
                },
            },
            "kellScoring": {},
            "unifiedCandidateIndexCount": 2,
            "unifiedCandidateIndex": [
                {"ticker": "AAA", "sources": ["next"], "unifiedSources": ["next"], "metrics": {"price": 12}},
                {"ticker": "BBB", "sources": ["bottom-fishing"], "unifiedSources": ["bottom-fishing"], "metrics": {"price": 8}},
            ],
            "kellCandidateCount": 0,
            "kellCandidates": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            source_path = pathlib.Path(tmp) / "source.json"
            output_path = pathlib.Path(tmp) / "out.json"
            source_path.write_text(json.dumps(source))
            old_argv = __import__("sys").argv
            try:
                __import__("sys").argv = [
                    "build_kell_compact.py",
                    "--input", str(source_path),
                    "--output", str(output_path),
                ]
                self.assertEqual(compact.main(), 0)
            finally:
                __import__("sys").argv = old_argv
            out = json.loads(output_path.read_text())
            self.assertEqual(out["schemaVersion"], "kell-compact-v5")
            self.assertEqual(out["source"]["modeUniverseCounts"]["bottom-fishing"], 2045)
            self.assertEqual(out["source"]["unifiedManifestSha256"], "b" * 64)
            self.assertEqual(out["unifiedCandidateIndexCount"], 2)
            self.assertEqual([item["ticker"] for item in out["unifiedCandidateIndex"]], ["AAA", "BBB"])
            self.assertEqual(out["unifiedCandidateIndex"][0]["unifiedSources"], ["next"])

    def test_compact_bar_handles_array_and_object_rows(self):
        self.assertEqual(
            compact.compact_bar(["2026-09-21", 10, 11, 9, 10.5, 1234, 99]),
            ["2026-09-21", 10.0, 11.0, 9.0, 10.5, 1234.0],
        )
        self.assertEqual(
            compact.compact_bar({
                "time": "2026-09-22", "open": 10, "high": 12,
                "low": 9.5, "close": 11, "volume": 1500,
            }),
            ["2026-09-22", 10.0, 12.0, 9.5, 11.0, 1500.0],
        )

    def test_compact_candidate_preserves_crash_base_filter_evidence(self):
        item = {
            "ticker": "AAA",
            "metrics": {
                "price": 12.5,
                "crashBaseTriggered": True,
                "crashBaseScore": 74.0,
                "crashBasePhase": "forming",
                "crashBaseAlertLevel": "watch",
                "crashBaseDrawdown5yPct": 81.0,
                "crashBaseAgeWeeks": 126,
            },
        }
        compact = builder.compact_candidate(item)
        self.assertTrue(compact["metrics"]["crashBaseTriggered"])
        self.assertEqual(compact["metrics"]["crashBaseScore"], 74.0)
        self.assertEqual(compact["metrics"]["crashBasePhase"], "forming")
        self.assertEqual(compact["metrics"]["crashBaseAlertLevel"], "watch")
        self.assertEqual(compact["metrics"]["crashBaseDrawdown5yPct"], 81.0)
        self.assertEqual(compact["metrics"]["crashBaseAgeWeeks"], 126)

    def test_compact_candidate_preserves_v5_score_dimensions(self):
        item = {
            "ticker": "AAA",
            "sources": ["next"],
            "metrics": {"price": 50},
            "kell_score": 82.5,
            "kell_quality_score": 91.0,
            "kell_readiness_score": 84.0,
            "kell_actionability_score": 84.0,
            "kell_context_score": 63.0,
            "kell_evidence_coverage": 90.0,
            "kell_structural_risk_score": 78.0,
            "kell_stage_cap": 100.0,
            "score_breakdown": {
                "model_version": "kell-overlay-v5-quality-readiness-context",
                "legacy_v4_score": 76.0,
                "raw_composite": 82.5,
                "stage_cap": 100.0,
                "final_score": 82.5,
                "evidence_coverage": 90.0,
                "components": {"quality": {"score": 91.0}},
                "criteria": {"verbose": {"detail": "do not copy this into compact"}},
            },
            "kell_stage": {"primary": "ema_crossback", "confidence": 0.95, "basis": []},
        }
        out = compact.compact_candidate(item)
        self.assertEqual(out["kell_quality_score"], 91.0)
        self.assertEqual(out["kell_readiness_score"], 84.0)
        self.assertEqual(out["score_breakdown"]["legacy_v4_score"], 76.0)
        self.assertNotIn("criteria", out["score_breakdown"])

    def test_tracked_candidate_can_embed_small_chart_history(self):
        item = {
            "ticker": "CLOV",
            "sources": ["tracked-watchlist"],
            "unifiedSources": [],
            "trackedWatchlist": True,
            "trackedOnly": True,
            "chartBars": [
                ["2026-09-23", 3, 3.2, 2.9, 3.1, 1000],
                ["2026-09-24", 3.1, 3.3, 3.0, 3.2, 1100],
            ],
            "weeklyChartBars": [
                ["2026-09-18", 2.9, 3.2, 2.8, 3.1, 5000],
            ],
        }
        out = compact.compact_candidate(item, include_bars=True)
        self.assertTrue(out["trackedWatchlist"])
        self.assertTrue(out["trackedOnly"])
        self.assertEqual(len(out["chartBars"]), 2)
        self.assertEqual(len(out["weeklyChartBars"]), 1)

    def test_chart_shards_cover_candidates_without_embedding_bars(self):
        candidates = []
        for i in range(5):
            ticker = f"T{i}"
            candidates.append({
                "ticker": ticker,
                "sources": ["next"],
                "metrics": {"price": 10 + i},
                "kell_stage": {"primary": "transition", "confidence": 0.5, "basis": []},
                "chartBars": [
                    ["2026-09-20", 10, 11, 9, 10.5, 1000],
                    ["2026-09-21", 10.5, 12, 10, 11.5, 1200],
                ],
                "weeklyChartBars": [
                    ["2026-09-11", 9.5, 11, 9, 10, 5000],
                    ["2026-09-18", 10, 12, 9.5, 11.5, 6000],
                ],
            })
        with tempfile.TemporaryDirectory() as tmp:
            meta = compact.write_chart_shards(
                candidates,
                pathlib.Path(tmp),
                {"runId": "r1", "sessionDate": "2026-09-21", "unifiedManifestSha256": "c" * 64},
                2,
            )
            self.assertEqual(meta["shardCount"], 3)
            self.assertEqual(meta["chartCandidateCount"], 5)
            self.assertEqual(meta["weeklyChartCandidateCount"], 5)
            self.assertEqual(meta["schemaVersion"], "kell-chart-shard-v2")
            files = sorted(pathlib.Path(tmp).glob("shard-*.json"))
            self.assertEqual(len(files), 3)
            tickers = set()
            for path in files:
                payload = json.loads(path.read_text())
                tickers.update(payload["charts"])
            self.assertEqual(tickers, {"T0", "T1", "T2", "T3", "T4"})
            first_payload = json.loads(files[0].read_text())
            self.assertEqual(first_payload["schemaVersion"], "kell-chart-shard-v2")
            self.assertEqual(first_payload["source"]["unifiedManifestSha256"], "c" * 64)
            self.assertEqual(len(first_payload["charts"]["T0"]["daily"]), 2)
            self.assertEqual(len(first_payload["charts"]["T0"]["weekly"]), 2)
            item = compact.compact_candidate(candidates[0], chart_shard=0)
            self.assertNotIn("chartBars", item)
            self.assertEqual(item["chartBarsCount"], 2)
            self.assertEqual(item["weeklyChartBarsCount"], 2)
            self.assertEqual(item["chartShard"], 0)


if __name__ == "__main__":
    unittest.main()
