#!/usr/bin/env python3
"""Publish immutable Kell companions for immutable Review snapshots.

The moving kell-latest payload is only for the latest UI. Every archived Review
snapshot for the same Unified run gets a compact Kell companion. All companions
for one run share one immutable chart archive, preventing both mixed-run reads
and duplicate chart storage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

SNAPSHOT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}--[a-f0-9]{64}$")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def validate_identity(publication: dict, kell: dict) -> None:
    if publication.get("schemaVersion") != "trend-birth-publication-v1":
        raise ValueError("Unsupported review publication schema")
    snapshot_id = str(publication.get("snapshotId") or "")
    if not SNAPSHOT_ID_RE.fullmatch(snapshot_id):
        raise ValueError("Invalid review snapshotId")
    source = kell.get("source") or {}
    for key in ("runId", "sessionDate", "unifiedManifestSha256"):
        if source.get(key) != publication.get(key):
            raise ValueError(f"Kell/publication identity mismatch for {key}")
    chart_meta = kell.get("kellChartData") or {}
    if chart_meta.get("schemaVersion") not in {"kell-chart-shard-v1", "kell-chart-shard-v2"}:
        raise ValueError("Missing or invalid Kell chart metadata")
    if int(chart_meta.get("shardCount") or 0) < 1:
        raise ValueError("Kell chart metadata has no shards")


def chart_dir_from_payload(payload: dict, directory: Path) -> Path:
    base = str((payload.get("kellChartData") or {}).get("basePath") or "")
    if not base.startswith("data/"):
        raise ValueError("Immutable Kell snapshot has invalid chart basePath")
    return directory / base.removeprefix("data/")


def validate_existing(
    snapshot_path: Path,
    publication: dict,
    expected_snapshot_id: str,
    directory: Path,
) -> dict:
    existing = load_json(snapshot_path)
    source = existing.get("source") or {}
    for key in ("runId", "sessionDate", "unifiedManifestSha256"):
        if source.get(key) != publication.get(key):
            raise ValueError(f"Existing immutable Kell snapshot identity mismatch for {key}")
    if source.get("reviewSnapshotId") != expected_snapshot_id:
        raise ValueError("Existing immutable Kell snapshot points at another Review snapshot")
    meta = existing.get("kellChartData") or {}
    expected = int(meta.get("shardCount") or 0)
    chart_dir = chart_dir_from_payload(existing, directory)
    files = sorted(chart_dir.glob("shard-*.json")) if chart_dir.exists() else []
    if expected < 1 or len(files) != expected:
        raise ValueError("Existing immutable Kell chart archive is incomplete")
    return existing


def matching_review_snapshot_ids(directory: Path, run_id: str, current_snapshot_id: str) -> list[str]:
    ids = {current_snapshot_id}
    snapshots_dir = directory / "snapshots"
    if snapshots_dir.exists():
        for path in snapshots_dir.glob(f"{run_id}--*.json"):
            snapshot_id = path.stem
            if SNAPSHOT_ID_RE.fullmatch(snapshot_id):
                ids.add(snapshot_id)
    return sorted(ids)


def ensure_shared_chart_archive(
    publication: dict,
    kell: dict,
    charts_dir: Path,
    directory: Path,
) -> str:
    snapshot_dir = directory / "kell-snapshots"
    current_path = snapshot_dir / f"{publication['snapshotId']}.json"

    # Reuse the already-published chart archive when upgrading an existing snapshot.
    if current_path.exists():
        existing = validate_existing(
            current_path,
            publication,
            publication["snapshotId"],
            directory,
        )
        return str((existing.get("kellChartData") or {})["basePath"])

    meta = kell.get("kellChartData") or {}
    expected = int(meta.get("shardCount") or 0)
    chart_files = sorted(charts_dir.glob("shard-*.json"))
    if len(chart_files) != expected:
        raise ValueError(
            f"Kell chart shard count mismatch: expected {expected}, found {len(chart_files)}"
        )

    run_key = f"{publication['runId']}--{publication['unifiedManifestSha256']}"
    chart_root = directory / "kell-chart-runs"
    immutable_chart_dir = chart_root / run_key
    if not immutable_chart_dir.exists():
        chart_root.mkdir(parents=True, exist_ok=True)
        temp_chart_dir = chart_root / f".{run_key}.tmp"
        if temp_chart_dir.exists():
            shutil.rmtree(temp_chart_dir)
        shutil.copytree(charts_dir, temp_chart_dir)
        temp_chart_dir.rename(immutable_chart_dir)
    else:
        files = sorted(immutable_chart_dir.glob("shard-*.json"))
        if len(files) != expected:
            raise ValueError("Existing shared Kell chart archive is incomplete")
    return f"data/kell-chart-runs/{run_key}"


def companion_payload(kell: dict, snapshot_id: str, chart_base_path: str) -> dict:
    pinned = json.loads(json.dumps(kell))
    pinned.setdefault("source", {})["reviewSnapshotId"] = snapshot_id
    pinned["kellChartData"]["basePath"] = chart_base_path
    return pinned


def date_snapshot_id(directory: Path, publication: dict) -> str | None:
    history_path = directory / "history" / f"{publication['sessionDate']}.json"
    if not history_path.exists():
        return None
    raw = history_path.read_bytes()
    try:
        source = json.loads(raw).get("source") or {}
    except json.JSONDecodeError:
        return None
    if source.get("runId") != publication.get("runId"):
        return None
    digest = hashlib.sha256(raw).hexdigest()
    snapshot_id = f"{publication['runId']}--{digest}"
    return snapshot_id if SNAPSHOT_ID_RE.fullmatch(snapshot_id) else None


def publish(
    publication_path: Path,
    kell_path: Path,
    charts_dir: Path,
    directory: Path,
) -> dict:
    publication = load_json(publication_path)
    kell = load_json(kell_path)
    validate_identity(publication, kell)

    snapshot_dir = directory / "kell-snapshots"
    history_dir = directory / "kell-history"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    history_dir.mkdir(parents=True, exist_ok=True)

    chart_base_path = ensure_shared_chart_archive(publication, kell, charts_dir, directory)
    snapshot_ids = matching_review_snapshot_ids(
        directory,
        publication["runId"],
        publication["snapshotId"],
    )

    created: list[str] = []
    reused: list[str] = []
    for snapshot_id in snapshot_ids:
        target = snapshot_dir / f"{snapshot_id}.json"
        if target.exists():
            validate_existing(target, publication, snapshot_id, directory)
            reused.append(snapshot_id)
            continue
        write_json(target, companion_payload(kell, snapshot_id, chart_base_path))
        created.append(snapshot_id)

    history_path = history_dir / f"{publication['sessionDate']}.json"
    if not history_path.exists():
        preferred_id = date_snapshot_id(directory, publication)
        if preferred_id and (snapshot_dir / f"{preferred_id}.json").exists():
            shutil.copy2(snapshot_dir / f"{preferred_id}.json", history_path)
        else:
            shutil.copy2(
                snapshot_dir / f"{publication['snapshotId']}.json",
                history_path,
            )

    return {
        "status": "created" if created else "reused",
        "snapshotId": publication["snapshotId"],
        "sessionDate": publication["sessionDate"],
        "chartBasePath": chart_base_path,
        "companionsCreated": created,
        "companionsReused": reused,
        "companionCount": len(snapshot_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", required=True)
    parser.add_argument("--kell", required=True)
    parser.add_argument("--charts-dir", required=True)
    parser.add_argument("--directory", default="lab/data")
    args = parser.parse_args()
    result = publish(
        Path(args.publication),
        Path(args.kell),
        Path(args.charts_dir),
        Path(args.directory),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
