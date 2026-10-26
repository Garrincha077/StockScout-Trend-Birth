"""Offline recovery of missing Trend Birth stage/close evidence from pinned Pages ZIPs.

This creates reconstructed inputs for a separate V3 comparison. It does not
publish, rescan, overwrite V2, retrieve today's prices or send notifications.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from functools import lru_cache
from datetime import date
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
from unittest.mock import patch

import build_review_snapshot as builder
from preserve_unified_eod_evidence import SOURCES, _sha256, verify_pages_bundle
from recover_kell_history_artifact import PagesArtifact, _materialize_tar
from trend_birth_intelligence import CHECK_KEYS, SCOPE, _point_counts
from trend_birth_stage_forward import _date_from_stamp

RADAR_COMMIT = "168fc51bfc207e134d29e6b30201e7c087c3c1d8"
RADAR_SHA256 = "94b5d96166c7366ae9e394ebc5f2a20bb75c46620017f97775827734ff182aa4"
PINNED_MANIFESTS = {
    "2026-10-15":"a1dc2612e175287a84db4eccd97d92d150401397ee10da2f9df6ec2d82059fe5",
    "2026-10-19":"0efee0cab526e0f62eca86b10dfb13a788d31bdd6f9faaebd133405b1eb40e0e",
}
OBSERVED_WATCHLISTS = {
    "2026-10-14": "64970217aa78391333a766accbbfb269e84c7e90267cb0b2fa784e53b68fefc3",
    "2026-10-16": "3f202606366365e66470bd8f95a91eb8a45c0933db58a78d724a70e85ece7821",
}
OBSERVED_TICKERS = ['AGEN','CLOV','DIS','HNST','IONQ','NVAX','ORCL','PCRX','QMCO','QRVO','RNG','RSKD','TWLO','U','W','XYZ']
BASE = "https://offline.invalid/"


def frozen_radar(path: Path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != RADAR_SHA256:
        raise ValueError("Recovery requires the exact frozen radar source")
    spec = importlib.util.spec_from_file_location("tb_recovery_frozen_radar", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if tuple(key for key, _ in module.CHECK_LABELS) != tuple(CHECK_KEYS):
        raise ValueError("Frozen radar check order differs from the retained archive")
    module._parse_day = lru_cache(maxsize=4096)(module._parse_day)
    return module.evaluate_trend_birth


def validate_observed_watchlist(value):
    if value.get("schemaVersion") != "tb-last-observed-tracked-v1":
        raise ValueError("Historical observed watchlist is required")
    expected = OBSERVED_WATCHLISTS.get(value.get("sourceSessionDate"))
    if not expected or value.get("sourceSnapshotSha256") != expected or value.get("tickers") != OBSERVED_TICKERS:
        raise ValueError("Historical observed snapshot identity differs")
    if value.get("sourceRunId") != {"2026-10-14":"2026-10-14-eod-38657441217-1", "2026-10-16":"2026-10-16-eod-38982996258-1"}[value["sourceSessionDate"]]:
        raise ValueError("Historical observed run identity differs")
    return value


def historical_watchlist(path: Path):
    return validate_observed_watchlist(json.loads(path.read_bytes()))


@lru_cache(maxsize=4096)
def chart_day(stamp):
    return _date_from_stamp(stamp)


def dated_rows(rows, as_of):
    """Reject future/undated/duplicate/unsorted source observations; never truncate silently."""
    previous = None
    for row in rows:
        stamp = row[0] if isinstance(row, list) else row.get("time") or row.get("date")
        day = chart_day(stamp)
        if day is None or day > as_of or (previous is not None and day <= previous):
            raise ValueError("Non-point-in-time chart rows")
        previous = day
    return rows


@contextmanager
def offline_reader(artifact):
    reads = set()
    def read(url):
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.query or parts.fragment:
            raise ValueError("Non-archive request refused")
        if parts.netloc == "offline.invalid":
            path = parts.path.lstrip("/")
        elif parts.netloc == "garrincha077.github.io" and parts.path.startswith("/StockScout-Unified/"):
            path = parts.path.removeprefix("/StockScout-Unified/")
        else:
            raise ValueError("Network fallback refused: " + parts.netloc)
        content = artifact.bytes(path)
        reads.add(path)
        return content
    with patch.object(builder, "_get_bytes", side_effect=read):
        yield reads


def reconstruct(artifact, evaluate, tracked):
    """Reuse the production scalar merge and chart priority, without Kell/weekly rescoring."""
    unified_bytes = artifact.bytes("data/manifest.json")
    unified = json.loads(unified_bytes)
    as_of, run = unified["sessionDate"], unified["runId"]
    date.fromisoformat(as_of)
    if unified.get("status") != "healthy":
        raise ValueError("Unhealthy source activation")
    pool, modes = {}, {}
    with offline_reader(artifact) as reads:
        for mode in builder.MODES:
            root = BASE + "data/modes/" + mode + "/"
            manifest = builder.verified_mode_manifest(BASE, unified, mode)
            core = builder._asset_json(root, manifest, "core")
            if not isinstance(core, dict):
                raise ValueError("Missing historical core")
            modes[mode] = root, manifest, core
            for row in builder._rows_for_mode(root, mode, manifest, core):
                ticker = builder._ticker(row)
                if not ticker:
                    raise ValueError("Missing historical universe ticker")
                item = pool.setdefault(ticker, {"chartModes": [], "raw": {}})
                if mode not in item["chartModes"]:
                    item["chartModes"].append(mode)
                item["raw"] = ({**item["raw"], **row} if mode == "next" else {**row, **item["raw"]})
        charts = builder._load_preferred_kell_charts(modes, pool)
    if tracked["sourceSessionDate"] >= as_of:
        raise ValueError("Tracked state must predate the recovered session")
    tracked_symbols=tracked["tickers"]
    missing_tracked=set(tracked_symbols)-set(pool)
    if missing_tracked:
        root, manifest, core=modes["bottom-fishing"]
        with offline_reader(artifact):
            charts.update(builder.load_charts(root,manifest,core,missing_tracked))
    unavailable, stages, prices, reasons = [], {}, {}, {}
    for position, ticker in enumerate(sorted(set(pool) | set(tracked_symbols)), 1):
        if position % 500 == 0:
            print(json.dumps({"recovering": as_of, "evaluatedRows": position}), flush=True)
        rows = dated_rows(charts.get(ticker, []), as_of)
        if not rows or chart_day(rows[-1][0] if isinstance(rows[-1], list) else rows[-1].get("time") or rows[-1].get("date")) != as_of:
            unavailable.append(ticker);reasons[ticker]="missing_or_stale_archived_chart"
            continue
        tb = evaluate(rows)
        if not tb.get("available"):
            unavailable.append(ticker);reasons[ticker]=tb.get("reason", "insufficient_archived_history")
            continue
        stages[ticker] = [tb["stage"], sum(1 << i for i, key in enumerate(CHECK_KEYS) if tb["checks"].get(key) is True)]
        # Same production price contract: merged core price/close, then chart close.
        raw = pool.get(ticker, {}).get("raw", {})
        close = rows[-1][4] if isinstance(rows[-1], list) else rows[-1]["close"]
        price = builder._number(raw, "price", "close") or float(close)
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Invalid source close: " + ticker)
        prices[ticker] = round(price, 6)
    counts = {str(i): sum(value[0] == i for value in stages.values()) for i in range(5)}
    point = {"sessionDate": as_of, "runId": run, "counts": counts, "evaluatedCount": len(stages),
             "unavailableCount": len(unavailable), "stages": stages, "unavailable": unavailable}
    _point_counts(point)
    close = {"sessionDate": as_of, "runId": run, "expectedEvaluated": len(stages),
             "priceCount": len(prices), "prices": prices}
    return {"schemaVersion": "trend-birth-recovered-input-v3", "scope": SCOPE,
            "source": {"sessionDate": as_of, "runId": run,
                       "unifiedManifestSha256": hashlib.sha256(unified_bytes).hexdigest(),
                       "sourceGeneratedAt": unified.get("generatedAt"),
                       "trackedInput": tracked,
                       "trackedMembershipExactOnRecoveredSession": False,
                       "unavailableReasons": reasons, "radarCommit": RADAR_COMMIT, "radarSha256": RADAR_SHA256,
                       "semantics": "frozen-radar-recomputed-on-authentic-point-in-time-inputs",
                       "observedByTrendBirthOnSession": False,
                       "unifiedCandidateCount": len(pool), "chartCoverageCount": len(charts),
                       "archiveReadCount": len(reads), "networkFallbacks": 0},
            "stagePoint": point, "closePoint": close}


def recover(zip_path, pinned, radar_path, tracked_path, output):
    if output.exists():
        raise ValueError("Refusing to overwrite recovered evidence")
    if zip_path.stat().st_size != pinned["artifactSize"] or _sha256(zip_path) != pinned["artifactDigest"]:
        raise ValueError("Source ZIP does not match pinned evidence")
    verify_pages_bundle(zip_path, pinned)
    evaluate = frozen_radar(radar_path)
    tracked = historical_watchlist(tracked_path)
    with tempfile.TemporaryDirectory() as tmp:
        tar_path = Path(tmp) / "artifact.tar"
        _materialize_tar(zip_path, tar_path)
        artifact = PagesArtifact(tar_path)
        try:
            result = reconstruct(artifact, evaluate, tracked)
        finally:
            artifact.close()
    result["source"]["originalArtifact"] = dict(pinned)
    if result["source"]["sessionDate"] != pinned["sessionDate"]:
        raise ValueError("Recovered session differs from pinned source")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--radar", type=Path, required=True)
    parser.add_argument("--tracked", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pinned = next((row for row in SOURCES if row["sessionDate"] == args.session), None)
    if pinned is None:
        raise ValueError("Unpinned source session")
    result = recover(args.artifact, pinned, args.radar, args.tracked, args.output)
    print(json.dumps({"source": result["source"], "counts": result["stagePoint"]["counts"],
                      "prices": result["closePoint"]["priceCount"]}), flush=True)


if __name__ == "__main__":
    main()
