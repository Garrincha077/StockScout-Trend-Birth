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
        old_snapshot_id = "run-1--" + "c" * 64
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
        snapshots = root / "snapshots"
        charts.mkdir()
        snapshots.mkdir()
        publication_path.write_text(json.dumps(publication))
        kell_path.write_text(json.dumps(kell))
        (snapshots / f"{snapshot_id}.json").write_text("{}")
        (snapshots / f"{old_snapshot_id}.json").write_text("{}")
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
        return publication, old_snapshot_id, publication_path, kell_path, charts

    def test_publishes_all_run_companions_with_one_shared_chart_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            publication, old_snapshot_id, publication_path, kell_path, charts = self.make_fixture(root)
            result = publisher.publish(publication_path, kell_path, charts, root)
            self.assertEqual(result["status"], "created")
            self.assertEqual(result["companionCount"], 2)
            current = root / "kell-snapshots" / f"{publication['snapshotId']}.json"
            old = root / "kell-snapshots" / f"{old_snapshot_id}.json"
            self.assertTrue(current.exists())
            self.assertTrue(old.exists())

            current_payload = json.loads(current.read_text())
            old_payload = json.loads(old.read_text())
            self.assertEqual(current_payload["source"]["reviewSnapshotId"], publication["snapshotId"])
            self.assertEqual(old_payload["source"]["reviewSnapshotId"], old_snapshot_id)
            self.assertEqual(
                current_payload["kellChartData"]["basePath"],
                old_payload["kellChartData"]["basePath"],
            )
            expected_base = "data/kell-chart-runs/run-1--" + "b" * 64
            self.assertEqual(current_payload["kellChartData"]["basePath"], expected_base)
            self.assertTrue(
                (root / "kell-chart-runs" / ("run-1--" + "b" * 64) / "shard-000.json").exists()
            )
            self.assertTrue((root / "kell-history" / "2026-09-23.json").exists())

    def test_existing_snapshot_is_reused_and_missing_sibling_is_backfilled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            publication, old_snapshot_id, publication_path, kell_path, charts = self.make_fixture(root)
            publisher.publish(publication_path, kell_path, charts, root)
            current = root / "kell-snapshots" / f"{publication['snapshotId']}.json"
            old = root / "kell-snapshots" / f"{old_snapshot_id}.json"
            before = current.read_text()
            old.unlink()

            kell = json.loads(kell_path.read_text())
            kell["newField"] = "new scoring output"
            kell_path.write_text(json.dumps(kell))
            result = publisher.publish(publication_path, kell_path, charts, root)

            self.assertEqual(result["status"], "created")
            self.assertEqual(current.read_text(), before)
            self.assertTrue(old.exists())
            backfilled = json.loads(old.read_text())
            self.assertEqual(backfilled["source"]["reviewSnapshotId"], old_snapshot_id)
            self.assertNotIn("newField", json.loads(current.read_text()))

    def test_rejects_mixed_review_and_kell_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            _publication, _old_snapshot_id, publication_path, kell_path, charts = self.make_fixture(root)
            kell = json.loads(kell_path.read_text())
            kell["source"]["sessionDate"] = "2026-09-22"
            kell_path.write_text(json.dumps(kell))
            with self.assertRaisesRegex(ValueError, "sessionDate"):
                publisher.publish(publication_path, kell_path, charts, root)


if __name__ == "__main__":
    unittest.main()
