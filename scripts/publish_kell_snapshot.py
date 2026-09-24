#!/usr/bin/env python3
"""Publish an immutable Kell companion for an immutable Review snapshot.

The latest Kell payload remains a moving pointer for the latest UI. Historical
Telegram links use a snapshot-specific companion and chart directory, so they
never mix an archived Review snapshot with a newer Kell dataset.
"""
from __future__ import annotations

import argparse
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


def validate_existing(snapshot_path: Path, chart_dir: Path, publication: dict) -> None:
    existing = load_json(snapshot_path)
    source = existing.get("source") or {}
    for key in ("runId", "sessionDate", "unifiedManifestSha256"):
        if source.get(key) != publication.get(key):
            raise ValueError(f"Existing immutable Kell snapshot identity mismatch for {key}")
    if source.get("reviewSnapshotId") != publication.get("snapshotId"):
        raise ValueError("Existing immutable Kell snapshot points at another Review snapshot")
    meta = existing.get("kellChartData") or {}
    expected = int(meta.get("shardCount") or 0)
    files = sorted(chart_dir.glob("shard-*.json")) if chart_dir.exists() else []
    if expected < 1 or len(files) != expected:
        raise ValueError("Existing immutable Kell chart archive is incomplete")


def publish(
    publication_path: Path,
    kell_path: Path,
    charts_dir: Path,
    directory: Path,
) -> dict:
    publication = load_json(publication_path)
    kell = load_json(kell_path)
    validate_identity(publication, kell)

    snapshot_id = publication["snapshotId"]
    session = publication["sessionDate"]
    snapshot_dir = directory / "kell-snapshots"
    chart_root = directory / "kell-chart-snapshots"
    history_dir = directory / "kell-history"
    snapshot_path = snapshot_dir / f"{snapshot_id}.json"
    immutable_chart_dir = chart_root / snapshot_id

    if snapshot_path.exists():
        validate_existing(snapshot_path, immutable_chart_dir, publication)
        if not (history_dir / f"{session}.json").exists():
            history_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(snapshot_path, history_dir / f"{session}.json")
        return {
            "status": "reused",
            "snapshotId": snapshot_id,
            "sessionDate": session,
            "kellSnapshotPath": str(snapshot_path.relative_to(directory)),
        }

    meta = kell.get("kellChartData") or {}
    expected = int(meta.get("shardCount") or 0)
    chart_files = sorted(charts_dir.glob("shard-*.json"))
    if len(chart_files) != expected:
        raise ValueError(
            f"Kell chart shard count mismatch: expected {expected}, found {len(chart_files)}"
        )

    pinned = json.loads(json.dumps(kell))
    pinned.setdefault("source", {})["reviewSnapshotId"] = snapshot_id
    pinned["kellChartData"]["basePath"] = f"data/kell-chart-snapshots/{snapshot_id}"

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    chart_root.mkdir(parents=True, exist_ok=True)
    temp_chart_dir = chart_root / f".{snapshot_id}.tmp"
    if temp_chart_dir.exists():
        shutil.rmtree(temp_chart_dir)
    shutil.copytree(charts_dir, temp_chart_dir)
    temp_chart_dir.rename(immutable_chart_dir)

    write_json(snapshot_path, pinned)
    history_path = history_dir / f"{session}.json"
    if not history_path.exists():
        write_json(history_path, pinned)

    return {
        "status": "created",
        "snapshotId": snapshot_id,
        "sessionDate": session,
        "kellSnapshotPath": str(snapshot_path.relative_to(directory)),
        "chartPath": str(immutable_chart_dir.relative_to(directory)),
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
