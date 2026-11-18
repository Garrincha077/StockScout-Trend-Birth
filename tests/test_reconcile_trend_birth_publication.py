import base64
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import reconcile_trend_birth_publication as reconciler

DAY = "2026-11-17"
FIRST = DAY + "-eod-42-1"
CORRECTED = DAY + "-eod-42-2"
DIGEST = "a" * 64
TARGET = {"sessionDate": DAY, "runId": CORRECTED, "unifiedManifestSha256": DIGEST}


class ReconcilerTests(unittest.TestCase):
    def test_stale_intraday_marker_cannot_block_corrected_activation(self):
        old_marker = f"unified-recovery 2026-11-18T08:00Z session={DAY} activation={FIRST} manifest={DIGEST}"
        prior = {"sessionDate": DAY, "runId": FIRST}
        with (
            patch.object(reconciler, "verify_unified", return_value=TARGET),
            patch.object(reconciler, "read_target", return_value=TARGET),
            patch.object(reconciler, "contents", side_effect=[(json.dumps(prior), "old"), (old_marker, "ref")]),
            patch.object(reconciler, "publisher_runs", return_value=[]),
            patch.object(reconciler, "start_publisher", return_value=81) as dispatch,
            patch.object(reconciler, "github", return_value={"commit": {"sha": "commit"}}) as write,
        ):
            reconciler.reconcile()
        dispatch.assert_called_once_with(reconciler.REPO, [])
        marker = base64.b64decode(write.call_args.kwargs["data"]["content"]).decode()
        self.assertIn(old_marker, marker)
        self.assertIn("publisher=81", marker)
        self.assertTrue(reconciler.has_marker(marker, CORRECTED, DIGEST))
        self.assertFalse(reconciler.has_marker(marker, CORRECTED, "b" * 64))

    def test_same_activation_reuses_running_publisher(self):
        prior = {"sessionDate": DAY, "runId": FIRST}
        with (
            patch.object(reconciler, "verify_unified", return_value=TARGET),
            patch.object(reconciler, "contents", return_value=(json.dumps(prior), "ref")),
            patch.object(reconciler, "publisher_runs", return_value=[
                {"head_branch": reconciler.BRANCH, "status": "in_progress"},
            ]),
            patch.object(reconciler, "start_publisher") as dispatch,
        ):
            reconciler.reconcile()
        dispatch.assert_not_called()

    def test_exact_previous_dispatch_is_not_repeated(self):
        marker = f"unified-recovery 2026-11-18T09:00Z session={DAY} activation={CORRECTED} manifest={DIGEST}"
        with (
            patch.object(reconciler, "verify_unified", return_value=TARGET),
            patch.object(reconciler, "publisher_runs", return_value=[]),
            patch.object(reconciler, "contents", side_effect=[
                (json.dumps({"sessionDate": DAY, "runId": FIRST}), "old"), (marker, "ref"),
            ]),
            patch.object(reconciler, "start_publisher") as dispatch,
            self.assertRaisesRegex(RuntimeError, "exact activation already dispatched"),
        ):
            reconciler.reconcile()
        dispatch.assert_not_called()

    def test_uses_successful_jobs_for_exact_upstream_attempt(self):
        jobs = []
        for name, step in (
            ("deploy-pages / smoke", "Verify exact remote run and every mode hash"),
            ("verify-notify", "Deliver five resumable Telegram series"),
        ):
            jobs.append({"name": name, "conclusion": "success",
                         "steps": [{"name": step, "conclusion": "success"}]})
        with (
            patch.object(reconciler, "read_target", return_value=TARGET),
            patch.object(reconciler, "json_request", side_effect=[
                {"status": "completed", "conclusion": "success", "head_branch": "main", "run_attempt": 2},
                {"jobs": jobs},
            ]) as fetch,
        ):
            self.assertEqual(reconciler.verify_unified(), TARGET)
        self.assertIn("/attempts/2/jobs", fetch.call_args.args[0])
