#!/usr/bin/env python3
"""Summarize comparable baseline, initial-v6 and tuned-v6 Unified audits."""
from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from pathlib import Path

EVENTS = ("kell_wedge_pop", "kell_ema_crossback", "kell_base_n_break", "kell_wedge_drop")


def sessions(pattern: str) -> tuple[dict[str, dict], set[str], set[str]]:
    result = {}
    source_hashes = set()
    baselines = set()
    for path in glob.glob(pattern):
        report = json.loads(Path(path).read_text(encoding="utf-8"))
        source_hashes.add(report.get("candidateSourceSha256") or report.get("v6Commit"))
        baselines.add(report.get("v5Commit"))
        for session in report["sessions"]:
            date = session["sessionDate"]
            if date in result:
                raise ValueError(f"Duplicate session {date}")
            result[date] = session
    if len(source_hashes) != 1:
        raise ValueError("Audits used different model sources")
    if len(baselines) != 1:
        raise ValueError("Audits used different v5 baselines")
    return result, source_hashes, baselines


def summarize(initial: dict[str, dict], tuned: dict[str, dict]) -> dict:
    if initial.keys() != tuned.keys():
        raise ValueError("Session sets differ")
    rows = []
    crossback_ages = Counter()
    for date in sorted(initial):
        before, after = initial[date], tuned[date]
        for key in ("runId", "manifestSha256", "candidateCount", "chartCoverageCount", "benchmarkBars"):
            if before[key] != after[key]:
                raise ValueError(f"{date}: {key} changed between replays")
        if before["eventCounts"]["v5"] != after["eventCounts"]["v5"]:
            raise ValueError(f"{date}: v5 baseline changed")
        crossback_ages.update(before["v5CrossbackPopAges"])
        rows.append({
            "sessionDate": date,
            "runId": before["runId"],
            "manifestSha256": before["manifestSha256"],
            "candidateCount": before["candidateCount"],
            "chartCoverageCount": before["chartCoverageCount"],
            "benchmarkBars": before["benchmarkBars"],
            "events": {
                key: {
                    "v5": before["eventCounts"]["v5"].get(key, 0),
                    "initialV6": before["eventCounts"]["v6"].get(key, 0),
                    "tunedV6": after["eventCounts"]["v6"].get(key, 0),
                }
                for key in EVENTS
            },
            "focus": {"v5": before["focus"]["v5"],
                      "initialV6": before["focus"]["v6"],
                      "tunedV6": after["focus"]["v6"]},
            "stageOrFocusChanged": {"initialV6": before["stageOrFocusChanged"],
                                    "tunedV6": after["stageOrFocusChanged"]},
        })
    totals = {
        "candidateSessions": sum(row["candidateCount"] for row in rows),
        "events": {
            key: {version: sum(row["events"][key][version] for row in rows)
                  for version in ("v5", "initialV6", "tunedV6")}
            for key in EVENTS
        },
        "focus": {version: sum(row["focus"][version] for row in rows)
                  for version in ("v5", "initialV6", "tunedV6")},
        "v5CrossbackPopAges": dict(sorted(crossback_ages.items(), key=lambda item: int(item[0]))),
    }
    return {"method": "Exact-session StockScout Unified Pages artifacts; identical inputs for v5, initial v6 and tuned v6; counts are candidate-sessions, not unique symbols or returns",
            "sessions": rows, "totals": totals}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial", required=True, help="Glob of initial-v6 audit JSON files")
    parser.add_argument("--tuned", required=True, help="Glob of tuned-v6 audit JSON files")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    initial, initial_sources, initial_baselines = sessions(args.initial)
    tuned, tuned_sources, tuned_baselines = sessions(args.tuned)
    if initial_baselines != tuned_baselines:
        raise ValueError("v5 baseline differs between replay groups")
    result = summarize(initial, tuned)
    result["v5Commit"] = next(iter(initial_baselines))
    result["initialV6Source"] = next(iter(initial_sources))
    result["tunedV6SourceSha256"] = next(iter(tuned_sources))
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
