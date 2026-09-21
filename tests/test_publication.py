import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def module(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).parents[1] / "scripts" / f"{name}.py"
    )
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


publisher = module("publish_review_snapshot")
builder = module("build_review_snapshot")


def fixture():
    return {
        "source": {"runId": "2026-09-18-eod-123-1", "sessionDate": "2026-09-18"},
        "candidateCount": 1,
        "chartCount": 1,
        "candidates": [{"ticker": "AAA", "chartBars": [[1, 1, 2, 1, 2, 100]]}],
    }


class PublicationTests(unittest.TestCase):
    def test_retry_is_noop_and_revision_preserves_old_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = fixture()
            first = publisher.publish(snapshot, root)
            original = (root / first["snapshotPath"].removeprefix("data/")).read_bytes()
            self.assertFalse(publisher.publish(snapshot, root)["changed"])
            snapshot["candidates"][0]["analysis"] = {"status": "WATCH"}
            second = publisher.publish(snapshot, root)
            self.assertNotEqual(first["snapshotId"], second["snapshotId"])
            self.assertEqual(
                original,
                (root / first["snapshotPath"].removeprefix("data/")).read_bytes(),
            )
            self.assertEqual(original, (root / "history/2026-09-18.json").read_bytes())
            self.assertEqual(
                second["sha256"],
                hashlib.sha256((root / "latest.json").read_bytes()).hexdigest(),
            )

    def test_rejects_rollback_missing_charts_duplicates_and_bad_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            publisher.publish(fixture(), root)
            for mutation in ("rollback", "charts", "duplicate", "run"):
                snapshot = fixture()
                if mutation == "rollback":
                    snapshot["source"]["sessionDate"] = "2026-09-17"
                if mutation == "charts":
                    snapshot["candidates"][0]["chartBars"] = []
                if mutation == "duplicate":
                    snapshot["candidates"] *= 2
                if mutation == "run":
                    snapshot["source"]["runId"] = "../escape"
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    publisher.publish(snapshot, root)

    def test_empty_scan_and_existing_legacy_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "history").mkdir()
            archive = root / "history/2026-09-18.json"
            archive.write_text("legacy")
            snapshot = fixture()
            snapshot.update(candidateCount=0, chartCount=0, candidates=[])
            publisher.publish(snapshot, root)
            self.assertEqual("legacy", archive.read_text())

    def test_mode_manifest_rejects_mixed_activation_and_hash(self):
        manifest = {"runId": "run-a", "sessionDate": "2026-09-18", "status": "healthy"}
        content = json.dumps(manifest).encode()
        unified = {
            **manifest,
            "modes": {
                "next": {
                    "manifestPath": "modes/next/manifest.json",
                    "manifestSha256": hashlib.sha256(content).hexdigest(),
                }
            },
        }
        with patch.object(builder, "_get_bytes", return_value=content):
            self.assertEqual(
                manifest,
                builder.verified_mode_manifest("https://example/", unified, "next"),
            )
            other = copy.deepcopy(unified)
            other["runId"] = "run-b"
            with self.assertRaises(ValueError):
                builder.verified_mode_manifest("https://example/", other, "next")
            other = copy.deepcopy(unified)
            other["modes"]["next"]["manifestSha256"] = "bad"
            with self.assertRaises(ValueError):
                builder.verified_mode_manifest("https://example/", other, "next")


if __name__ == "__main__":
    unittest.main()
