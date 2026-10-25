"""Fail-closed tests for one-shot preservation of original Unified EOD Pages evidence."""
from __future__ import annotations

import io
from copy import deepcopy
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import preserve_unified_eod_evidence as evidence


def make_zip(root: Path, source: dict, *, corrupt_day: bool = False,
             corrupt_run: bool = False, omit_mode: bool = False) -> Path:
    tar_path = root / "artifact.tar"
    members = evidence.REQUIRED_MANIFESTS[:-1] if omit_mode else evidence.REQUIRED_MANIFESTS
    with tarfile.open(tar_path, "w") as tar:
        for index, member in enumerate(members):
            date = "2026-10-14" if corrupt_day and index == 1 else source["sessionDate"]
            run = 1 if corrupt_run and index == 2 else source["workflowRunId"]
            payload = json.dumps({
                "sessionDate": date,
                "runId": date + "-eod-" + str(run) + "-1",
            }).encode()
            info = tarfile.TarInfo("./" + member)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    path = root / "pages.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as packed:
        packed.write(tar_path, "artifact.tar")
    return path


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.source = evidence.SOURCES[0]

    def test_exact_source_identity_verified_for_all_four_manifests(self):
        with tempfile.TemporaryDirectory() as d:
            identity = evidence.verify_pages_bundle(make_zip(Path(d), self.source), self.source)
        self.assertEqual(identity["sessionDate"], "2026-10-15")
        self.assertEqual(identity["runId"], "2026-10-15-eod-38825335004-1")
        self.assertEqual(len(identity["verifiedManifestPaths"]), 4)

    def test_mismatched_session_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive = make_zip(Path(d), self.source, corrupt_day=True)
            with self.assertRaisesRegex(ValueError, "session date mismatch"):
                evidence.verify_pages_bundle(archive, self.source)

    def test_mismatched_run_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive = make_zip(Path(d), self.source, corrupt_run=True)
            with self.assertRaisesRegex(ValueError, "workflow run identity mismatch"):
                evidence.verify_pages_bundle(archive, self.source)

    def test_missing_mode_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive = make_zip(Path(d), self.source, omit_mode=True)
            with self.assertRaisesRegex(ValueError, "missing source manifests"):
                evidence.verify_pages_bundle(archive, self.source)

    def test_source_artifact_digest_is_pinned(self):
        row = self.source
        data = {"artifacts": [{
            "id": row["artifactId"], "name": row["artifactName"],
            "size_in_bytes": row["artifactSize"], "digest": row["artifactDigest"],
            "expires_at": row["expiresAt"], "expired": False,
            "workflow_run": {"head_sha": row["headSha"]},
        }]}
        with patch.object(evidence, "_gh", return_value=data):
            evidence._source_api_check(row)
        changed = json.loads(json.dumps(data))
        changed["artifacts"][0]["digest"] = "sha256:incorrect"
        with patch.object(evidence, "_gh", return_value=changed):
            with self.assertRaisesRegex(ValueError, "metadata changed"):
                evidence._source_api_check(row)

    def test_release_requires_draft_and_matching_original_assets(self):
        manifest, release = self.release_fixture()
        with patch.object(evidence, "_gh", return_value=[release]):
            evidence.verify_release(manifest, "x/y")
        release["draft"] = False
        with patch.object(evidence, "_gh", return_value=[release]):
            with self.assertRaisesRegex(ValueError, "private draft"):
                evidence.verify_release(manifest, "x/y")
        release["draft"] = True
        release["assets"][0]["digest"] = "sha256:bad"
        with patch.object(evidence, "_gh", return_value=[release]):
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                evidence.verify_release(manifest, "x/y")

    def release_fixture(self):
        sources = [{**row,
                    "archivedName": "unified-eod-" + row["sessionDate"] + "-pages.zip",
                    "verifiedSize": row["artifactSize"], "verifiedSha256": row["artifactDigest"]}
                   for row in evidence.SOURCES]
        manifest = {"schemaVersion": "tb-original-unified-pages-evidence-v1",
                    "sourceRepository": evidence.SOURCE_REPO,
                    "releaseTag": evidence.RELEASE_TAG, "sources": sources}
        release = {"tag_name": evidence.RELEASE_TAG, "draft": True, "html_url": "https://github.com/x/y/releases/tag/t",
                   "assets": [{"name": row["archivedName"], "size": row["verifiedSize"],
                               "digest": row["verifiedSha256"]} for row in sources] +
                             [{"name": "source-evidence-manifest.json", "size": 10}]}
        return manifest, release

    def test_release_rejects_empty_incomplete_duplicate_and_replaced_sources(self):
        original, release = self.release_fixture()
        changed_identity = deepcopy(original)
        changed_identity["sources"][0]["headSha"] = "0" * 40
        replaced_zip = deepcopy(original)
        replaced_zip["sources"][0]["verifiedSha256"] = "sha256:bad"
        bad_schema = deepcopy(original)
        bad_schema["sourceRepository"] = "other/repository"
        for manifest in [
            {**original, "sources": []},
            {**original, "sources": original["sources"][:1]},
            {**original, "sources": [original["sources"][0]] * 2},
            changed_identity, replaced_zip, bad_schema,
        ]:
            with self.subTest(manifest=manifest):
                with patch.object(evidence, "_gh", return_value=[release]) as gh:
                    with self.assertRaises(ValueError):
                        evidence.verify_release(manifest, "x/y")
                    gh.assert_not_called()

    def test_release_rejects_missing_original_zip_and_changed_manifest_bytes(self):
        manifest, release = self.release_fixture()
        missing = deepcopy(release)
        missing["assets"].pop(0)
        with patch.object(evidence, "_gh", return_value=[missing]):
            with self.assertRaisesRegex(ValueError, "Missing GitHub Release asset"):
                evidence.verify_release(manifest, "x/y")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source-evidence-manifest.json"
            path.write_text(json.dumps(manifest))
            release["assets"][-1].update(size=path.stat().st_size, digest=evidence._sha256(path))
            with patch.object(evidence, "_gh", return_value=[release]):
                evidence.verify_release(manifest, "x/y", path)
            path.write_text(json.dumps({**manifest, "changed": True}))
            with patch.object(evidence, "_gh", return_value=[release]):
                with self.assertRaisesRegex(ValueError, "size mismatch|digest mismatch"):
                    evidence.verify_release(manifest, "x/y", path)


if __name__ == "__main__":
    unittest.main()
