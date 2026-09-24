#!/usr/bin/env python3
"""Archive a small point-in-time Kell score snapshot for future validation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def compact_candidate(item: dict) -> dict:
    breakdown = item.get("score_breakdown") or {}
    readiness = (breakdown.get("components") or {}).get("readiness") or {}
    kell_stage = item.get("kell_stage") or {}
    return {
        "ticker": item.get("ticker"),
        "sources": list(item.get("unifiedSources") or item.get("sources") or []),
        "kell_score": item.get("kell_score"),
        "legacy_v4_score": breakdown.get("legacy_v4_score"),
        "kell_quality_score": item.get("kell_quality_score"),
        "kell_readiness_score": item.get("kell_readiness_score"),
        "kell_context_score": item.get("kell_context_score"),
        "kell_evidence_coverage": item.get("kell_evidence_coverage"),
        "kell_stage_cap": item.get("kell_stage_cap"),
        "stage": kell_stage.get("primary") or item.get("kell_cycle_stage"),
        "stage_basis": list(kell_stage.get("basis") or []),
        "structural_risk_atr": readiness.get("structural_risk_atr"),
        "screens": list(item.get("kellScreens") or item.get("kell_screens") or []),
        "setups": list(item.get("kellSetups") or item.get("kell_setups") or []),
        "context": list(item.get("kellContext") or item.get("kell_context") or []),
    }


def build_archive(payload: dict) -> dict:
    source = payload.get("source") or {}
    rows = list(payload.get("kellCandidates") or payload.get("candidates") or [])
    return {
        "schemaVersion": "kell-score-history-v1",
        "source": {
            "sessionDate": source.get("sessionDate"),
            "runId": source.get("runId"),
        },
        "kellScoring": {
            "modelVersion": (payload.get("kellScoring") or {}).get("modelVersion"),
        },
        "candidateCount": len(rows),
        "candidates": [compact_candidate(item) for item in rows],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", default="lab/data/kell-score-history")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    archive = build_archive(payload)
    session_date = str((archive.get("source") or {}).get("sessionDate") or "")
    if not session_date:
        raise ValueError("sessionDate missing")
    output = Path(args.output_dir) / f"{session_date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(archive, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"status": "ok", "sessionDate": session_date, "candidates": archive["candidateCount"], "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
