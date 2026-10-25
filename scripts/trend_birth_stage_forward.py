#!/usr/bin/env python3
"""Point-in-time stage-entry outcomes (5/20/60 trading days), using existing EOD charts.

No second scan: archive immutable stage transitions; mature returns only after
the next close entry and the full hold period. Keep successes in small monthly
event shards so expiry of the rolling chart history cannot erase observations.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
from statistics import median

from trend_birth_intelligence import SCOPE, all_points, load_months, write_json
from archive_trend_birth_closes import load_prices

SCHEMA = "trend-birth-forward-eod-month-v2"
REPORT_SCHEMA = "trend-birth-stage-forward-v2"
HORIZONS = (5, 20, 60)


def _date_from_stamp(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        numeric = float(text)
        if math.isfinite(numeric) and numeric > 0:
            seconds = numeric / 1000 if numeric >= 1e12 else numeric
            return datetime.fromtimestamp(seconds, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        pass
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _bars(row: dict, as_of: str) -> dict[str, float]:
    # Original Unified charts are a mixture of compact OHLCV lists and dicts,
    # with either ISO or Unix-seconds/milliseconds timestamps.
    result: dict[str, float] = {}
    for item in row.get("chartBars") or []:
        if isinstance(item, list) and len(item) >= 5:
            stamp, raw_close = item[0], item[4]
        elif isinstance(item, dict):
            stamp, raw_close = item.get("time") or item.get("date"), item.get("close")
        else:
            continue
        day = _date_from_stamp(stamp)
        try:
            close = float(raw_close)
        except (TypeError, ValueError):
            continue
        if day and day <= as_of and math.isfinite(close) and close > 0:
            result[day] = close
    return result


def _calendar(prices: dict[str, dict[str, float]], as_of: str) -> list[str]:
    # Full-universe membership rotates: no individual ticker (including AAPL)
    # is guaranteed to appear in every EOD. Majority of CURRENT available
    # US-equity charts provides a deterministic exchange-session calendar.
    # Thin/illiquid one-off dates cannot create fake trading sessions.
    active = [bars for bars in prices.values() if as_of in bars and len(bars) >= 10]
    if not active:
        raise ValueError("No sufficiently complete current Unified charts for exchange calendar")
    counts = Counter(day for bars in active for day in bars)
    quorum = len(active) // 2 + 1
    days = sorted(day for day, count in counts.items()
                  if day <= as_of and count >= quorum)
    if not days or days[-1] != as_of:
        raise ValueError("No current consensus exchange session")
    return days


def _price_series(price_archive: dict[str, dict]) -> dict[str, dict[str, float]]:
    by_ticker: dict[str, dict[str, float]] = {}
    for day, point in sorted(price_archive.items()):
        for ticker, value in point["prices"].items():
            if not math.isfinite(float(value)) or float(value) <= 0:
                raise ValueError("Invalid historical EOD close: " + ticker + " " + day)
            by_ticker.setdefault(ticker, {})[day] = float(value)
    return by_ticker


def _events(points: list[dict]) -> list[dict]:
    result: list[dict] = []
    for old, current in zip(points, points[1:]):
        before, after = old["stages"], current["stages"]
        entries = [
            [ticker, before[ticker][0], value[0], {}]
            for ticker, value in after.items()
            if ticker in before and before[ticker][0] != value[0]
        ]
        entries.sort(key=lambda x: x[0])
        result.append({
            "sessionDate": current["sessionDate"],
            "previousSessionDate": old["sessionDate"],
            "runId": current["runId"],
            "events": entries,
        })
    return result


def _load_archive(directory: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for path in sorted(directory.glob("????-??.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schemaVersion") != SCHEMA or payload.get("month") != path.stem:
            raise ValueError("Incompatible forward history: " + str(path))
        for session in payload.get("sessions") or []:
            day = session.get("sessionDate")
            if not isinstance(day, str) or day[:7] != path.stem or day in rows:
                raise ValueError("Invalid/duplicate forward event day: " + str(day))
            rows[day] = session
    return rows


def _merge(events: list[dict], archived: dict[str, dict]) -> list[dict]:
    valid_days = {row["sessionDate"] for row in events}
    if set(archived) - valid_days:
        raise ValueError("Forward event archive has dates absent from stage archive")
    for day in events:
        date = day["sessionDate"]
        stored = archived.get(date)
        if stored is None:
            archived[date] = day
            continue
        if (stored.get("runId") != day["runId"] or
            stored.get("previousSessionDate") != day["previousSessionDate"] or
            [r[:3] for r in stored.get("events", [])] != [r[:3] for r in day["events"]]):
            raise ValueError("Conflicting point-in-time stage entries: " + date)
        for r in stored["events"]:
            if not isinstance(r, list) or len(r) != 4 or not isinstance(r[3], dict):
                raise ValueError("Corrupt stored outcome for " + date)
    return [archived[key] for key in sorted(archived)]


def _mature(sessions: list[dict], prices: dict[str, dict[str, float]],
            calendar: list[str]) -> None:
    positions = {day: idx for idx, day in enumerate(calendar)}
    for session in sessions:
        signal = session["sessionDate"]
        start = positions.get(signal)
        if start is None:
            # Mature flags and outcomes persist after rolling charts expire.
            continue
        entry_index = start + 1
        if entry_index >= len(calendar):
            continue
        entry_day = calendar[entry_index]
        matured = session.setdefault("matured", [])
        for h in HORIZONS:
            if entry_index + h < len(calendar) and str(h) not in matured:
                matured.append(str(h))
        matured.sort(key=int)
        for ticker, from_stage, stage, saved in session["events"]:
            if not 0 <= from_stage <= 4 or not 0 <= stage <= 4:
                raise ValueError("Invalid historical stage")
            ticker_prices = prices.get(ticker) or {}
            entry = ticker_prices.get(entry_day)
            for h in HORIZONS:
                key = str(h)
                exit_index = entry_index + h
                if key in saved or exit_index >= len(calendar):
                    continue
                exit_day = calendar[exit_index]
                exit_price = ticker_prices.get(exit_day)
                if entry is None or exit_price is None:
                    continue  # mature but unavailable: excluded, never zero-filled
                value = round((exit_price / entry - 1) * 100, 4)
                if math.isfinite(value):
                    saved[key] = value


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "meanPct": None, "medianPct": None,
                "winRatePct": None, "p10Pct": None, "p90Pct": None}
    ordered = sorted(values)
    def quantile(p: float) -> float:
        index = (len(ordered) - 1) * p
        lo, hi = int(index), math.ceil(index)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)
    return {"n": len(values), "meanPct": round(sum(values) / len(values), 3),
            "medianPct": round(median(values), 3),
            "winRatePct": round(100 * sum(v > 0 for v in values) / len(values), 2),
            "p10Pct": round(quantile(0.1), 3),
            "p90Pct": round(quantile(0.9), 3)}


def _missing_reasons(sessions: list[dict], calendar: list[str],
                     archived: dict[str, dict], horizon: int, stage: int) -> dict:
    """Partition missing mature outcomes without guessing missing prices."""
    positions = {day: index for index, day in enumerate(calendar)}
    causes = {"missingSessionGap": 0, "missingTickerQuote": 0,
              "missingUnclassified": 0}
    key = str(horizon)
    for session in sessions:
        if key not in session.get("matured", []):
            continue
        start = positions.get(session["sessionDate"])
        for ticker, _old_stage, new_stage, saved in session["events"]:
            if new_stage != stage or key in saved:
                continue
            if start is None or start + 1 + horizon >= len(calendar):
                causes["missingUnclassified"] += 1
                continue
            entry_day, exit_day = calendar[start + 1], calendar[start + 1 + horizon]
            if entry_day not in archived or exit_day not in archived:
                causes["missingSessionGap"] += 1
            elif (ticker not in archived[entry_day]["prices"] or
                  ticker not in archived[exit_day]["prices"]):
                causes["missingTickerQuote"] += 1
            else:
                causes["missingUnclassified"] += 1
    return causes


def _data_quality(calendar: list[str], archived: dict[str, dict]) -> dict:
    first = min(archived)
    # The source chart calendar is rolling (~260 sessions); older permanent
    # archives must never make the current calendar coverage ratio impossible.
    window_start = max(first, calendar[0])
    market_days = sorted(set(day for day in calendar if day >= window_start) |
                         set(day for day in archived if day >= window_start))
    gaps = [day for day in market_days if day not in archived]
    expected = sum(day["expectedEvaluated"] for day in archived.values())
    actual = sum(day["priceCount"] for day in archived.values())
    return {
        "archiveStart": first,
        "coverageWindowStart": window_start,
        "archivedSessions": len(market_days) - len(gaps),
        "totalArchivedSessions": len(archived),
        "exchangeSessionsInWindow": len(market_days),
        "missingExchangeSessions": gaps,
        "sourcePriceCoveragePct": round(100 * actual / expected, 2) if expected else None,
        "expectedSourceQuotes": expected,
        "actualSourceQuotes": actual,
    }


def report(sessions: list[dict], calendar: list[str], as_of: str,
           archived: dict[str, dict]) -> dict:
    all_events = sum(len(row["events"]) for row in sessions)
    data_quality = _data_quality(calendar, archived)
    by_horizon: dict[str, dict] = {}
    for h in HORIZONS:
        stage_rows: dict[str, dict] = {}
        for stage in range(5):
            matured = [event[3].get(str(h))
                for session in sessions if str(h) in session.get("matured", [])
                for event in session["events"] if event[2] == stage]
            values = [float(value) for value in matured if value is not None]
            eligible = len(matured)
            matured_dates = len({
                session["sessionDate"] for session in sessions
                if str(h) in session.get("matured", [])
                and any(event[2] == stage for event in session["events"])
            })
            pending = sum(
                1 for session in sessions if str(h) not in session.get("matured", [])
                for event in session["events"] if event[2] == stage
            )
            stats = _stats(values)
            stats.update(_missing_reasons(sessions, calendar, archived, h, stage))
            stats.update({
                "expectedMatured": eligible,
                "missingMatured": eligible - len(values),
                "pending": pending,
                "maturedSignalDates": matured_dates,
                "coveragePct": round(100 * len(values) / eligible, 2) if eligible else None,
            })
            if (stats["missingSessionGap"] + stats["missingTickerQuote"] +
                stats["missingUnclassified"] != stats["missingMatured"]):
                raise ValueError("Outcome missing-cause audit does not reconcile")
            stats["eligibleForCalibration"] = (
                eligible >= 250 and matured_dates >= 20 and
                stats["coveragePct"] is not None and stats["coveragePct"] >= 99.0 and
                not data_quality["missingExchangeSessions"]
            )
            stage_rows[str(stage)] = stats
        by_horizon[str(h)] = stage_rows
    return {
        "schemaVersion": REPORT_SCHEMA, "scope": SCOPE, "asOf": as_of,
        "horizons": list(HORIZONS), "archivedEventDays": len(sessions),
        "stageTransitions": all_events,
        "entryRule": "signal close -> next exchange-session close",
        "exitRule": "h complete exchange sessions after entry close",
        "benchmark": None, "dividendsIncluded": False,
        "pointInTimeStageMembership": True, "survivorshipGuard": "unmatched tickers excluded; missing mature outcomes counted",
        "calendarSource": "majority of current Unified EOD chart dates",
        "priceSource": "archived point-in-time EOD metrics.price (not dividends adjusted)",
        "dataQuality": data_quality,
        "byHorizon": by_horizon,
    }


def build(latest_path: Path, stages_dir: Path, prices_dir: Path, outcomes_dir: Path, output: Path) -> dict:
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    as_of = str((latest.get("source") or {}).get("sessionDate") or "")
    points = all_points(load_months(stages_dir))
    if not points or points[-1]["sessionDate"] != as_of:
        raise ValueError("Stage archive and EOD snapshot have different latest dates")
    # Live chart bars define exchange session dates only. Their historical
    # prices may be stale/partial and MUST NOT determine realized outcomes.
    chart_dates = {
        str(row.get("ticker") or "").upper(): _bars(row, as_of)
        for row in (latest.get("trendBirthCandidateIndex") or [])
    }
    calendar = _calendar(chart_dates, as_of)
    closed = load_prices(prices_dir)
    if as_of not in closed or set(closed) != {p["sessionDate"] for p in points}:
        raise ValueError("Daily close and stage archives are not aligned")
    for point in points:
        close = closed[point["sessionDate"]]
        if (close.get("runId") != point["runId"] or
            close.get("expectedEvaluated") != point["evaluatedCount"]):
            raise ValueError("EOD close provenance mismatch: " + point["sessionDate"])
    prices = _price_series(closed)
    sessions = _merge(_events(points), _load_archive(outcomes_dir))
    _mature(sessions, prices, calendar)
    grouped: dict[str, list[dict]] = {}
    for session in sessions:
        grouped.setdefault(session["sessionDate"][:7], []).append(session)
    for month, rows in grouped.items():
        write_json(outcomes_dir / (month + ".json"), {
            "schemaVersion": SCHEMA, "month": month, "scope": SCOPE,
            "sessions": rows,
        })
    result = report(sessions, calendar, as_of, closed)
    write_json(output, result)
    return {"asOf": as_of, "transitions": result["stageTransitions"],
            "archivedDays": len(sessions),
            "matured5": sum(result["byHorizon"]["5"][str(i)]["n"] for i in range(5))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", type=Path, required=True)
    parser.add_argument("--stages-dir", type=Path, required=True)
    parser.add_argument("--prices-dir", type=Path, required=True)
    parser.add_argument("--outcomes-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.latest, args.stages_dir, args.prices_dir, args.outcomes_dir, args.output)))


if __name__ == "__main__":
    main()
