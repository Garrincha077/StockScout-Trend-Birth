import hashlib
import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import refresh_review_publication as refresh

TARGET = {"runId": "2026-10-01-eod-42-1", "sessionDate": "2026-10-01", "unifiedManifestSha256": "a" * 64}


def pointer(target=TARGET):
    digest = "b" * 64
    identity = target["runId"] + "--" + digest
    return {**target, "schemaVersion": "trend-birth-publication-v1", "sha256": digest,
            "snapshotId": identity, "snapshotPath": f"data/snapshots/{identity}.json",
            "candidateCount": 81, "chartCount": 81}


class RefreshTests(unittest.TestCase):
    def test_calendar_handles_before_close_holiday_and_early_close(self):
        cases = [(datetime(2026, 10, 2, 8, tzinfo=UTC), "2026-10-01"),
                 (datetime(2026, 12, 25, 21, tzinfo=UTC), "2026-12-24"),
                 (datetime(2026, 11, 27, 17, 59, tzinfo=UTC), "2026-11-25"),
                 (datetime(2026, 11, 27, 18, tzinfo=UTC), "2026-11-27")]
        for now, expected in cases:
            self.assertEqual(expected, refresh.latest_completed_session(now))

    def test_all_three_mode_hashes_and_identities_are_required(self):
        active = {"runId": TARGET["runId"], "sessionDate": TARGET["sessionDate"], "status": "healthy", "modes": {}}
        frames = []
        for mode in ("bottom-fishing", "next", "ryan-original"):
            data = json.dumps({"runId": TARGET["runId"], "sessionDate": TARGET["sessionDate"], "mode": mode}).encode()
            active["modes"][mode] = {"manifestPath": f"modes/{mode}/manifest.json", "manifestSha256": hashlib.sha256(data).hexdigest()}
            frames.append(data)
        raw = json.dumps(active).encode()
        with patch.object(refresh, "fetch_bytes", side_effect=[raw, *frames]), patch.object(refresh, "latest_completed_session", return_value=TARGET["sessionDate"]):
            self.assertEqual(hashlib.sha256(raw).hexdigest(), refresh.read_target()["unifiedManifestSha256"])
        frames[1] = b'{}'
        with patch.object(refresh, "fetch_bytes", side_effect=[raw, *frames]), patch.object(refresh, "latest_completed_session", return_value=TARGET["sessionDate"]), self.assertRaisesRegex(ValueError, "hash mismatch"):
            refresh.read_target()

    def test_stale_upstream_is_rejected_before_any_dispatch(self):
        with patch.object(refresh, "fetch_bytes", return_value=json.dumps({"sessionDate": "2026-09-30", "status": "healthy"}).encode()), patch.object(refresh, "latest_completed_session", return_value="2026-10-01"), patch.object(refresh, "gh") as gh, self.assertRaisesRegex(ValueError, "STALE_UPSTREAM"):
            refresh.refresh("owner/repo")
        gh.assert_not_called()

    def test_matching_publication_is_noop_and_checks_upstream_again(self):
        with patch.object(refresh, "read_target", return_value=TARGET) as read, patch.object(refresh, "committed_pointer", return_value=pointer()), patch.object(refresh, "fetch_bytes", return_value=json.dumps(pointer()).encode()), patch.object(refresh, "publisher_runs") as runs, patch.object(refresh, "start_publisher") as start:
            report = refresh.refresh("owner/repo")
        self.assertEqual("fresh", report["status"])
        self.assertEqual(2, read.call_count)
        runs.assert_not_called()
        start.assert_not_called()

    def test_changed_activation_during_noop_verification_is_rejected(self):
        with patch.object(refresh, "read_target", side_effect=[TARGET, {**TARGET, "runId": "changed"}]), patch.object(refresh, "committed_pointer", return_value=pointer()), patch.object(refresh, "fetch_bytes", return_value=json.dumps(pointer()).encode()), self.assertRaisesRegex(ValueError, "changed"):
            refresh.refresh("owner/repo")

    def test_new_activation_dispatches_once_and_waits_for_success(self):
        run = {"id": 43, "event": "workflow_dispatch", "status": "completed", "conclusion": "success"}
        old = {**pointer(), "runId": "old"}
        with patch.object(refresh, "read_target", return_value=TARGET), patch.object(refresh, "committed_pointer", side_effect=[old, pointer()]), patch.object(refresh, "fetch_bytes", side_effect=[json.dumps(old).encode(), json.dumps(pointer()).encode()]), patch.object(refresh, "publisher_runs", side_effect=[[], [run]]), patch.object(refresh, "gh", return_value="") as gh, patch.object(refresh, "api", return_value=run):
            report = refresh.refresh("owner/repo")
        self.assertTrue(report["dispatched"])
        self.assertEqual(43, report["publisherRunId"])
        gh.assert_called_once_with("workflow", "run", refresh.WORKFLOW, "--repo", "owner/repo", "--ref", refresh.BRANCH)

    def test_running_publisher_is_reused_without_second_dispatch(self):
        running = {"id": 43, "status": "in_progress"}
        with patch.object(refresh, "read_target", return_value=TARGET), patch.object(refresh, "committed_pointer", side_effect=[{}, pointer()]), patch.object(refresh, "fetch_bytes", side_effect=[b'{}', json.dumps(pointer()).encode()]), patch.object(refresh, "publisher_runs", return_value=[running]), patch.object(refresh, "start_publisher") as start, patch.object(refresh, "api", return_value={"status": "completed", "conclusion": "success"}):
            self.assertEqual("fresh", refresh.refresh("owner/repo")["status"])
        start.assert_not_called()

    def test_deployment_lag_never_rebuilds_already_committed_data(self):
        with patch.object(refresh, "read_target", return_value=TARGET), patch.object(refresh, "committed_pointer", return_value=pointer()), patch.object(refresh, "fetch_bytes", side_effect=[b'{}', json.dumps(pointer()).encode()]), patch.object(refresh, "publisher_runs", return_value=[]), patch.object(refresh, "start_publisher") as start:
            self.assertEqual("fresh", refresh.refresh("owner/repo")["status"])
        start.assert_not_called()

    def test_failed_publisher_is_reported_without_retry(self):
        with patch.object(refresh, "read_target", return_value=TARGET), patch.object(refresh, "committed_pointer", return_value={}), patch.object(refresh, "fetch_bytes", return_value=b'{}'), patch.object(refresh, "publisher_runs", return_value=[{"id": 43, "status": "in_progress"}]), patch.object(refresh, "api", return_value={"status": "completed", "conclusion": "failure"}), patch.object(refresh, "start_publisher") as start, self.assertRaisesRegex(ValueError, "Publisher failed"):
            refresh.refresh("owner/repo")
        start.assert_not_called()

    def test_dry_run_and_ambiguous_dispatch_do_not_start_another_run(self):
        with patch.object(refresh, "read_target", return_value=TARGET), patch.object(refresh, "committed_pointer", return_value={}), patch.object(refresh, "fetch_bytes", return_value=b'{}'), patch.object(refresh, "publisher_runs", return_value=[]), patch.object(refresh, "gh") as gh:
            self.assertEqual("refresh_needed", refresh.refresh("owner/repo", dry_run=True)["status"])
        gh.assert_not_called()
        with patch.object(refresh, "gh") as gh, patch.object(refresh, "publisher_runs", return_value=[{"id": 43, "event": "workflow_dispatch"}, {"id": 44, "event": "workflow_dispatch"}]), self.assertRaisesRegex(ValueError, "Ambiguous"):
            refresh.start_publisher("owner/repo", [])
        gh.assert_called_once()

    def test_pointer_rejects_wrong_source_hash_path_or_chart_count(self):
        for field, value in [("unifiedManifestSha256", "c" * 64), ("snapshotPath", "data/latest.json"), ("chartCount", 80), ("candidateCount", True)]:
            self.assertFalse(refresh.pointer_matches({**pointer(), field: value}, TARGET))

    def test_controller_has_no_send_and_topic_runs_are_read_only(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/refresh-trend-birth-review-lab.yml").read_text()
        self.assertIn("*/15 1-19 * * *", workflow)
        self.assertIn("github.ref != 'refs/heads/main' || inputs.dry_run", workflow)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", workflow)
        self.assertNotIn("--send", workflow)


if __name__ == "__main__":
    unittest.main()
