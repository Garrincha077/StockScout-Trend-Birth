#!/usr/bin/env python3
"""Archive one inspectable, no-send Weekly Birth shadow report per session."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def build_report(snapshot: dict, previous: dict | None = None) -> dict:
    source = snapshot.get("source") or {}
    shortlist = snapshot.get("shortlists") or {}
    if shortlist.get("schemaVersion") != "stockscout-shortlists-v2":
        raise ValueError("Weekly Birth v2 shortlist is unavailable")
    universe = snapshot.get("trendBirthCandidateIndex") or []
    selected = shortlist.get("weeklyTrendBirth") or []
    if len(selected) > 15:
        raise ValueError("Weekly Birth shortlist exceeds 15")
    members = {str(item.get("ticker") or "") for item in selected}
    if not members or "" in members:
        members.discard("")
    old_members = {str(item.get("ticker") or "") for item in (previous or {}).get("selected", [])}
    stages = Counter((item.get("weeklyBirth") or {}).get("stageLabel") or "Unknown" for item in selected)
    reasons = Counter(
        reason
        for item in universe
        for reason in (item.get("weeklyBirth") or {}).get("rejectReasons") or []
    )
    detail = []
    for item in selected:
        evidence = item.get("weeklyBirth") or {}
        metrics = evidence.get("metrics") or {}
        detail.append({
            "ticker": item["ticker"],
            "stage": evidence.get("stageLabel"),
            "score": evidence.get("score"),
            "baseWeeks": metrics.get("baseWeeks"),
            "baseDepthPct": metrics.get("baseDepthPct"),
            "weeklyMaClusterPct": metrics.get("weeklyMaClusterPct"),
            "recentBaseRangePct26w": metrics.get("recentBaseRangePct26w"),
            "recentBaseRangePct12w": metrics.get("recentBaseRangePct12w"),
            "runwayPct": metrics.get("runwayPct"),
            "extensionPct": metrics.get("extensionPct"),
            "mansfieldRsPct": metrics.get("mansfieldRsPct"),
            "mansfieldRsChangePct4w": metrics.get("mansfieldRsChangePct4w"),
            "breakoutVolumeRatio4w": metrics.get("breakoutVolumeRatio4w"),
            "maSlope30wPct4w": metrics.get("maSlope30wPct4w"),
            "maPriorSlope30wPct4w": metrics.get("maPriorSlope30wPct4w"),
            "blueSkyConfirmed": metrics.get("blueSkyConfirmed"),
        })
    return {
        "schemaVersion": "weekly-birth-shadow-audit-v1",
        "modelVersion": ((selected[0].get("weeklyBirth") or {}).get("modelVersion") if selected else "weinstein-stage2a-v3"),
        "sessionDate": source.get("sessionDate"),
        "runId": source.get("runId"),
        "unifiedManifestSha256": source.get("unifiedManifestSha256"),
        "evaluatedCount": len(universe),
        "eligibleCount": sum((item.get("weeklyBirth") or {}).get("eligible") is True for item in universe),
        "selectedCount": len(selected),
        "stageCounts": dict(sorted(stages.items())),
        "rejectionReasonCounts": dict(sorted(reasons.items())),
        "added": sorted(members - old_members) if previous else [],
        "removed": sorted(old_members - members) if previous else [],
        "previousSessionDate": (previous or {}).get("sessionDate"),
        "selected": detail,
        "manualChartReviewComplete": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--history-dir", required=True)
    args = parser.parse_args()
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    session = str((snapshot.get("source") or {}).get("sessionDate") or "")
    if not session:
        raise ValueError("Snapshot sessionDate is required")
    directory = Path(args.history_dir)
    earlier = sorted((path for path in directory.glob("*.json") if path.stem < session), reverse=True)
    previous = json.loads(earlier[0].read_text(encoding="utf-8")) if earlier else None
    report = build_report(snapshot, previous)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{session}.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sessionDate": session, "selected": report["selectedCount"], "eligible": report["eligibleCount"], "added": len(report["added"]), "removed": len(report["removed"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
