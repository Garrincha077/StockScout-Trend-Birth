"""Publish and verify bounded ticker lookups for a single Review activation."""

import argparse
import hashlib
import json
from pathlib import Path
import re

from build_kell_compact import compact_candidate
from publish_review_snapshot import encode, write_changed

BUCKETS = 64
SCHEMA = "trend-birth-watchlist-bucket-v1"
IDENTITY_KEYS = ("runId", "sessionDate", "unifiedManifestSha256")
CHART_PATH = re.compile(r"data/kell-chart-(?:runs|snapshots)/[A-Za-z0-9][A-Za-z0-9_-]{0,259}")
SNAPSHOT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}--[a-f0-9]{64}")


def read(path):
    return json.loads(path.read_bytes())


def bucket(ticker):
    index = 0
    for byte in ticker.encode("utf-8"):
        index = (31 * index + byte) % BUCKETS
    return index


def identity(data):
    return {key: data[key] for key in IDENTITY_KEYS}


def index(data, key):
    return {row["ticker"]: row for row in data.get(key, [])}


def build_rows(full, companion):
    unified = index(full, "unifiedCandidateIndex")
    tracked = index(full, "trendBirthCandidateIndex")
    review = index(full, "candidates")
    kell = index(companion, "kellCandidates")
    for ticker in sorted(unified.keys() | tracked.keys() | review.keys() | kell.keys()):
        current = tracked.get(ticker) or unified.get(ticker, {})
        base = review.get(ticker, {})
        overlay = kell.get(ticker, {})
        combined = current | base | overlay
        combined["metrics"] = (current.get("metrics") or {}) | (base.get("metrics") or {}) | (overlay.get("metrics") or {})
        for key in ("sources", "unifiedSources"):
            combined[key] = list(dict.fromkeys(value for row in (current, base, overlay) for value in row.get(key, [])))
        if current.get("trackedWatchlist"):
            combined["trendBirth"] = current["trendBirth"]
        if current.get("earlyTrend"):
            combined["earlyTrend"] = current["earlyTrend"]
        use_inline = bool(combined.get("chartBars"))
        row = compact_candidate(combined, include_bars=use_inline)
        row["watchlistUnifiedOnly"] = bool(current and not base and not overlay and not current.get("trackedOnly"))
        row["analysis"] = base.get("analysis") or {}
        if not use_inline and overlay.get("chartAvailable"):
            row["chartShard"] = overlay["chartShard"]
        row["chartAvailable"] = use_inline or "chartShard" in row
        yield ticker, row


def build(directory, review_path, publication_path):
    publication = read(publication_path)
    snapshot_id = publication["snapshotId"]
    if not SNAPSHOT_ID.fullmatch(snapshot_id):
        raise ValueError("Invalid Review snapshot ID")
    content = review_path.read_bytes()
    if hashlib.sha256(content).hexdigest() != publication["sha256"]:
        raise ValueError("Watchlist source differs from Review snapshot")
    full = json.loads(content)
    companion = read(directory / "kell-snapshots" / (snapshot_id + ".json"))
    source = identity(publication)
    if identity(full["source"]) != source or identity(companion["source"]) != source:
        raise ValueError("Watchlist and Review use different source activations")
    if companion["source"]["reviewSnapshotId"] != snapshot_id:
        raise ValueError("Watchlist Kell companion is not pinned to Review")
    chart_base = companion["kellChartData"]["basePath"]
    if not CHART_PATH.fullmatch(chart_base):
        raise ValueError("Invalid immutable Watchlist chart base")
    rows = [{} for _ in range(BUCKETS)]
    for ticker, row in build_rows(full, companion):
        rows[bucket(ticker)][ticker] = row
    relative = f"watchlist-runs/{snapshot_id}"
    digests = []
    for number, items in enumerate(rows):
        raw = encode({"schemaVersion": SCHEMA, "source": source,
                      "snapshotId": snapshot_id, "bucket": number, "rows": items})
        target = directory / relative / f"{number:02x}.json"
        if target.exists() and target.read_bytes() != raw:
            raise ValueError("Immutable Watchlist bucket collision")
        write_changed(target, raw)
        digests.append(hashlib.sha256(raw).hexdigest())
    publication["watchlist"] = {
        "schemaVersion": SCHEMA, "basePath": "data/" + relative, "chartBasePath": chart_base,
        "sha256": digests, "tickers": sum(len(items) for items in rows),
    }
    validate(directory, publication)
    write_changed(publication_path, encode(publication))


def validate(directory, publication):
    ref = publication.get("watchlist")
    if ref is None:
        return
    snapshot_id = publication["snapshotId"]
    relative = f"watchlist-runs/{snapshot_id}"
    if (not SNAPSHOT_ID.fullmatch(snapshot_id) or ref["schemaVersion"] != SCHEMA
            or ref["basePath"] != "data/" + relative or len(ref["sha256"]) != BUCKETS
            or not CHART_PATH.fullmatch(ref["chartBasePath"])):
        raise ValueError("Invalid published Watchlist reference")
    count = 0
    chart_refs = {}
    for number, digest in enumerate(ref["sha256"]):
        raw = (directory / relative / f"{number:02x}.json").read_bytes()
        shard = json.loads(raw)
        if (hashlib.sha256(raw).hexdigest() != digest or shard["schemaVersion"] != SCHEMA
                or shard["source"] != identity(publication) or shard["bucket"] != number
                or shard["snapshotId"] != snapshot_id):
            raise ValueError("Watchlist bucket content does not match publication")
        for ticker, row in shard["rows"].items():
            if bucket(ticker) != number or row["ticker"] != ticker:
                raise ValueError("Watchlist ticker belongs to a different bucket")
            if "chartShard" in row:
                chart_refs.setdefault(row["chartShard"], set()).add(ticker)
        count += len(shard["rows"])
    for shard, names in chart_refs.items():
        path = directory / ref["chartBasePath"].removeprefix("data/") / f"shard-{shard:03d}.json"
        payload = read(path)
        if identity(payload["source"]) != identity(publication) or not names <= payload["charts"].keys():
            raise ValueError("Watchlist chart reference belongs to another activation or omits a ticker")
    if count != ref["tickers"]:
        raise ValueError("Watchlist ticker count differs from publication")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("lab/data"))
    parser.add_argument("--validate", action="store_true")
    opts = parser.parse_args()
    publication = opts.directory / "publication.json"
    if opts.validate:
        validate(opts.directory, read(publication))
    else:
        build(opts.directory, opts.directory / "latest.json", publication)


if __name__ == "__main__":
    main()
