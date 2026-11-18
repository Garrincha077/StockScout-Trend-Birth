"""Publish deterministic, content-addressed review snapshots. No network or notifications."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path

EOD_RUN = re.compile(r"^(\d{4}-\d{2}-\d{2})-eod-(\d+)-(\d+)$")


def validate_revision(previous: dict, session: str, run: str) -> None:
    previous_session = previous.get("sessionDate", "")
    if session < previous_session:
        raise ValueError("Refusing to roll back the latest market session")
    if session != previous_session:
        return
    before = EOD_RUN.fullmatch(str(previous.get("runId") or ""))
    after = EOD_RUN.fullmatch(run)
    if before and after and (int(after[2]), int(after[3])) < (int(before[2]), int(before[3])):
        raise ValueError("Refusing to roll back a newer activation of the same EOD session")


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



def bootstrap(snapshot: dict, snapshot_id: str) -> dict | None:
    """Small, immutable initial view; research keeps its original exact snapshot."""
    lists = snapshot.get("shortlists") or {}
    if lists.get("schemaVersion") != "stockscout-shortlists-v2":
        return None
    return {
        "schemaVersion": "trend-birth-review-bootstrap-v1",
        "reviewSnapshotId": snapshot_id,
        "source": snapshot["source"],
        "shortlists": lists,
        "trendBirthRadar": snapshot.get("trendBirthRadar"),
        "kellScoring": snapshot.get("kellScoring"),
        "candidateCount": snapshot.get("candidateCount", 0),
        "candidates": [],
    }


def publish_bootstrap(snapshot: dict, manifest: dict, directory: Path) -> bool:
    compact = bootstrap(snapshot, manifest["snapshotId"])
    if compact is None:
        return False
    snapshot_id = manifest["snapshotId"]
    relative = "review-bootstrap-v1/" + snapshot_id + ".json"
    changed = _write_bootstrap(directory / relative, compact)
    manifest["bootstrapPath"] = "data/" + relative
    if snapshot.get("earlyTrendResearch"):
        relative = "review-bootstrap-v2/" + snapshot_id + ".json"
        lists = compact["shortlists"].copy()
        compact["shortlists"] = lists
        compact["deferredShortlists"] = {}
        for view in ("weeklyTrendBirth", "kellSwing", "kellDaily"):
            if view not in lists:
                continue
            payload = encode({
                "schemaVersion": "trend-birth-shortlist-v1", "snapshotId": snapshot_id,
                "source": snapshot["source"], "view": view, "items": lists[view],
            })
            digest = hashlib.sha256(payload).hexdigest()
            shard = f"review-bootstrap-v2/{snapshot_id}/{view}--{digest}.json"
            target = directory / shard
            if target.exists() and target.read_bytes() != payload:
                raise ValueError("Immutable Review shortlist collision")
            changed |= write_changed(target, payload)
            lists[view] = []
            compact["deferredShortlists"][view] = {"path": "data/" + shard, "sha256": digest}
        changed |= _write_bootstrap(directory / relative, compact)
        manifest["deferredBootstrapPath"] = "data/" + relative
    return changed


def _write_bootstrap(target: Path, bootstrap_data: dict) -> bool:
    content = encode(bootstrap_data)
    if target.exists() and target.read_bytes() != content:
        raise ValueError("Immutable bootstrap collision")
    return write_changed(target, content)


def validate_shortlists(directory: Path, publication: dict) -> None:
    snapshot_id = publication.get("snapshotId")
    base = f"review-bootstrap-v2/{snapshot_id}"
    deferred = publication.get("deferredBootstrapPath")
    if deferred is None and publication.get("bootstrapPath") != "data/" + base + ".json":
        return
    bootstrap = json.loads((directory / (base + ".json")).read_bytes())
    legacy = None
    if deferred is not None:
        legacy_path = f"review-bootstrap-v1/{snapshot_id}.json"
        if deferred != "data/" + base + ".json" or publication.get("bootstrapPath") != "data/" + legacy_path:
            raise ValueError("Review bootstrap compatibility paths differ from publication")
        legacy = json.loads((directory / legacy_path).read_bytes())
        if (legacy.get("reviewSnapshotId") != snapshot_id or legacy.get("source") != bootstrap["source"] or
                not isinstance(legacy.get("shortlists"), dict)):
            raise ValueError("Compatible Review bootstrap differs from publication")
    for view, ref in bootstrap["deferredShortlists"].items():
        if view not in {"weeklyTrendBirth", "kellSwing", "kellDaily"}:
            raise ValueError("Unexpected deferred Review shortlist")
        path = f"{base}/{view}--{ref['sha256']}.json"
        if ref["path"] != "data/" + path:
            raise ValueError("Deferred Review shortlist path differs from publication")
        raw = (directory / path).read_bytes()
        payload = json.loads(raw)
        if (hashlib.sha256(raw).hexdigest() != ref["sha256"] or
                payload["schemaVersion"] != "trend-birth-shortlist-v1" or payload["view"] != view or
                payload["snapshotId"] != snapshot_id or payload["source"] != bootstrap["source"] or
                not isinstance(payload["items"], list)):
            raise ValueError("Deferred Review shortlist differs from publication")
        if legacy is not None and payload["items"] != legacy["shortlists"].get(view):
            raise ValueError("Compatible Review shortlist differs from publication")


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
    if previous is None and latest.exists():
        previous = json.loads(latest.read_bytes())["source"]
    if previous:
        validate_revision(previous, session, run)
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
    changed = publish_bootstrap(snapshot, manifest, directory)
    if previous and previous.get("snapshotId") == snapshot_id and "research" in previous:
        manifest["research"] = previous["research"]
    changed = write_changed(archive, content) or changed
    # Preserve existing date links forever, including the pre-v1 archives.
    date_archive = directory / "history" / f"{session}.json"
    if not date_archive.exists() and not date_archive.with_suffix(".json.gz").exists():
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
