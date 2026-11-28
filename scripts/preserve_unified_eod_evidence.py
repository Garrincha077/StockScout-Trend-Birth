#!/usr/bin/env python3
"""Preserve exact expiring Unified Pages source artifacts without rewriting EOD history.

One-shot, fail-closed evidence capture. Assets go to a draft GitHub Release rather
than the growing Git repository or Vercel. No rescoring, EOD date insertion, or
source data invention is performed here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import zipfile

SOURCE_REPO = "Garrincha077/StockScout-Unified"
RELEASE_TAG = "tb-eod-source-evidence-2026-11-28"
SOURCES = (
    {
        "sessionDate": "2026-11-23",
        "workflowRunId": 45361079072,
        "headSha": "79281c5178837075e6938fd83146782de924b48b",
        "artifactId": 14908740778,
        "artifactName": "github-pages",
        "artifactSize": 160438581,
        "artifactDigest": "sha256:dd28f03b52d3657bf0545d3dd71488541f829639b033ddd276ed14ce870053b9",
        "expiresAt": "2026-12-08T09:49:42Z"
    },
    {
        "sessionDate": "2026-11-24",
        "workflowRunId": 45546702411,
        "headSha": "79281c5178837075e6938fd83146782de924b48b",
        "artifactId": 14993531122,
        "artifactName": "github-pages",
        "artifactSize": 161210718,
        "artifactDigest": "sha256:2c7f9201cc3bad967b3c28d81eda2d906b9bf13c9a7a1f67acbcb254d3d1fb80",
        "expiresAt": "2026-12-09T05:03:05Z"
    },
    {
        "sessionDate": "2026-11-25",
        "workflowRunId": 45750493320,
        "headSha": "79281c5178837075e6938fd83146782de924b48b",
        "artifactId": 15088275288,
        "artifactName": "github-pages",
        "artifactSize": 162090568,
        "artifactDigest": "sha256:0541de5aa8ca3df44e190310955cdb6fb64385fd72545354689b728ffd29f3ac",
        "expiresAt": "2026-12-10T04:36:44Z"
    },
    {
        "sessionDate": "2026-11-27",
        "workflowRunId": 46102672662,
        "headSha": "79281c5178837075e6938fd83146782de924b48b",
        "artifactId": 15247577878,
        "artifactName": "github-pages",
        "artifactSize": 162430824,
        "artifactDigest": "sha256:0f37896b3e1b00f8b857f96190cc5e99908ed787074e46f159dc98450a5a1b61",
        "expiresAt": "2026-12-12T04:06:25Z"
    },
)
REQUIRED_MANIFESTS = (
    "data/manifest.json",
    "data/modes/bottom-fishing/manifest.json",
    "data/modes/next/manifest.json",
    "data/modes/ryan-original/manifest.json",
)


def _gh(*args: str, binary: bool = False):
    output = subprocess.run(
        ["gh", *args], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout
    return output if binary else json.loads(output.decode("utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(part)
    return "sha256:" + digest.hexdigest()


def verify_pages_bundle(path: Path, source: dict) -> dict:
    """Validate ZIP CRC and tar-contained point-in-time source identity in place."""
    found: dict[str, dict] = {}
    with zipfile.ZipFile(path) as packed:
        if "artifact.tar" not in packed.namelist():
            raise ValueError("Pages artifact has no artifact.tar")
        bad = packed.testzip()
        if bad:
            raise ValueError("Invalid Pages ZIP CRC: " + bad)
        with packed.open("artifact.tar") as stream:
            with tarfile.open(fileobj=stream, mode="r|*") as tar:
                for member in tar:
                    name = member.name.removeprefix("./")
                    if not member.isfile() or name not in REQUIRED_MANIFESTS:
                        continue
                    handle = tar.extractfile(member)
                    if handle is None:
                        raise ValueError("Unreadable Pages manifest: " + name)
                    found[name] = json.load(handle)
                    if len(found) == len(REQUIRED_MANIFESTS):
                        break
    if set(found) != set(REQUIRED_MANIFESTS):
        raise ValueError("Pages bundle missing source manifests: " + str(sorted(set(REQUIRED_MANIFESTS) - set(found))))
    run_ids = set()
    for name in REQUIRED_MANIFESTS:
        manifest = found[name]
        if manifest.get("sessionDate") != source["sessionDate"]:
            raise ValueError("Pages session date mismatch: " + name)
        run_id = str(manifest.get("runId") or "")
        if not run_id.startswith(source["sessionDate"] + "-eod-" + str(source["workflowRunId"]) + "-"):
            raise ValueError("Pages workflow run identity mismatch: " + name)
        run_ids.add(run_id)
    if len(run_ids) != 1:
        raise ValueError("Disagreeing point-in-time run IDs within Pages bundle")
    return {"sessionDate": source["sessionDate"], "runId": run_ids.pop(),
            "verifiedManifestPaths": list(REQUIRED_MANIFESTS)}


def _source_api_check(source: dict) -> None:
    payload = _gh("api", f"repos/{SOURCE_REPO}/actions/runs/{source['workflowRunId']}/artifacts?per_page=100")
    matching = [a for a in payload.get("artifacts", []) if a.get("id") == source["artifactId"]]
    if len(matching) != 1:
        raise ValueError("Exact original artifact absent: " + str(source["artifactId"]))
    actual = matching[0]
    for key, expected in (
        ("name", source["artifactName"]),
        ("size_in_bytes", source["artifactSize"]),
        ("digest", source["artifactDigest"]),
        ("expires_at", source["expiresAt"]),
    ):
        if actual.get(key) != expected:
            raise ValueError("Original artifact metadata changed for " + str(source["artifactId"]) + ": " + key)
    if actual.get("expired"):
        raise ValueError("Original Pages artifact already expired")
    if (actual.get("workflow_run") or {}).get("head_sha") != source["headSha"]:
        raise ValueError("Original source commit mismatch")


def preserve(destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    verified = []
    for source in SOURCES:
        _source_api_check(source)
        filename = "unified-eod-" + source["sessionDate"] + "-pages.zip"
        target = destination / filename
        if not target.exists():
            with target.open("wb") as output:
                subprocess.run([
                    "gh", "api", f"repos/{SOURCE_REPO}/actions/artifacts/{source['artifactId']}/zip"
                ], stdout=output, check=True, stderr=subprocess.PIPE)
        if target.stat().st_size != source["artifactSize"]:
            raise ValueError("Artifact ZIP size mismatch: " + filename)
        digest = _sha256(target)
        if digest != source["artifactDigest"]:
            raise ValueError("Artifact ZIP SHA256 mismatch: " + filename)
        identity = verify_pages_bundle(target, source)
        verified.append({**source, **identity, "archivedName": filename,
                         "verifiedSha256": digest, "verifiedSize": target.stat().st_size})
        print(json.dumps({"verified": source["sessionDate"], "runId": identity["runId"],
                          "sha256": digest, "bytes": target.stat().st_size}), flush=True)

    manifest = {
        "schemaVersion": "tb-original-unified-pages-evidence-v1",
        "sourceRepository": SOURCE_REPO,
        "preservedAtUtc": datetime.now(timezone.utc).isoformat(),
        "storage": "draft GitHub Release; not part of Git history or Vercel build",
        "releaseTag": RELEASE_TAG,
        "purpose": "Provenance preservation only: no historical stage or outcome mutation",
        "sources": verified,
    }
    (destination / "source-evidence-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_release(manifest: dict, repo: str, manifest_path: Path | None = None) -> None:
    if (manifest.get("schemaVersion") != "tb-original-unified-pages-evidence-v1" or
        manifest.get("sourceRepository") != SOURCE_REPO or
        manifest.get("releaseTag") != RELEASE_TAG):
        raise ValueError("Incompatible source evidence manifest")
    sources = manifest.get("sources")
    if (not isinstance(sources, list) or len(sources) != len(SOURCES) or
        any(not isinstance(row, dict) or not isinstance(row.get("sessionDate"), str) for row in sources) or
        {row.get("sessionDate") for row in sources} != {row["sessionDate"] for row in SOURCES}):
        raise ValueError("Evidence manifest must contain all pinned source sessions exactly once")
    by_day = {row["sessionDate"]: row for row in sources}
    expected = []
    for pinned in SOURCES:
        row = by_day[pinned["sessionDate"]]
        if any(row.get(key) != value for key, value in pinned.items()):
            raise ValueError("Evidence source identity differs from pinned artifact: " + pinned["sessionDate"])
        name = "unified-eod-" + pinned["sessionDate"] + "-pages.zip"
        if (row.get("archivedName") != name or
            row.get("verifiedSize") != pinned["artifactSize"] or
            row.get("verifiedSha256") != pinned["artifactDigest"]):
            raise ValueError("Evidence source ZIP differs from pinned bytes: " + pinned["sessionDate"])
        expected.append((name, pinned["artifactSize"], pinned["artifactDigest"]))
    releases = _gh("api", f"repos/{repo}/releases?per_page=100")
    matching = [item for item in releases if item.get("tag_name") == RELEASE_TAG]
    if len(matching) != 1:
        raise ValueError("Expected one exact draft evidence release for pinned tag")
    release = matching[0]
    if not release.get("draft"):
        raise ValueError("Evidence release must remain a private draft")
    assets = {a["name"]: a for a in release.get("assets", [])}
    expected.append(("source-evidence-manifest.json",
                     manifest_path.stat().st_size if manifest_path else None,
                     _sha256(manifest_path) if manifest_path else None))
    for name, size, digest in expected:
        asset = assets.get(name)
        if not asset:
            raise ValueError("Missing GitHub Release asset: " + name)
        if size is not None and asset.get("size") != size:
            raise ValueError("GitHub Release asset size mismatch: " + name)
        remote_digest = asset.get("digest")
        if digest is not None and remote_digest != digest:
            raise ValueError("GitHub Release asset digest mismatch: " + name)
    print(json.dumps({"status": "verified_draft_release", "tag": RELEASE_TAG,
                      "releaseUrl": release.get("html_url"), "assets": [n for n, _, _ in expected]}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify-release", action="store_true")
    args = parser.parse_args()
    if args.verify_release:
        manifest_path = args.output_dir / "source-evidence-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        verify_release(manifest, os.environ["GITHUB_REPOSITORY"], manifest_path)
    else:
        preserve(args.output_dir)


if __name__ == "__main__":
    main()
