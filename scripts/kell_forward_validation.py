#!/usr/bin/env python3
"""Point-in-time forward validation for Kell v4/v5 score snapshots.

The validator never reconstructs historical candidate membership from today's universe.
It consumes score snapshots that were actually archived on each session date and joins
them to a later OHLCV store only for outcome measurement.

Default horizons are trading sessions: 5, 10, 20, 40, 60 and 120.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

try:
    from .market_sessions import CALENDAR_PATH, exchange_sessions, session_date
except ImportError:
    from market_sessions import CALENDAR_PATH, exchange_sessions, session_date

DEFAULT_HORIZONS = (5, 10, 20, 40, 60, 120)
MODEL_FIELDS = {
    "v5": "kell_score",
    "v4": "legacy_v4_score",
}


def _number(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _candidate_rows(payload: dict) -> list[dict]:
    if payload.get("schemaVersion") == "kell-score-history-v2":
        columns = list(payload.get("columns") or [])
        return [
            dict(zip(columns, row))
            for row in (payload.get("candidates") or [])
            if isinstance(row, list) and len(row) == len(columns)
        ]
    return list(payload.get("candidates") or payload.get("kellCandidates") or [])


def _score(item: dict, model: str) -> float | None:
    if model == "v5":
        return _number(item.get("kell_score"))
    if model == "v4":
        direct = _number(item.get("legacy_v4_score"))
        if direct is not None:
            return direct
        return _number((item.get("score_breakdown") or {}).get("legacy_v4_score"))
    raise ValueError(f"unknown model: {model}")


def _run_attempt(source: dict) -> int:
    direct = source.get("runAttempt")
    try:
        if direct is not None:
            return int(direct)
    except (TypeError, ValueError):
        pass
    run_id = str(source.get("runId") or "")
    tail = run_id.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def _snapshot_priority(snapshot: dict) -> tuple[int, int, int, str]:
    source = snapshot.get("source") or {}
    recovered = bool(source.get("recovered"))
    exact_recovery = (
        recovered
        and source.get("recoveryReliability") == "exact-pages-artifact"
        and source.get("artifactIdentityVerified") is True
        and source.get("pointInTimeCandidateMembership") is True
    )
    point_in_time_recovery = recovered and source.get("pointInTimeCandidateMembership") is True
    if not recovered:
        authenticity = 3  # contemporaneously archived score snapshot
    elif exact_recovery:
        authenticity = 2  # exact historical Pages universe, current model recomputation
    elif point_in_time_recovery:
        authenticity = 1
    else:
        authenticity = 0
    try:
        artifact_id = int(source.get("artifactId") or 0)
    except (TypeError, ValueError):
        artifact_id = 0
    return authenticity, _run_attempt(source), artifact_id, str(snapshot.get("path") or "")


def load_score_snapshots(scores_dir: Path) -> list[dict]:
    by_date: dict[str, dict] = {}
    paths = (sorted(scores_dir.glob("*.json")) + sorted(scores_dir.glob("*.json.gz")) + sorted(scores_dir.glob("*.json.gz.b64")))
    for path in paths:
        if path.name.endswith(".json.gz.b64"):
            packed = base64.b64decode(path.read_text(encoding="ascii"), validate=True)
            payload = json.loads(gzip.decompress(packed).decode("utf-8"))
        elif path.suffix == ".gz":
            payload = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
        payloads = (
            list(payload.get("snapshots") or [])
            if payload.get("schemaVersion") == "kell-score-history-bundle-v1"
            else [payload]
        )
        for snapshot_payload in payloads:
            source = dict(snapshot_payload.get("source") or {})
            day = session_date(source.get("sessionDate") or snapshot_payload.get("sessionDate"))
            if not day:
                continue
            rows = _candidate_rows(snapshot_payload)
            snapshot = {
                "path": str(path),
                "sessionDate": day,
                "runId": source.get("runId"),
                "modelVersion": (snapshot_payload.get("kellScoring") or {}).get("modelVersion")
                or snapshot_payload.get("modelVersion"),
                "source": source,
                "schemaVersion": snapshot_payload.get("schemaVersion"),
                "candidates": rows,
            }
            current = by_date.get(day)
            if current is None or _snapshot_priority(snapshot) > _snapshot_priority(current):
                by_date[day] = snapshot
    return [by_date[key] for key in sorted(by_date)]


def _normalize_bar(row: Any) -> dict | None:
    if isinstance(row, list) and len(row) >= 6:
        values = row[:6]
        source = {
            "date": values[0], "open": values[1], "high": values[2],
            "low": values[3], "close": values[4], "volume": values[5],
        }
    elif isinstance(row, dict):
        source = {
            "date": row.get("date") or row.get("time"),
            "open": row.get("open"), "high": row.get("high"),
            "low": row.get("low"), "close": row.get("close"),
            "volume": row.get("volume") or 0,
        }
    else:
        return None
    try:
        bar = {
            "date": session_date(source["date"]),
            "open": float(source["open"]),
            "high": float(source["high"]),
            "low": float(source["low"]),
            "close": float(source["close"]),
            "volume": float(source["volume"]),
        }
    except (TypeError, ValueError):
        return None
    if (not bar["date"] or
            not all(math.isfinite(bar[k]) and bar[k] > 0 for k in ("open", "high", "low", "close")) or
            not math.isfinite(bar["volume"]) or bar["volume"] < 0):
        return None
    return bar


def load_chart_store(charts_dir: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for path in sorted(charts_dir.glob("shard-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for ticker, chart in (payload.get("charts") or {}).items():
            rows = chart.get("daily") if isinstance(chart, dict) else chart
            by_day = {}
            for row in rows or []:
                if (bar := _normalize_bar(row)) is None:
                    continue
                day = bar["date"]
                if day in by_day and by_day[day] != bar:
                    raise ValueError(f"Conflicting daily bars for {ticker} on {day}")
                by_day[day] = bar
            normalized = [by_day[day] for day in sorted(by_day)]
            if normalized:
                existing = out.get(str(ticker))
                if existing is None or len(normalized) > len(existing):
                    out[str(ticker)] = normalized
    return out


def _deciles(rows: list[dict], model: str) -> dict[str, int]:
    scored = []
    for item in rows:
        ticker = str(item.get("ticker") or "")
        score = _score(item, model)
        if ticker and score is not None:
            scored.append((score, ticker))
    scored.sort(key=lambda x: (x[0], x[1]))
    n = len(scored)
    result: dict[str, int] = {}
    for index, (_, ticker) in enumerate(scored):
        # 1 = lowest score, 10 = highest score.
        result[ticker] = min(10, int(index * 10 / max(n, 1)) + 1)
    return result


def _outcome_for_window(bars: dict[str, dict], signal_day: str, sessions: tuple[str, ...]) -> dict | None:
    if not sessions or signal_day not in bars or any(day not in bars for day in sessions):
        return None
    future = [bars[day] for day in sessions]
    entry = future[0]["open"]
    if entry <= 0:
        return None
    exit_close = future[-1]["close"]
    return {
        "forward_return_pct": (exit_close / entry - 1.0) * 100.0,
        "mfe_pct": (max(bar["high"] for bar in future) / entry - 1.0) * 100.0,
        "mae_pct": (min(bar["low"] for bar in future) / entry - 1.0) * 100.0,
    }


def _outcome(bars: list[dict], signal_day: str, horizon: int,
             sessions: tuple[str, ...] | None = None) -> dict | None:
    by_day = {bar["date"]: bar for bar in bars}
    calendar = sessions if sessions is not None else tuple(sorted(by_day))
    if signal_day not in calendar:
        return None
    start = calendar.index(signal_day)
    future = calendar[start + 1:start + horizon + 1]
    return _outcome_for_window(by_day, signal_day, future) if len(future) == horizon else None


def _observed_sessions(chart_store: dict[str, list[dict]]) -> tuple[str, ...]:
    return tuple(sorted({bar["date"] for bars in chart_store.values() for bar in bars}))


def build_observations(
    snapshots: list[dict],
    chart_store: dict[str, list[dict]],
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    sessions: tuple[str, ...] | None = None,
) -> list[dict]:
    observations: list[dict] = []
    calendar = sessions if sessions is not None else _observed_sessions(chart_store)
    positions = {day: i for i, day in enumerate(calendar)}
    charts = {ticker: {bar["date"]: bar for bar in bars} for ticker, bars in chart_store.items()}
    for snapshot in snapshots:
        day = snapshot["sessionDate"]
        if day not in positions:
            continue
        start = positions[day]
        windows = {
            horizon: calendar[start + 1:start + horizon + 1] for horizon in horizons
            if start + horizon < len(calendar)
        }
        decile_maps = {model: _deciles(snapshot["candidates"], model) for model in MODEL_FIELDS}
        for item in snapshot["candidates"]:
            ticker = str(item.get("ticker") or "")
            bars = charts.get(ticker)
            if not ticker or not bars:
                continue
            for horizon, window in windows.items():
                outcome = _outcome_for_window(bars, day, window)
                if outcome is None:
                    continue
                for model in MODEL_FIELDS:
                    score = _score(item, model)
                    decile = decile_maps[model].get(ticker)
                    if score is None or decile is None:
                        continue
                    observations.append({
                        "sessionDate": snapshot["sessionDate"],
                        "ticker": ticker,
                        "model": model,
                        "score": score,
                        "decile": decile,
                        "horizon": horizon,
                        **outcome,
                    })
    return observations


def outcome_coverage(
    snapshots: list[dict],
    chart_store: dict[str, list[dict]],
    observations: list[dict],
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    sessions: tuple[str, ...] | None = None,
) -> dict[str, dict[str, dict]]:
    calendar = sessions if sessions is not None else _observed_sessions(chart_store)
    calendar_index = {value: index for index, value in enumerate(calendar)}
    matured_by_horizon: dict[int, set[str]] = {}
    for horizon in horizons:
        matured_by_horizon[horizon] = {
            snapshot["sessionDate"]
            for snapshot in snapshots
            if snapshot["sessionDate"] in calendar_index
            and calendar_index[snapshot["sessionDate"]] + horizon < len(calendar)
        }

    result: dict[str, dict[str, dict]] = {model: {} for model in MODEL_FIELDS}
    for model in MODEL_FIELDS:
        for horizon in horizons:
            matured_sessions = matured_by_horizon[horizon]
            expected = 0
            for snapshot in snapshots:
                if snapshot["sessionDate"] not in matured_sessions:
                    continue
                expected += sum(_score(item, model) is not None for item in snapshot["candidates"])
            observed = sum(
                1
                for row in observations
                if row["model"] == model and row["horizon"] == horizon
            )
            coverage_pct = round(observed / expected * 100.0, 2) if expected else None
            result[model][str(horizon)] = {
                "maturedSessions": len(matured_sessions),
                "expectedObservations": expected,
                "observedObservations": observed,
                "missingObservations": max(expected - observed, 0),
                "coveragePct": coverage_pct,
            }
    return result


def _stats(rows: list[dict]) -> dict:
    if not rows:
        return {
            "count": 0, "mean_return_pct": None, "median_return_pct": None,
            "hit_rate_pct": None, "mean_mfe_pct": None, "mean_mae_pct": None,
        }
    returns = [float(row["forward_return_pct"]) for row in rows]
    return {
        "count": len(rows),
        "mean_return_pct": round(sum(returns) / len(returns), 3),
        "median_return_pct": round(median(returns), 3),
        "hit_rate_pct": round(sum(value > 0 for value in returns) / len(returns) * 100.0, 2),
        "mean_mfe_pct": round(sum(float(row["mfe_pct"]) for row in rows) / len(rows), 3),
        "mean_mae_pct": round(sum(float(row["mae_pct"]) for row in rows) / len(rows), 3),
    }


def summarize(
    observations: list[dict],
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    coverage: dict[str, dict[str, dict]] | None = None,
    min_outcome_coverage_pct: float = 99.0,
) -> dict:
    result = {
        "schemaVersion": "kell-forward-validation-v1",
        "horizons": list(horizons),
        "models": {},
    }
    for model in MODEL_FIELDS:
        model_out: dict[str, Any] = {}
        for horizon in horizons:
            rows = [row for row in observations if row["model"] == model and row["horizon"] == horizon]
            deciles = {
                str(decile): _stats([row for row in rows if row["decile"] == decile])
                for decile in range(1, 11)
            }
            top = [row for row in rows if row["decile"] == 10]
            bottom = [row for row in rows if row["decile"] == 1]
            top_quintile = [row for row in rows if row["decile"] >= 9]
            bottom_quintile = [row for row in rows if row["decile"] <= 2]
            top_stats = _stats(top)
            bottom_stats = _stats(bottom)
            top_q_stats = _stats(top_quintile)
            bottom_q_stats = _stats(bottom_quintile)
            def spread(a: dict, b: dict) -> float | None:
                if a["mean_return_pct"] is None or b["mean_return_pct"] is None:
                    return None
                return round(a["mean_return_pct"] - b["mean_return_pct"], 3)
            coverage_row = (coverage or {}).get(model, {}).get(str(horizon))
            coverage_pct = (
                coverage_row.get("coveragePct")
                if isinstance(coverage_row, dict)
                else None
            )
            eligible = (
                coverage_row is None
                or (
                    coverage_pct is not None
                    and float(coverage_pct) >= float(min_outcome_coverage_pct)
                )
            )
            model_out[str(horizon)] = {
                "observations": len(rows),
                "maturedSessions": len({row["sessionDate"] for row in rows}),
                "outcomeCoverage": coverage_row,
                "eligibleForValidation": eligible,
                "minOutcomeCoveragePct": min_outcome_coverage_pct,
                "deciles": deciles,
                "topDecile": top_stats,
                "bottomDecile": bottom_stats,
                "topMinusBottomMeanReturnPct": spread(top_stats, bottom_stats),
                "topQuintile": top_q_stats,
                "bottomQuintile": bottom_q_stats,
                "topMinusBottomQuintileMeanReturnPct": spread(top_q_stats, bottom_q_stats),
            }
        result["models"][model] = model_out

    comparison = {}
    for horizon in horizons:
        v5 = result["models"]["v5"][str(horizon)]
        v4 = result["models"]["v4"][str(horizon)]
        v5_top = v5["topDecile"]["mean_return_pct"]
        v4_top = v4["topDecile"]["mean_return_pct"]
        eligible = bool(v5.get("eligibleForValidation")) and bool(v4.get("eligibleForValidation"))
        comparison[str(horizon)] = {
            "eligibleForValidation": eligible,
            "v5MinusV4TopDecileMeanReturnPct": (
                round(v5_top - v4_top, 3)
                if eligible and v5_top is not None and v4_top is not None
                else None
            ),
            "v5TopMinusBottomSpreadPct": (
                v5["topMinusBottomMeanReturnPct"] if eligible else None
            ),
            "v4TopMinusBottomSpreadPct": (
                v4["topMinusBottomMeanReturnPct"] if eligible else None
            ),
        }
    result["comparison"] = comparison
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores-dir", required=True)
    parser.add_argument("--charts-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--calendar", type=Path, default=CALENDAR_PATH)
    parser.add_argument("--as-of", help="Latest completed XNYS session represented in the chart inputs")
    parser.add_argument("--publication", type=Path, help="Verify the latest score archive against this Review publication")
    parser.add_argument("--include-swing-statistics", action="store_true",
                        help="Attach reconstructed comparisons and published plan execution counts")
    parser.add_argument(
        "--min-outcome-coverage-pct",
        type=float,
        default=99.0,
        help="Minimum matured outcome coverage required before validation comparisons are eligible",
    )
    parser.add_argument(
        "--horizons",
        default=",".join(str(x) for x in DEFAULT_HORIZONS),
        help="Comma-separated trading-session horizons, default 5,10,20,40,60,120",
    )
    args = parser.parse_args()
    horizons = tuple(sorted({int(value) for value in args.horizons.split(",") if int(value) > 0}))
    snapshots = load_score_snapshots(Path(args.scores_dir))
    charts = load_chart_store(Path(args.charts_dir))
    if not snapshots or not charts:
        parser.error("Kell forward validation requires score snapshots and dated OHLCV charts")
    publication = json.loads(args.publication.read_bytes()) if args.publication else None
    as_of = publication["sessionDate"] if publication else args.as_of or max(_observed_sessions(charts))
    if publication and args.as_of and args.as_of != as_of:
        parser.error("Requested Kell cutoff differs from publication session")
    sessions = exchange_sessions(as_of, args.calendar)
    eligible_days = set(sessions)
    snapshots = [snapshot for snapshot in snapshots if snapshot["sessionDate"] in eligible_days]
    if not snapshots:
        parser.error("No archived Kell score snapshots within the exchange calendar")
    if publication:
        keys = ("sessionDate", "runId", "unifiedManifestSha256")
        if any(snapshots[-1]["source"].get(key) != publication.get(key) for key in keys):
            parser.error("Latest Kell score archive does not match Review publication")
    observations = build_observations(snapshots, charts, horizons, sessions)
    coverage = outcome_coverage(snapshots, charts, observations, horizons, sessions)
    report = summarize(
        observations,
        horizons,
        coverage=coverage,
        min_outcome_coverage_pct=args.min_outcome_coverage_pct,
    )
    report["source"] = {
        "asOf": as_of,
        "lastSignalDate": snapshots[-1]["sessionDate"],
        "entryRule": "next_exchange_session_open",
        "exitRule": "hth_exchange_session_close_after_signal",
        "publicationBeforeEntryVerified": False,
        "calendar": "xnys-eod-sessions-v1",
        "scoreSnapshotCount": len(snapshots),
        "chartTickerCount": len(charts),
        "pointInTimeCandidateMembership": True,
        "minOutcomeCoveragePct": args.min_outcome_coverage_pct,
        "outcomeCoverageGuard": True,
    }
    if publication:
        report["source"].update({key: publication[key] for key in keys})
    if args.include_swing_statistics:
        from replay_kell_swing import ACTIONS_PATH, build_statistics
        from market_actions import read_actions

        actions, _ = read_actions(ACTIONS_PATH)
        report["swingStatistics"] = build_statistics(snapshots, charts, sessions, actions)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({
        "status": "ok",
        "scoreSnapshots": len(snapshots),
        "chartTickers": len(charts),
        "observations": len(observations),
        "horizons": list(horizons),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
