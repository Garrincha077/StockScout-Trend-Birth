"""Losslessly package oversized Review JSON, retaining original SHA-256.

Run only after successful EOD/Review/Kell checks. Existing dated archives stay
immutable; oversized new archives use deterministic gzip and original digests.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from review_archive_io import archive_for_day

RAW_LIMIT = 96 * 1024 * 1024
GIT_BLOB_LIMIT = 100 * 1024 * 1024

def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def raw_bytes(path: Path) -> bytes:
    return gzip.decompress(path.read_bytes()) if path.name.endswith(".json.gz") else path.read_bytes()

def _pack(path: Path, *, max_raw_bytes: int, immutable: bool) -> Path:
    if not path.is_file():
        raise FileNotFoundError("Validated Review file is missing: " + str(path))
    raw = path.read_bytes()
    packed_path = path.with_suffix(path.suffix + ".gz")
    if len(raw) <= max_raw_bytes:
        if len(raw) >= GIT_BLOB_LIMIT:
            raise ValueError("Raw Review blob exceeds GitHub hard limit: " + str(path))
        if not immutable:
            packed_path.unlink(missing_ok=True)
        return path
    packed = gzip.compress(raw, compresslevel=6, mtime=0)
    if len(packed) >= GIT_BLOB_LIMIT:
        raise ValueError("Compressed Review blob still exceeds GitHub limit: " + str(path))
    if packed_path.exists() and immutable and packed_path.read_bytes() != packed:
        raise ValueError("Immutable compressed Review archive collision: " + str(packed_path))
    if not packed_path.exists() or packed_path.read_bytes() != packed:
        tmp = packed_path.with_suffix(".gz.tmp")
        tmp.write_bytes(packed)
        tmp.replace(packed_path)
    if raw_bytes(packed_path) != raw:
        raise ValueError("Lossless Review gzip round-trip failed: " + str(path))
    path.unlink()
    return packed_path

def package(directory: Path, *, max_raw_bytes: int = RAW_LIMIT) -> dict:
    pointer = directory / "publication.json"
    manifest = json.loads(pointer.read_bytes())
    if manifest.get("schemaVersion") != "trend-birth-publication-v1":
        raise ValueError("Unsupported Review publication schema")
    sid = manifest["snapshotId"]
    day = manifest["sessionDate"]
    if manifest.get("snapshotPath") != f"data/snapshots/{sid}.json":
        raise ValueError("Unexpected pre-pack Review snapshot path")
    latest = directory / "latest.json"
    snapshot = directory / "snapshots" / (sid + ".json")
    historical = archive_for_day(directory / "history", day)
    historical_path = (historical if historical.name.endswith(".gz") else
                       _pack(historical, max_raw_bytes=max_raw_bytes, immutable=True))
    raw = latest.read_bytes()
    if digest(raw) != manifest["sha256"] or snapshot.read_bytes() != raw:
        raise ValueError("Review publication SHA256/content mismatch before packing")
    source = json.loads(raw)["source"]
    if source.get("runId") != manifest["runId"] or source.get("sessionDate") != day:
        raise ValueError("Review source identity mismatch before packing")
    snapshot_path = _pack(snapshot, max_raw_bytes=max_raw_bytes, immutable=True)
    latest_path = _pack(latest, max_raw_bytes=max_raw_bytes, immutable=False)
    if digest(raw_bytes(snapshot_path)) != manifest["sha256"] or digest(raw_bytes(latest_path)) != manifest["sha256"]:
        raise ValueError("Review hash identity changed during packing")
    manifest["snapshotPath"] = "data/snapshots/" + snapshot_path.name
    manifest["latestPath"] = "data/" + latest_path.name
    manifest["historyPath"] = "data/history/" + historical_path.name
    manifest["historySha256"] = digest(raw_bytes(historical_path))
    manifest["snapshotEncoding"] = "gzip" if snapshot_path.suffix == ".gz" else "json"
    pointer.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")), encoding="utf-8")
    return {"sessionDate": day, "runId": manifest["runId"],
            "snapshotPath": manifest["snapshotPath"], "latestPath": manifest["latestPath"],
            "historyPath": manifest["historyPath"], "sha256": manifest["sha256"]}

def materialize_latest(directory: Path) -> dict:
    """Restore uncompressed latest JSON only in the calibration checkout."""
    manifest = json.loads((directory / "publication.json").read_bytes())
    latest = directory / "latest.json"
    if not latest.exists():
        if manifest.get("latestPath") != "data/latest.json.gz":
            raise ValueError("No verified compressed latest source available")
        raw = raw_bytes(directory / "latest.json.gz")
        if digest(raw) != manifest["sha256"]:
            raise ValueError("Compressed latest SHA256 mismatch")
        latest.write_bytes(raw)
    if digest(latest.read_bytes()) != manifest["sha256"]:
        raise ValueError("Materialized latest SHA256 mismatch")
    return {"restored": True, "sessionDate": manifest["sessionDate"], "runId": manifest["runId"]}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("lab/data"))
    parser.add_argument("--materialize-latest", action="store_true")
    args = parser.parse_args()
    result = materialize_latest(args.directory) if args.materialize_latest else package(args.directory)
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
