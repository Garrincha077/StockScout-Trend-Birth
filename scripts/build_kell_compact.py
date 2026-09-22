#!/usr/bin/env python3
"""Build a compact browser payload for Kell full-Unified filters.

The full lab snapshot intentionally carries chart history and detailed score evidence
for reproducibility. The Vercel preview only needs filter membership, a small metrics
summary and Kell score/stage metadata to render the full candidate lists.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

METRIC_KEYS = (
    "price", "rvol", "rsi14", "emaGapPct", "slope50", "slope30w",
    "swingState", "baseLike", "setup", "actionability",
)
KELL_METRIC_KEYS = (
    "ret_3m_pct", "ret_6m_pct", "ret_ytd_pct", "gap_pct", "rvol20",
    "beta", "beta_source", "revenue_yoy_pct", "eps_yoy_pct", "rs_rank", "weekly_ema10",
    "breakout_proximity_pct",
)

def pick(source: dict, keys: tuple[str, ...]) -> dict:
    return {key: source.get(key) for key in keys if key in source}

def compact_candidate(item: dict) -> dict:
    return {
        "ticker": item.get("ticker"),
        "sources": list(item.get("sources") or []),
        "metrics": pick(item.get("metrics") or {}, METRIC_KEYS),
        "kell_metrics": pick(item.get("kell_metrics") or {}, KELL_METRIC_KEYS),
        "kell_score": item.get("kell_score"),
        "kell_cycle_stage": item.get("kell_cycle_stage"),
        "kell_breakout_proximity_pct": item.get("kell_breakout_proximity_pct"),
        "kellScreens": list(item.get("kellScreens") or []),
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    src = source.get("source") or {}
    out = {
        "schemaVersion": "kell-compact-v1",
        "source": {
            "runId": src.get("runId"),
            "sessionDate": src.get("sessionDate"),
            "readOnly": True,
        },
        "kellScoring": source.get("kellScoring") or {},
        "kellCandidateCount": source.get("kellCandidateCount", 0),
        "kellCandidates": [
            compact_candidate(item)
            for item in (source.get("kellCandidates") or [])
        ],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "ok",
        "sessionDate": out["source"]["sessionDate"],
        "kellCandidates": len(out["kellCandidates"]),
        "bytes": output.stat().st_size,
    }))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
