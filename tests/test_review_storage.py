"""Regression for the GitHub 100 MiB limit and exact Review archive identity."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pack_review_storage as packer  # noqa: E402
import review_archive_io as archive_io  # noqa: E402

spec = importlib.util.spec_from_file_location("publish_review_snapshot_storage", ROOT / "scripts/publish_review_snapshot.py")
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)

def snapshot(day, run):
    return {"source": {"sessionDate": day, "runId": run, "unifiedManifestSha256": "a" * 64},
            "candidateCount": 1, "chartCount": 1,
            "candidates": [{"ticker": "AAA", "chartBars": [[1, 2, 3, 4, 5, 6]] * 100}]}

class StorageTests(unittest.TestCase):
    def test_lossless_snapshot_and_immutable_daily_link(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            value = snapshot("2026-11-04", "run-1")
            manifest = publisher.publish(value, base)
            raw = (base / "latest.json").read_bytes()
            original_sha = hashlib.sha256(raw).hexdigest()
            result = packer.package(base, max_raw_bytes=256)
            self.assertEqual(result["sha256"], original_sha)
            for path in ("latest.json.gz", "history/2026-11-04.json.gz",
                         "snapshots/" + manifest["snapshotId"] + ".json.gz"):
                self.assertEqual(gzip.decompress((base / path).read_bytes()), raw)
            self.assertFalse((base / "latest.json").exists())
            self.assertEqual(archive_io.read_archive(archive_io.archive_for_day(base / "history", "2026-11-04")), value)
            self.assertEqual(archive_io.archive_paths(base / "history")[0].name, "2026-11-04.json.gz")
            self.assertEqual(json.loads((base / "publication.json").read_text())["snapshotPath"], result["snapshotPath"])
            self.assertEqual(packer.materialize_latest(base)["runId"], "run-1")
            self.assertEqual((base / "latest.json").read_bytes(), raw)

    def test_new_session_preserves_prior_gzip_archive(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            publisher.publish(snapshot("2026-11-04", "run-1"), base)
            packer.package(base, max_raw_bytes=256)
            previous = (base / "history/2026-11-04.json.gz").read_bytes()
            publisher.publish(snapshot("2026-11-05", "run-2"), base)
            packer.package(base, max_raw_bytes=256)
            self.assertEqual((base / "history/2026-11-04.json.gz").read_bytes(), previous)
            self.assertEqual([archive_io.archive_day(p) for p in archive_io.archive_paths(base / "history")],
                             ["2026-11-04", "2026-11-05"])
            (base / "history/2026-11-04.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Ambiguous"):
                archive_io.archive_paths(base / "history")

    def test_small_files_keep_plain_json(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            pointer = publisher.publish(snapshot("2026-11-04", "run-1"), base)
            result = packer.package(base)
            self.assertEqual(result["snapshotPath"], pointer["snapshotPath"])
            self.assertEqual(result["latestPath"], "data/latest.json")
            self.assertTrue((base / "latest.json").exists())

if __name__ == "__main__":
    unittest.main()
