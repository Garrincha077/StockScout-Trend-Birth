"""Publish deterministic, content-addressed review snapshots. No network or notifications."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path


def encode(value: dict) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def validate(snapshot: dict) -> tuple[str, str]:
    source = snapshot["source"]
    session = source["sessionDate"]
    dt.date.fromisoformat(session)
    run = source["runId"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}", run):
        raise ValueError("Invalid runId")
    unified_sha = str(source.get("unifiedManifestSha256") or "")
    if not re.fullmatch(r"[a-f0-9]{64}", unified_sha):
        raise ValueError("Invalid or missing Unified manifest SHA256")
    candidates = snapshot["candidates"]
    tickers = [item["ticker"] for item in candidates]
    if len(tickers) != len(set(tickers)) or any(not ticker for ticker in tickers):
        raise ValueError("Duplicate or empty tickers")
    if snapshot["candidateCount"] != len(candidates):
        raise ValueError("Candidate count mismatch")
    charts = sum(bool(item.get("chartBars")) for item in candidates)
    if snapshot["chartCount"] != charts or charts != len(candidates):
        raise ValueError("Incomplete chart coverage")
    # A genuinely empty scan is valid; incomplete nonempty scans are not.
    return session, run


def write_changed(path: Path, content: bytes) -> bool:
    if path.exists() and path.read_bytes() == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return True


def publish(snapshot: dict, directory: Path) -> dict:
    session, run = validate(snapshot)
    content = encode(snapshot)
    digest = hashlib.sha256(content).hexdigest()
    snapshot_id = f"{run}--{digest}"
    relative = f"snapshots/{snapshot_id}.json"
    archive = directory / relative
    pointer = directory / "publication.json"
    latest = directory / "latest.json"
    previous = json.loads(pointer.read_bytes()) if pointer.exists() else None
    previous_session = previous["sessionDate"] if previous else ""
    if not previous_session and latest.exists():
        previous_session = json.loads(latest.read_bytes())["source"]["sessionDate"]
    if previous_session and session < previous_session:
        raise ValueError("Refusing to roll back the latest market session")
    if archive.exists() and archive.read_bytes() != content:
        raise ValueError("Immutable snapshot collision")
    manifest = {
        "schemaVersion": "trend-birth-publication-v1",
        "snapshotId": snapshot_id,
        "snapshotPath": f"data/{relative}",
        "sha256": digest,
        "runId": run,
        "sessionDate": session,
        "unifiedManifestSha256": snapshot["source"]["unifiedManifestSha256"],
        "candidateCount": snapshot["candidateCount"],
        "chartCount": snapshot["chartCount"],
    }
    changed = write_changed(archive, content)
    # Preserve existing date links forever, including the pre-v1 archives.
    date_archive = directory / "history" / f"{session}.json"
    if not date_archive.exists():
        changed = write_changed(date_archive, content) or changed
    changed = write_changed(latest, content) or changed
    # Commit all files together. Consumers use the pointer only after deployment.
    changed = write_changed(pointer, encode(manifest)) or changed
    return {"changed": changed, **manifest}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--directory", default="lab/data")
    args = parser.parse_args()
    result = publish(json.loads(Path(args.input).read_bytes()), Path(args.directory))
    print(json.dumps(result))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"changed={str(result['changed']).lower()}\n")


if __name__ == "__main__":
    main()
