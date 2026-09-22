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
            })
        with tempfile.TemporaryDirectory() as tmp:
            meta = compact.write_chart_shards(
                candidates,
                pathlib.Path(tmp),
                {"runId": "r1", "sessionDate": "2026-09-21"},
                2,
            )
            self.assertEqual(meta["shardCount"], 3)
            self.assertEqual(meta["chartCandidateCount"], 5)
            files = sorted(pathlib.Path(tmp).glob("shard-*.json"))
            self.assertEqual(len(files), 3)
            tickers = set()
            for path in files:
                payload = json.loads(path.read_text())
                tickers.update(payload["charts"])
            self.assertEqual(tickers, {"T0", "T1", "T2", "T3", "T4"})
            item = compact.compact_candidate(candidates[0], chart_shard=0)
            self.assertNotIn("chartBars", item)
            self.assertEqual(item["chartBarsCount"], 2)
            self.assertEqual(item["chartShard"], 0)


if __name__ == "__main__":
    unittest.main()
