import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from publish_review_research import REPORTS, publish, validate_research


class ResearchPublicationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.day = "2026-11-17"
        self.source = {"sessionDate": self.day, "runId": "unified-123",
                       "unifiedManifestSha256": "a" * 64}
        self.pointer = {**self.source, "snapshotId": "unified-123--" + "b" * 64,
                        "sha256": "b" * 64}
        self.write("publication.json", self.pointer)
        for name, (filename, schema) in REPORTS.items():
            payload = {"schemaVersion": schema, "source": dict(self.source)}
            if name == "trendBirthForward":
                payload["asOf"] = self.day
            elif name == "kellForward":
                payload["source"].update({"asOf": self.day, "lastSignalDate": self.day})
            elif name == "alerts":
                payload["reviewSnapshotId"] = self.pointer["snapshotId"]
            self.write(filename, payload)

    def write(self, name, payload):
        (self.directory / name).write_text(json.dumps(payload), encoding="utf-8")

    def read(self, name):
        return json.loads((self.directory / name).read_bytes())

    def test_idempotent_and_keeps_old_bundle_when_recomputed(self):
        original = publish(self.directory)
        self.assertEqual(publish(self.directory), original)
        validate_research(self.directory, self.read("publication.json"))
        filename = REPORTS["kellForward"][0]
        report = self.read(filename)
        report["newCoverageMeasurement"] = 84.06
        self.write(filename, report)
        newer = publish(self.directory)
        self.assertNotEqual(newer, original)
        self.assertTrue((self.directory / original["path"].removeprefix("data/")).is_file())
        validate_research(self.directory, self.read("publication.json"))

    def test_rejects_stale_report_and_keeps_pointer(self):
        publish(self.directory)
        original = self.read("publication.json")
        filename = REPORTS["trendBirthForward"][0]
        report = self.read(filename)
        report["source"]["runId"] = "other-run"
        self.write(filename, report)
        with self.assertRaisesRegex(ValueError, "does not match Review"):
            publish(self.directory)
        self.assertEqual(self.read("publication.json"), original)

    def test_missing_and_partial_archive_cannot_pass(self):
        reference = publish(self.directory)
        path = self.directory / reference["path"].removeprefix("data/")
        path.write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            validate_research(self.directory, self.read("publication.json"))

    def test_matched_comparison_must_use_the_active_cutoff(self):
        publish(self.directory)
        original = self.read("publication.json")
        filename = REPORTS["trendBirthForward"][0]
        report = self.read(filename)
        report["earlyTrend"] = {"matched": {"schemaVersion": "trend-birth-matched-cohorts-v1",
                                            "asOf": "2026-11-16"}}
        self.write(filename, report)
        with self.assertRaisesRegex(ValueError, "Matched Trend Birth cohorts differ"):
            publish(self.directory)
        self.assertEqual(self.read("publication.json"), original)
