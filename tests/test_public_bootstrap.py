"""Live publication readiness must validate public bootstrap bytes, not pointers alone."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import refresh_review_publication as refresh

RUN = "2026-10-30-eod-41152740415-1"
DIGEST = "a" * 64
TARGET = {"runId": RUN, "sessionDate": "2026-10-30",
          "unifiedManifestSha256": "b" * 64}
IDENTITY = RUN + "--" + DIGEST
POINTER = {**TARGET, "schemaVersion": "trend-birth-publication-v1",
           "snapshotId": IDENTITY, "sha256": DIGEST, "candidateCount": 79,
           "chartCount": 79, "snapshotPath": f"data/snapshots/{IDENTITY}.json",
           "bootstrapPath": f"data/review-bootstrap-v1/{IDENTITY}.json"}
BOOTSTRAP = {
    "schemaVersion": "trend-birth-review-bootstrap-v1",
    "reviewSnapshotId": IDENTITY, "candidateCount": 79, "source": TARGET,
    "shortlists": {"schemaVersion": "stockscout-shortlists-v2",
                   "weeklyTrendBirth": [], "kellDaily": []},
    "trendBirthRadar": {"schemaVersion": "trend-birth-radar-v1",
                        "evaluatedCount": 5, "stageCounts":
                        {"0": 1, "1": 1, "2": 1, "3": 1, "4": 1}},
}


class BootstrapReadinessTests(unittest.TestCase):
    def test_exact_public_bootstrap_is_verified(self):
        urls = []
        def fetch(url):
            urls.append(url)
            return json.dumps(BOOTSTRAP).encode()
        with patch.object(refresh, "fetch_bytes", side_effect=fetch):
            got = refresh.verify_public_bootstrap(POINTER, TARGET)
        self.assertEqual(got["candidateCount"], 79)
        self.assertEqual(got["evaluatedCount"], 5)
        self.assertEqual(urls, [refresh.PUBLIC_ROOT + POINTER["bootstrapPath"]])

    def test_missing_or_wrong_path_fails_without_fetch(self):
        for wrong in (None, "data/latest.json", "https://another.host/data/foo"):
            pointer = {**POINTER, "bootstrapPath": wrong}
            with patch.object(refresh, "fetch_bytes") as fetch, self.assertRaisesRegex(ValueError, "PUBLIC_BOOTSTRAP_PATH"):
                refresh.verify_public_bootstrap(pointer, TARGET)
            fetch.assert_not_called()

    def test_mismatched_payload_rejected(self):
        for section, key, value in [
            ("root", "reviewSnapshotId", "wrong"),
            ("root", "candidateCount", 80),
            ("source", "runId", "another-run"),
            ("source", "unifiedManifestSha256", "c" * 64),
            ("shortlists", "weeklyTrendBirth", None),
            ("trendBirthRadar", "evaluatedCount", 8),
            ("trendBirthRadar", "stageCounts", {"0": 5}),
        ]:
            data = copy.deepcopy(BOOTSTRAP)
            target = data if section == "root" else data[section]
            target[key] = value
            with patch.object(refresh, "fetch_bytes", return_value=json.dumps(data).encode()), self.assertRaisesRegex(ValueError, "PUBLIC_BOOTSTRAP_"):
                refresh.verify_public_bootstrap(POINTER, TARGET)

    def test_missing_bootstrap_never_reports_ready(self):
        with patch.object(refresh, "read_target", return_value=TARGET), \
             patch.object(refresh, "committed_pointer", return_value=POINTER), \
             patch.object(refresh, "fetch_bytes", side_effect=[
                 json.dumps(POINTER).encode(), b"not-json"
             ]), \
             patch.object(refresh, "publisher_runs") as runs, \
             self.assertRaises(json.JSONDecodeError):
            refresh.refresh("owner/repo")
        runs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
