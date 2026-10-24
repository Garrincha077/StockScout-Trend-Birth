#!/usr/bin/env python3
"""Compact, permanent as-of-EOD close prices for every evaluated Trend Birth ticker.

This reuses existing immutable Review snapshot archives and only reads sessions
not already represented in small monthly close shards. No price API or scanning.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from trend_birth_intelligence import SCOPE, all_points, load_months, write_json

SCHEMA = "trend-birth-close-month-v1"


def extract(snapshot: dict, point: dict) -> dict:
    source = snapshot.get("source") or {}
    day = point["sessionDate"]
    if source.get("sessionDate") != day or source.get("runId") != point["runId"]:
        raise ValueError("EOD price and stage provenance mismatch: " + day)
    rows = snapshot.get("trendBirthCandidateIndex")
    if not isinstance(rows, list):
        raise ValueError("Missing point-in-time full-universe price index: " + day)
    prices: dict[str, float] = {}
    seen: set[str] = set()
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker or ticker in seen:
            raise ValueError("Duplicate or missing price ticker on " + day)
        seen.add(ticker)
        if ticker not in point["stages"]:
            continue  # never invent prices for unavailable technical setups
        value = (row.get("metrics") or {}).get("price")
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(price) and price > 0:
            prices[ticker] = round(price, 6)
    if seen != set(point["stages"]) | set(point["unavailable"]):
        raise ValueError("Price universe does not match archived stages: " + day)
    return {
        "sessionDate": day, "runId": point["runId"],
        "expectedEvaluated": point["evaluatedCount"],
        "priceCount": len(prices), "prices": dict(sorted(prices.items())),
    }


def load_prices(directory: Path) -> dict[str, dict]:
    sessions: dict[str, dict] = {}
    for path in sorted(directory.glob("????-??.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("schemaVersion") != SCHEMA or doc.get("scope") != SCOPE or doc.get("month") != path.stem:
            raise ValueError("Unexpected EOD close archive schema: " + path.name)
        for item in doc.get("sessions") or []:
            day = item.get("sessionDate")
            if not isinstance(day, str) or day[:7] != path.stem or day in sessions:
                raise ValueError("Duplicate/misdated EOD close archive: " + str(day))
            prices = item.get("prices")
            if not isinstance(prices, dict) or len(prices) != item.get("priceCount"):
                raise ValueError("Malformed close archive: " + day)
            sessions[day] = item
    return sessions


def build(latest_path: Path, history_dir: Path, stages_dir: Path,
          prices_dir: Path) -> dict:
    points = all_points(load_months(stages_dir))
    if not points:
        raise ValueError("Cannot archive closes without immutable stage dates")
    archived = load_prices(prices_dir)
    known = {p["sessionDate"] for p in points}
    if set(archived) - known:
        raise ValueError("Price archive contains a day outside the stage history")
    current = json.loads(latest_path.read_text(encoding="utf-8"))
    latest_day = str((current.get("source") or {}).get("sessionDate"))
    if points[-1]["sessionDate"] != latest_day:
        raise ValueError("Latest stage and quote day mismatch")
    for point in points:
        day = point["sessionDate"]
        if day in archived:
            if archived[day].get("runId") != point["runId"] or archived[day]["expectedEvaluated"] != point["evaluatedCount"]:
                raise ValueError("Conflicting immutable EOD close snapshot: " + day)
            continue
        if day == latest_day:
            snapshot = current
        else:
            source = history_dir / (day + ".json")
            if not source.is_file():
                raise ValueError("Source EOD snapshot missing: " + str(source))
            snapshot = json.loads(source.read_text(encoding="utf-8"))
        archived[day] = extract(snapshot, point)
    grouped: dict[str, list[dict]] = {}
    for day in sorted(archived):
        grouped.setdefault(day[:7], []).append(archived[day])
    for month, sessions in grouped.items():
        write_json(prices_dir / (month + ".json"), {
            "schemaVersion": SCHEMA, "scope": SCOPE,
            "month": month, "sessions": sessions,
        })
    return {
        "sessions": len(archived),
        "last": latest_day,
        "latestPriceCoveragePct": round(
            100 * archived[latest_day]["priceCount"] /
            archived[latest_day]["expectedEvaluated"], 2
        ),
        "latestPrices": archived[latest_day]["priceCount"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", type=Path, required=True)
    parser.add_argument("--history-dir", type=Path, required=True)
    parser.add_argument("--stages-dir", type=Path, required=True)
    parser.add_argument("--prices-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.latest, args.history_dir,
                           args.stages_dir, args.prices_dir)))


if __name__ == "__main__":
    main()
