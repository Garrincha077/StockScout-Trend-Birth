#!/usr/bin/env python3
"""Validate that Review, Kell and chart artifacts come from one Unified activation."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
EXPECTED_UNIFIED_REPO = "Garrincha077/StockScout-Unified"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def identity(source: dict) -> tuple[str, str, str]:
    run_id = str(source.get("runId") or "")
    session_date = str(source.get("sessionDate") or "")
    unified_sha = str(source.get("unifiedManifestSha256") or "")
    if not run_id or not session_date or not SHA256_RE.fullmatch(unified_sha):
        raise ValueError("Incomplete Unified source identity")
    return run_id, session_date, unified_sha


def validate(review_path: Path, publication_path: Path, kell_path: Path, charts_dir: Path) -> dict:
    review_bytes = review_path.read_bytes()
    review = json.loads(review_bytes)
    publication = load(publication_path)
    kell = load(kell_path)

    if (review.get("source") or {}).get("repo") != EXPECTED_UNIFIED_REPO:
        raise ValueError("Review source is not StockScout-Unified")
    if (review.get("source") or {}).get("readOnly") is not True:
        raise ValueError("Review source must be read-only")
    if (kell.get("source") or {}).get("readOnly") is not True:
        raise ValueError("Kell source must be read-only")

    review_id = identity(review.get("source") or {})
    kell_id = identity(kell.get("source") or {})
    publication_id = (
        str(publication.get("runId") or ""),
        str(publication.get("sessionDate") or ""),
        str(publication.get("unifiedManifestSha256") or ""),
    )
    if review_id != kell_id:
        raise ValueError("Review and Kell source identities differ")
    if review_id != publication_id:
        raise ValueError("Review publication pointer is not bound to the same Unified activation")

    review_digest = hashlib.sha256(review_bytes).hexdigest()
    if publication.get("sha256") != review_digest:
        raise ValueError("Review publication digest does not match latest.json")

    review_kell = review.get("kellScoring") or {}
    compact_kell = kell.get("kellScoring") or {}
    if review_kell.get("candidateGenerationChanged") is not False:
        raise ValueError("Kell overlay must not change Unified candidate generation")
    if review_kell.get("scope") != "all-unified-candidates":
        raise ValueError("Unexpected Kell scope")
    if review_kell.get("unifiedCandidateCount") != compact_kell.get("unifiedCandidateCount"):
        raise ValueError("Unified candidate count drift between Review and Kell")
    if review.get("kellCandidateCount") != kell.get("kellCandidateCount"):
        raise ValueError("Kell candidate count drift")
    if len(kell.get("kellCandidates") or []) != kell.get("kellCandidateCount"):
        raise ValueError("Compact Kell candidate count mismatch")

    chart_meta = kell.get("kellChartData") or {}
    expected_shards = int(chart_meta.get("shardCount") or 0)
    shard_paths = sorted(charts_dir.glob("shard-*.json"))
    if len(shard_paths) != expected_shards:
        raise ValueError("Kell chart shard count mismatch")

    chart_tickers: set[str] = set()
    for path in shard_paths:
        shard = load(path)
        if identity(shard.get("source") or {}) != review_id:
            raise ValueError(f"{path.name}: source identity mismatch")
        chart_tickers.update((shard.get("charts") or {}).keys())

    expected_tickers = {str(item.get("ticker") or "") for item in kell.get("kellCandidates") or []}
    expected_tickers.discard("")
    if chart_tickers != expected_tickers:
        raise ValueError("Kell chart coverage does not exactly match compact candidates")

    return {
        "status": "ok",
        "runId": review_id[0],
        "sessionDate": review_id[1],
        "unifiedManifestSha256": review_id[2],
        "unifiedCandidateCount": review_kell.get("unifiedCandidateCount"),
        "reviewCandidateCount": review.get("candidateCount"),
        "kellCandidateCount": kell.get("kellCandidateCount"),
        "chartTickerCount": len(chart_tickers),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", default="lab/data/latest.json")
    parser.add_argument("--publication", default="lab/data/publication.json")
    parser.add_argument("--kell", default="lab/data/kell-latest.json")
    parser.add_argument("--charts-dir", default="lab/data/kell-charts")
    args = parser.parse_args()
    result = validate(
        Path(args.review),
        Path(args.publication),
        Path(args.kell),
        Path(args.charts_dir),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
