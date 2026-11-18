"""Retrospective early-model replay against archived daily and weekly membership."""

import argparse
from bisect import bisect_right
from collections import Counter
import hashlib
import json
from pathlib import Path

from build_review_snapshot import _embedded_spy_benchmark
from early_trend_birth import HISTORY, MODEL, SHORTLIST_SIZE, evaluate, priority
from early_trend_outcomes import report
from market_actions import read_actions
from market_sessions import bar_session_date, exchange_sessions, session_date
from trend_birth_stage_forward import _price_series
from weekly_birth import LABELS


def archives(directory, group):
    return {
        point["sessionDate"]: point
        for path in sorted(directory.glob(f"{group}_????-??.json"))
        for point in json.loads(path.read_bytes())["sessions"]
    }


def chart_history(snapshot):
    charts = {}
    for group in ("kellCandidates", "candidates"):
        for row in snapshot[group]:
            bars = row.get("chartBars") or []
            if len(bars) > len(charts.get(row["ticker"], [])):
                charts[row["ticker"]] = bars
    benchmark = {
        session_date(bar["time"]): bar["close"] for bar in _embedded_spy_benchmark(charts)
    }
    dated = {}
    for ticker, rows in charts.items():
        days = [bar_session_date(bar) for bar in rows]
        if all(days) and all(a < b for a, b in zip(days, days[1:])):
            dated[ticker] = days, rows
    if not benchmark or not dated:
        raise ValueError("No replayable charts or embedded SPY")
    return dated, benchmark


def replay(snapshot, archive_dir, actions):
    history, benchmark = chart_history(snapshot)
    stage_points = archives(archive_dir, "trend-birth-ticker-history")
    price_archive = archives(archive_dir, "trend-birth-price-history")
    points = []
    membership = Counter()
    coverage_by_day = {}
    stages_by_label = {label: stage for stage, label in LABELS.items()}
    for filename in sorted(archive_dir.glob("weekly-birth-shadow_????-??-??.json")):
        weekly = json.loads(filename.read_bytes())
        day = weekly["sessionDate"]
        old = stage_points[day]
        if old["runId"] != weekly["runId"]:
            raise ValueError("Archived weekly and daily attempts differ on " + day)
        selected = {item["ticker"]: item for item in weekly["selected"]}
        available, candidates = {}, []
        for ticker, stages in old["stages"].items():
            if ticker not in history:
                continue
            days, rows = history[ticker]
            end = bisect_right(days, day)
            if end <= HISTORY or days[end - 1] != day:
                continue
            available[ticker] = stages
            weekly_item = selected.get(ticker, {})
            weekly_stage = stages_by_label.get(weekly_item.get("stage"))
            found = evaluate(rows[end - HISTORY - 1:end], day, benchmark, stages[0], {"stage": weekly_stage})
            if found:
                candidates.append({"ticker": ticker, "earlyTrend": found})
        top = sorted(candidates, key=priority)[:SHORTLIST_SIZE]
        weekly_kept = sorted(set(selected) & available.keys())
        membership["qualifiedCandidateDays"] += len(candidates)
        membership["archivedEligibleTickerDays"] += len(old["stages"])
        membership["replayedEligibleTickerDays"] += len(available)
        membership["archivedWeeklyTickerDays"] += len(selected)
        membership["replayedWeeklyTickerDays"] += len(weekly_kept)
        coverage_by_day[day] = {"eligible": len(old["stages"]), "replayed": len(available), "qualified": len(candidates)}
        points.append({"sessionDate": day, "stages": available, "earlyTrend": {
            "model": MODEL, "shortlist": [item["ticker"] for item in top], "weekly": weekly_kept,
        }})
    as_of = snapshot["source"]["sessionDate"]
    if len(points) < 2 or not price_archive or points[-1]["sessionDate"] > as_of:
        raise ValueError("Insufficient or misdated point-in-time archives")
    calendar = exchange_sessions(as_of)
    results = report(points, _price_series(price_archive), calendar, actions)
    return {
        **results, "from": points[0]["sessionDate"], "asOf": as_of,
        "coverage": dict(membership), "coverageByDay": coverage_by_day,
        "limits": "Retrospective signal reconstruction from charts preserved at the final snapshot. "
                  "Archive membership is dated, but chart coverage, revisions and split adjustments can "
                  "introduce selection bias. This common subset is unsuitable for claims of forward performance.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--actions", type=Path, default=Path("scripts/data/review-market-actions-v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    raw = options.snapshot.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != options.sha256.lower():
        raise ValueError("Unexpected pinned Review snapshot hash")
    ledger, action_hash = read_actions(options.actions)
    result = replay(json.loads(raw), options.archive_dir, ledger)
    result.update(snapshotSha256=digest, actionsSha256=action_hash)
    options.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
