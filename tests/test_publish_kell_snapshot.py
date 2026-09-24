import importlib.util
import json
import pathlib
import tempfile
import unittest

MODULE = pathlib.Path(__file__).parents[1] / "scripts" / "publish_kell_snapshot.py"
spec = importlib.util.spec_from_file_location("publish_kell_snapshot", MODULE)
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class KellSnapshotPublicationTests(unittest.TestCase):
    def make_fixture(self, root: pathlib.Path):
        snapshot_id = "run-1--" + "a" * 64
        publication = {
            "schemaVersion": "trend-birth-publication-v1",
            "snapshotId": snapshot_id,
            "runId": "run-1",
            "sessionDate": "2026-09-23",
            "unifiedManifestSha256": "b" * 64,
        }
        kell = {
            "schemaVersion": "kell-compact-v5",
            "source": {
                "runId": "run-1",
                "sessionDate": "2026-09-23",
                "unifiedManifestSha256": "b" * 64,
            },
            "kellChartData": {
                "schemaVersion": "kell-chart-shard-v2",
                "basePath": "data/kell-charts",
                "shardCount": 1,
            },
            "kellCandidates": [],
        }
        publication_path = root / "publication.json"
        kell_path = root / "kell-latest.json"
        charts = root / "kell-charts"
        charts.mkdir()
        publication_path.write_text(json.dumps(publication))
        kell_path.write_text(json.dumps(kell))
        (charts / "shard-000.json").write_text(json.dumps({
            "schemaVersion": "kell-chart-shard-v2",
            "source": {
                "runId": "run-1",
                "sessionDate": "2026-09-23",
                "unifiedManifestSha256": "b" * 64,
            },
            "shard": 0,
            "charts": {},
        }))
        return publication, publication_path, kell_path, charts

    def test_publishes_snapshot_specific_kell_and_charts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            publication, publication_path, kell_path, charts = self.make_fixture(root)
            result = publisher.publish(publication_path, kell_path, charts, root)
            self.assertEqual(result["status"], "created")
            snap = root / "kell-snapshots" / f"{publication['snapshotId']}.json"
            self.assertTrue(snap.exists())
            payload = json.loads(snap.read_text())
            self.assertEqual(payload["source"]["reviewSnapshotId"], publication["snapshotId"])
            self.assertEqual(
                payload["kellChartData"]["basePath"],
                f"data/kell-chart-snapshots/{publication['snapshotId']}",
            )
            self.assertTrue(
                (root / "kell-chart-snapshots" / publication["snapshotId"] / "shard-000.json").exists()
            )
            self.assertTrue((root / "kell-history" / "2026-09-23.json").exists())

    def test_existing_snapshot_is_reused_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            publication, publication_path, kell_path, charts = self.make_fixture(root)
            publisher.publish(publication_path, kell_path, charts, root)
            snap = root / "kell-snapshots" / f"{publication['snapshotId']}.json"
            before = snap.read_text()
            kell = json.loads(kell_path.read_text())
            kell["newField"] = "new scoring output"
            kell_path.write_text(json.dumps(kell))
            result = publisher.publish(publication_path, kell_path, charts, root)
            self.assertEqual(result["status"], "reused")
            self.assertEqual(snap.read_text(), before)

    def test_rejects_mixed_review_and_kell_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            _publication, publication_path, kell_path, charts = self.make_fixture(root)
            kell = json.loads(kell_path.read_text())
            kell["source"]["sessionDate"] = "2026-09-22"
            kell_path.write_text(json.dumps(kell))
            with self.assertRaisesRegex(ValueError, "sessionDate"):
                publisher.publish(publication_path, kell_path, charts, root)


if __name__ == "__main__":
    unittest.main()
