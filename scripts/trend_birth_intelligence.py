#!/usr/bin/env python3
"""Permanent, point-in-time ticker-stage archives and compact daily intelligence.

No new scanner, credential, database or scheduled job. Stage history is sharded by
calendar month and must reconcile with the existing full-universe EOD radar.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

SCHEMA = "trend-birth-ticker-month-v1"
SUMMARY_SCHEMA = "trend-birth-intelligence-v1"
RADAR_SCHEMA = "trend-birth-radar-v1"
SCOPE = "unified-plus-tracked-watchlist"
CHECK_KEYS = (
    "sma50Rising", "sma30wRising", "structureValid", "notExtended",
    "recentPullbackCompression", "ema10Rising", "ema20NonFalling",
    "ema10AboveEma20", "closeAboveShortEmas", "bullishReexpansion",
)
CHECK_LABELS = (
    "SMA50 raste", "30W SMA raste", "Struktura potvrđena", "Nije produžena",
    "Kompresija nakon povlačenja", "EMA10 raste", "EMA20 nije silazna",
    "EMA10 iznad EMA20", "Cijena iznad EMA10/20", "Bullish re-expansion",
)


def _day(value: object) -> str:
    if not isinstance(value, str) or dt.date.fromisoformat(value).isoformat() != value:
        raise ValueError("Invalid EOD sessionDate")
    return value


def _point_counts(point: dict) -> dict[str, int]:
    counts = {str(i): 0 for i in range(5)}
    for ticker, value in point["stages"].items():
        if not isinstance(ticker, str) or not ticker or ticker != ticker.upper():
            raise ValueError("Invalid stage ticker")
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("Invalid stage/check tuple: " + ticker)
        stage, mask = value
        if type(stage) is not int or stage not in range(5):
            raise ValueError("Invalid stage: " + ticker)
        if type(mask) is not int or not 0 <= mask < (1 << len(CHECK_KEYS)):
            raise ValueError("Invalid check mask: " + ticker)
        counts[str(stage)] += 1
    if len(set(point["unavailable"])) != len(point["unavailable"]):
        raise ValueError("Duplicated unavailable ticker")
    if any(ticker in point["stages"] for ticker in point["unavailable"]):
        raise ValueError("Ticker present as evaluated and unavailable")
    if any(not isinstance(ticker, str) or not ticker or ticker != ticker.upper()
           for ticker in point["unavailable"]):
        raise ValueError("Invalid unavailable ticker")
    if counts != point["counts"] or sum(counts.values()) != point["evaluatedCount"]:
        raise ValueError("Ticker stages do not reconcile with daily radar")
    if len(point["unavailable"]) != point["unavailableCount"]:
        raise ValueError("Unavailable ticker count does not reconcile")
    return counts


def point_from_snapshot(snapshot: dict) -> dict | None:
    radar = snapshot.get("trendBirthRadar") or {}
    if radar.get("schemaVersion") != RADAR_SCHEMA:
        return None  # No invented pre-radar history.
    source = snapshot.get("source") or {}
    day = _day(source.get("sessionDate"))
    run_id = str(source.get("runId") or "")
    if not run_id or radar.get("scope") != SCOPE:
        raise ValueError("Missing run ID or incompatible Trend Birth universe")
    rows = snapshot.get("trendBirthCandidateIndex")
    if not isinstance(rows, list):
        raise ValueError("Full-universe ticker index missing for " + day)
    stages: dict[str, list[int]] = {}
    unavailable: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid index row for " + day)
        ticker = str(row.get("ticker") or "").upper()
        if not ticker or ticker in stages or ticker in unavailable:
            raise ValueError("Empty or duplicate ticker: " + ticker)
        tb = row.get("trendBirth") or {}
        if tb.get("available") is True:
            stage = tb.get("stage")
            if type(stage) is not int or stage not in range(5):
                raise ValueError("Invalid Trend Birth stage: " + ticker)
            checks = tb.get("checks") or {}
            if not isinstance(checks, dict):
                raise ValueError("Invalid checklist for " + ticker)
            mask = sum((1 << idx) for idx, key in enumerate(CHECK_KEYS) if checks.get(key) is True)
            stages[ticker] = [stage, mask]
        elif tb.get("available") is False:
            unavailable.append(ticker)
        else:
            raise ValueError("Missing Trend Birth availability for " + ticker)
    radar_counts = radar.get("stageCounts") or {}
    if not isinstance(radar_counts, dict) or set(radar_counts) != {str(i) for i in range(5)}:
        raise ValueError("Missing radar stage counts")
    if any(type(value) is not int or value < 0 for value in radar_counts.values()):
        raise ValueError("Invalid radar stage count")
    point = {
        "sessionDate": day,
        "runId": run_id,
        "counts": {str(i): radar_counts[str(i)] for i in range(5)},
        "evaluatedCount": radar.get("evaluatedCount"),
        "unavailableCount": radar.get("unavailableCount"),
        "stages": dict(sorted(stages.items())),
        "unavailable": sorted(unavailable),
    }
    _point_counts(point)
    return point


def load_months(directory: Path) -> dict[str, dict]:
    months: dict[str, dict] = {}
    for path in sorted(directory.glob("????-??.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schemaVersion") != SCHEMA or data.get("scope") != SCOPE:
            raise ValueError("Invalid retained ticker-history schema: " + path.name)
        month = data.get("month")
        if month != path.stem or not isinstance(data.get("sessions"), list):
            raise ValueError("Invalid ticker-history month: " + path.name)
        seen: set[str] = set()
        for point in data["sessions"]:
            day = _day(point.get("sessionDate"))
            if day[:7] != month or day in seen or not point.get("runId"):
                raise ValueError("Invalid/duplicate ticker-history session: " + day)
            seen.add(day)
            _point_counts(point)
        months[month] = data
    return months


def merge_point(months: dict[str, dict], point: dict) -> None:
    month = point["sessionDate"][:7]
    payload = months.setdefault(month, {
        "schemaVersion": SCHEMA, "scope": SCOPE, "month": month, "sessions": [],
    })
    for old in payload["sessions"]:
        if old["sessionDate"] == point["sessionDate"]:
            if old != point:
                raise ValueError("Conflicting historical ticker stages for " + point["sessionDate"])
            return
    payload["sessions"].append(point)
    payload["sessions"].sort(key=lambda value: value["sessionDate"])


def all_points(months: dict[str, dict]) -> list[dict]:
    return sorted(
        (point for payload in months.values() for point in payload["sessions"]),
        key=lambda value: value["sessionDate"],
    )


def _new_checks(before: list[int] | None, after: list[int]) -> list[str]:
    if before is None:
        return []
    bits = after[1] & ~before[1]
    return [label for idx, label in enumerate(CHECK_LABELS) if bits & (1 << idx)]



def calculate_stability(points: list[dict]) -> tuple[dict, dict[str, tuple[int, int]]]:
    """Compute observed-EOD streaks and mature, paired-session retention.

    A missing, unavailable or out-of-universe ticker breaks its streak.
    Only tickers evaluated at both endpoints enter a retention denominator.
    """
    if not points:
        raise ValueError("Cannot calculate stability without EOD sessions")
    quality_streaks: dict[str, int] = {}
    four_streaks: dict[str, int] = {}
    quality_kept = quality_eligible = four_kept = four_eligible = 0
    latest_quality_dropout = latest_four_dropout = 0
    prior = None
    for point in points:
        stages = point["stages"]
        next_quality = {
            ticker: quality_streaks.get(ticker, 0) + 1
            for ticker, value in stages.items() if value[0] >= 3
        }
        next_four = {
            ticker: four_streaks.get(ticker, 0) + 1
            for ticker, value in stages.items() if value[0] == 4
        }
        if prior is not None:
            common = prior["stages"].keys() & stages.keys()
            q_from = [ticker for ticker in common if prior["stages"][ticker][0] >= 3]
            f_from = [ticker for ticker in common if prior["stages"][ticker][0] == 4]
            quality_eligible += len(q_from)
            four_eligible += len(f_from)
            quality_kept += sum(stages[ticker][0] >= 3 for ticker in q_from)
            four_kept += sum(stages[ticker][0] == 4 for ticker in f_from)
            latest_quality_dropout = sum(stages[ticker][0] < 3 for ticker in q_from)
            latest_four_dropout = sum(stages[ticker][0] < 4 for ticker in f_from)
        quality_streaks, four_streaks = next_quality, next_four
        prior = point

    def rate(kept: int, eligible: int) -> dict:
        return {"kept": kept, "eligible": eligible,
                "percent": round(100 * kept / eligible, 1) if eligible else None}

    return ({
        "observedSessions": len(points),
        "transitionPairs": max(0, len(points) - 1),
        "quality": {
            "current": len(quality_streaks),
            "atLeast3": sum(value >= 3 for value in quality_streaks.values()),
            "atLeast5": sum(value >= 5 for value in quality_streaks.values()),
            "oneSession": sum(value == 1 for value in quality_streaks.values()),
            "latestDropouts": latest_quality_dropout if len(points) > 1 else None,
            "retention": rate(quality_kept, quality_eligible),
        },
        "four": {
            "current": len(four_streaks),
            "atLeast3": sum(value >= 3 for value in four_streaks.values()),
            "atLeast5": sum(value >= 5 for value in four_streaks.values()),
            "oneSession": sum(value == 1 for value in four_streaks.values()),
            "latestDropouts": latest_four_dropout if len(points) > 1 else None,
            "retention": rate(four_kept, four_eligible),
        },
    }, {
        ticker: (quality_streaks.get(ticker, 0), four_streaks.get(ticker, 0))
        for ticker in points[-1]["stages"]
    })


def build_summary(current: dict, points: list[dict]) -> dict:
    date = _day((current.get("source") or {}).get("sessionDate"))
    today = next((point for point in reversed(points) if point["sessionDate"] == date), None)
    if today is None:
        raise ValueError("Latest EOD missing from permanent ticker history")
    verify = point_from_snapshot(current)
    if verify != today or points[-1] != today:
        raise ValueError("Latest snapshot differs from newest ticker-stage archive")
    prior = next((point for point in reversed(points) if point["sessionDate"] < date), None)
    stability, streaks = calculate_stability(points)
    old = prior["stages"] if prior else {}
    new = today["stages"]
    common = sorted(set(old) & set(new))
    upgrades = [ticker for ticker in common if new[ticker][0] > old[ticker][0]]
    downgrades = [ticker for ticker in common if new[ticker][0] < old[ticker][0]]
    new_four = [ticker for ticker in upgrades if new[ticker][0] == 4]
    to_ready = [ticker for ticker in upgrades if new[ticker][0] == 3]
    stable_four = [ticker for ticker in common if old[ticker][0] == new[ticker][0] == 4]
    today_index = {
        str(item.get("ticker") or "").upper(): item
        for item in current.get("trendBirthCandidateIndex") or []
    }

    def row(ticker: str) -> dict:
        item = today_index.get(ticker) or {}
        value = new[ticker]
        before = old.get(ticker)
        trend_birth = item.get("trendBirth") or {}
        weekly = ((item.get("weeklyBirth") or {}).get("metrics") or {})
        return {
            "ticker": ticker, "stage": value[0], "previousStage": before[0] if before else None,
            "qualityStreak": streaks[ticker][0], "fourStreak": streaks[ticker][1],
            "newChecks": _new_checks(before, value),
            "missingFor4": list(trend_birth.get("missingFor4") or [])[:4],
            "tracked": item.get("trackedWatchlist") is True,
            "baseWeeks": weekly.get("baseWeeks"),
            "runwayPct": weekly.get("runwayPct"),
            "readiness": item.get("kell_readiness_score"),
            "kellScore": item.get("kell_score"),
        }

    def order(ticker: str) -> tuple:
        item = today_index.get(ticker) or {}
        return (-float(item.get("kell_readiness_score") or 0),
                -float(item.get("kell_score") or 0), ticker)

    new_four.sort(key=order)
    to_ready.sort(key=order)
    stable_four.sort(key=order)
    upgrades.sort(key=lambda ticker: (-new[ticker][0], *order(ticker)))
    downgrades.sort(key=lambda ticker: (new[ticker][0], ticker))
    candidate_order = [*new_four, *to_ready,
                       *[ticker for ticker in upgrades if new[ticker][0] == 2],
                       *stable_four]
    featured = list(dict.fromkeys(candidate_order))[:10]
    return {
        "schemaVersion": SUMMARY_SCHEMA,
        "source": {"sessionDate": date, "runId": today["runId"], "scope": SCOPE,
                   "previousSessionDate": prior["sessionDate"] if prior else None},
        "baselineOnly": prior is None,
        "counts": today["counts"],
        "evaluatedCount": today["evaluatedCount"],
        "unavailableCount": today["unavailableCount"],
        "commonEvaluated": len(common),
        "newCoverage": len(set(new) - set(old)) if prior else None,
        "lostCoverage": len(set(old) - set(new)) if prior else None,
        "upgrades": len(upgrades), "downgrades": len(downgrades),
        "netImprovement": len(upgrades) - len(downgrades),
        "newFour": len(new_four), "toReady": len(to_ready),
        "stableFour": len(stable_four),
        "stability": stability,
        "topOpportunities": [row(ticker) for ticker in featured],
        "newFourTickers": new_four,
        "readyTickers": to_ready,
        "downgradeTickers": downgrades,
    }


def write_json(path: Path, data: dict) -> None:
    content = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build(latest_path: Path, history_dir: Path, month_dir: Path, summary_path: Path) -> dict:
    current = json.loads(latest_path.read_text(encoding="utf-8"))
    latest = point_from_snapshot(current)
    if latest is None:
        raise ValueError("Latest EOD has no full Trend Birth radar")
    months = load_months(month_dir)
    retained_days = {p["sessionDate"] for p in all_points(months)}
    merge_point(months, latest)
    retained_days.add(latest["sessionDate"])
    for path in sorted(history_dir.glob("????-??-??.json")):
        if path.stem > latest["sessionDate"] or path.stem in retained_days:
            continue  # Reuse durable compact points, avoid rereading multi-GB archives daily.
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue  # Legacy snapshots preceding the radar contract.
        point = point_from_snapshot(snapshot)
        if point is None:
            continue
        if point["sessionDate"] != path.stem:
            raise ValueError("Misdated raw archive: " + path.name)
        merge_point(months, point)
        retained_days.add(point["sessionDate"])
    points = all_points(months)
    summary = build_summary(current, points)
    for month, payload in months.items():
        write_json(month_dir / (month + ".json"), payload)
    write_json(summary_path, summary)
    return {"sessions": len(points), "months": len(months),
            "latest": latest["sessionDate"], "newFour": summary["newFour"],
            "netImprovement": summary["netImprovement"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", type=Path, required=True)
    parser.add_argument("--history-dir", type=Path, required=True)
    parser.add_argument("--month-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.latest, args.history_dir, args.month_dir, args.summary)))


if __name__ == "__main__":
    main()
