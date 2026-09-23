import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).parents[1] / "scripts" / "validate_unified_review_bundle.py"
spec = importlib.util.spec_from_file_location("bundle_validator", MODULE)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")


class UnifiedBundleValidatorTests(unittest.TestCase):
    def fixture(self, root: Path):
        source = {
            "repo": "Garrincha077/StockScout-Unified",
            "runId": "2026-09-22-eod-1-1",
            "sessionDate": "2026-09-22",
            "unifiedManifestSha256": "d" * 64,
            "readOnly": True,
        }
        review = {
            "source": source,
            "candidateCount": 1,
            "chartCount": 1,
            "candidates": [{"ticker": "AAA", "chartBars": [["2026-09-22", 1, 2, 1, 2, 100]]}],
            "kellScoring": {
                "scope": "all-unified-candidates",
                "candidateGenerationChanged": False,
                "unifiedCandidateCount": 2,
            },
            "kellCandidateCount": 1,
        }
        review_path = root / "latest.json"
        write_json(review_path, review)
        digest = __import__("hashlib").sha256(review_path.read_bytes()).hexdigest()
        publication = {
            "runId": source["runId"],
            "sessionDate": source["sessionDate"],
            "unifiedManifestSha256": source["unifiedManifestSha256"],
            "sha256": digest,
        }
        kell = {
            "source": {
                "runId": source["runId"],
                "sessionDate": source["sessionDate"],
                "unifiedManifestSha256": source["unifiedManifestSha256"],
                "readOnly": True,
            },
            "kellScoring": {"unifiedCandidateCount": 2},
            "kellCandidateCount": 1,
            "kellCandidates": [{"ticker": "AAA"}],
            "kellChartData": {"shardCount": 1},
        }
        publication_path = root / "publication.json"
        kell_path = root / "kell-latest.json"
        charts_dir = root / "kell-charts"
        write_json(publication_path, publication)
        write_json(kell_path, kell)
        write_json(charts_dir / "shard-000.json", {
            "source": {
                "runId": source["runId"],
                "sessionDate": source["sessionDate"],
                "unifiedManifestSha256": source["unifiedManifestSha256"],
            },
            "charts": {"AAA": {"daily": [["2026-09-22", 1, 2, 1, 2, 100]]}},
        })
        return review_path, publication_path, kell_path, charts_dir

    def test_accepts_one_exact_unified_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = validator.validate(*self.fixture(Path(tmp)))
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["unifiedCandidateCount"], 2)
            self.assertEqual(result["chartTickerCount"], 1)

    def test_rejects_same_date_different_unified_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_path, publication_path, kell_path, charts_dir = self.fixture(root)
            kell = json.loads(kell_path.read_text())
            kell["source"]["unifiedManifestSha256"] = "e" * 64
            write_json(kell_path, kell)
            with self.assertRaisesRegex(ValueError, "source identities differ"):
                validator.validate(review_path, publication_path, kell_path, charts_dir)

    def test_rejects_candidate_generation_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_path, publication_path, kell_path, charts_dir = self.fixture(root)
            review = json.loads(review_path.read_text())
            review["kellScoring"]["candidateGenerationChanged"] = True
            write_json(review_path, review)
            publication = json.loads(publication_path.read_text())
            publication["sha256"] = __import__("hashlib").sha256(review_path.read_bytes()).hexdigest()
            write_json(publication_path, publication)
            with self.assertRaisesRegex(ValueError, "must not change"):
                validator.validate(review_path, publication_path, kell_path, charts_dir)


if __name__ == "__main__":
    unittest.main()
