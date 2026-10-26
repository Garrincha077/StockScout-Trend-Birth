"""Compare Weekly definitions on a pinned existing snapshot; never rescan or publish.

Example:
 git show 168fc51:scripts/weekly_birth.py > /tmp/weekly-before.py
 python scripts/audit_weekly_review.py --snapshot /tmp/latest.json \
   --before /tmp/weekly-before.py --source-commit 168fc51 --output /tmp/weekly-diff.json

Only rows retained in that snapshot are replayed. Coverage and archived/replay
agreement are explicit; this is a definition-change audit, not a return backtest.
"""
import argparse
import importlib.util
import json
from pathlib import Path

from weekly_birth import evaluate_weekly_birth, weekly_shortlist


def compare(snapshot, before):
    rows = {}
    lists = snapshot.get("shortlists") or {}
    for group in (snapshot.get("kellCandidates", []), snapshot.get("candidates", []),
                  snapshot.get("trendBirthCandidateIndex", []), lists.get("weeklyTrendBirth", [])):
        for item in group:
            bars = item.get("weeklyChartBars") or item.get("chartBars") or []
            ticker = item["ticker"]
            if bars and (ticker not in rows or len(bars) > len(rows[ticker])):
                rows[ticker] = bars
    changes, old_rows, new_rows = [], [], []
    matches = 0
    for item in snapshot["trendBirthCandidateIndex"]:
        bars = rows.get(item["ticker"])
        if not bars:
            continue
        old = before(bars)
        new = evaluate_weekly_birth(bars)
        keys = ("score", "stage", "eligible")
        equal = all(old.get(k) == item["weeklyBirth"].get(k) for k in keys)
        matches += equal
        old_rows.append({"ticker": item["ticker"], "weeklyBirth": old})
        new_rows.append({"ticker": item["ticker"], "weeklyBirth": new})
        resistance_old = old.get("metrics", {}).get("resistancePrice")
        resistance_new = new.get("metrics", {}).get("resistancePrice")
        if any(old.get(k) != new.get(k) for k in keys) or resistance_old != resistance_new:
            changes.append({"ticker": item["ticker"], "archivedReplayMatches": equal,
                            "before": {k: old.get(k) for k in keys}, "after": {k: new.get(k) for k in keys},
                            "resistanceBefore": resistance_old, "resistanceAfter": resistance_new})
    return {"asOf": snapshot["source"]["sessionDate"], "rowsAvailable": len(rows),
            "archivedReplayMatches": matches, "universe": len(snapshot["trendBirthCandidateIndex"]),
            "baselinePublishedShortlist": [x["ticker"] for x in lists["weeklyTrendBirth"]],
            "replayedBefore": [x["ticker"] for x in weekly_shortlist(old_rows)],
            "replayedAfter": [x["ticker"] for x in weekly_shortlist(new_rows)],
            "changedCount": len(changes), "changes": changes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "before", "output", "source-commit"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("weekly_before", args.before)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = compare(json.loads(Path(args.snapshot).read_bytes()), module.evaluate_weekly_birth)
    result["sourceCommit"] = args.source_commit
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "changes"}))


if __name__ == "__main__":
    main()
