#!/usr/bin/env python3
"""Point-in-time forward validation for Kell v4/v5 score snapshots.

The validator never reconstructs historical candidate membership from today's universe.
It consumes score snapshots that were actually archived on each session date and joins
them to a later OHLCV store only for outcome measurement.

Default horizons are trading sessions: 5, 10, 20, 40, 60 and 120.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

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


def _date(value: Any) -> str:
    return str(value or "")[:10]


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


def load_score_snapshots(scores_dir: Path) -> list[dict]:
    snapshots = []
    paths = sorted(scores_dir.glob("*.json")) + sorted(scores_dir.glob("*.json.gz"))
    for path in paths:
        if path.suffix == ".gz":
            payload = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
        payloads = (
            list(payload.get("snapshots") or [])
            if payload.get("schemaVersion") == "kell-score-history-bundle-v1"
            else [payload]
        )
        for snapshot_payload in payloads:
            session_date = _date(
                (snapshot_payload.get("source") or {}).get("sessionDate")
                or snapshot_payload.get("sessionDate")
            )
            if not session_date:
                continue
            rows = _candidate_rows(snapshot_payload)
            snapshots.append({
                "path": str(path),
                "sessionDate": session_date,
                "runId": (snapshot_payload.get("source") or {}).get("runId"),
                "modelVersion": (snapshot_payload.get("kellScoring") or {}).get("modelVersion")
                or snapshot_payload.get("modelVersion"),
                "candidates": rows,
            })
    return snapshots


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
            "date": _date(source["date"]),
            "open": float(source["open"]),
            "high": float(source["high"]),
            "low": float(source["low"]),
            "close": float(source["close"]),
            "volume": float(source["volume"]),
        }
    except (TypeError, ValueError):
        return None
    if not bar["date"] or not all(math.isfinite(bar[k]) for k in ("open", "high", "low", "close", "volume")):
        return None
    return bar


def load_chart_store(charts_dir: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for path in sorted(charts_dir.glob("shard-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for ticker, chart in (payload.get("charts") or {}).items():
            rows = chart.get("daily") if isinstance(chart, dict) else chart
            normalized = [bar for row in (rows or []) if (bar := _normalize_bar(row)) is not None]
            if normalized:
                normalized.sort(key=lambda x: x["date"])
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


def _outcome(bars: list[dict], session_date: str, horizon: int) -> dict | None:
    index = next((i for i, bar in enumerate(bars) if bar["date"] == session_date), None)
    if index is None or index + horizon >= len(bars):
        return None
    entry = bars[index]["close"]
    if entry <= 0:
        return None
    future = bars[index + 1:index + horizon + 1]
    exit_close = bars[index + horizon]["close"]
    return {
        "forward_return_pct": (exit_close / entry - 1.0) * 100.0,
        "mfe_pct": (max(bar["high"] for bar in future) / entry - 1.0) * 100.0,
        "mae_pct": (min(bar["low"] for bar in future) / entry - 1.0) * 100.0,
    }


def build_observations(
    snapshots: list[dict],
    chart_store: dict[str, list[dict]],
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> list[dict]:
    observations: list[dict] = []
    for snapshot in snapshots:
        decile_maps = {model: _deciles(snapshot["candidates"], model) for model in MODEL_FIELDS}
        for item in snapshot["candidates"]:
            ticker = str(item.get("ticker") or "")
            bars = chart_store.get(ticker)
            if not ticker or not bars:
                continue
            for horizon in horizons:
                outcome = _outcome(bars, snapshot["sessionDate"], horizon)
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


def summarize(observations: list[dict], horizons: tuple[int, ...] = DEFAULT_HORIZONS) -> dict:
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
            model_out[str(horizon)] = {
                "observations": len(rows),
                "maturedSessions": len({row["sessionDate"] for row in rows}),
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
        comparison[str(horizon)] = {
            "v5MinusV4TopDecileMeanReturnPct": (
                round(v5_top - v4_top, 3) if v5_top is not None and v4_top is not None else None
            ),
            "v5TopMinusBottomSpreadPct": v5["topMinusBottomMeanReturnPct"],
            "v4TopMinusBottomSpreadPct": v4["topMinusBottomMeanReturnPct"],
        }
    result["comparison"] = comparison
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores-dir", required=True)
    parser.add_argument("--charts-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--horizons",
        default=",".join(str(x) for x in DEFAULT_HORIZONS),
        help="Comma-separated trading-session horizons, default 5,10,20,40,60,120",
    )
    args = parser.parse_args()
    horizons = tuple(sorted({int(value) for value in args.horizons.split(",") if int(value) > 0}))
    snapshots = load_score_snapshots(Path(args.scores_dir))
    charts = load_chart_store(Path(args.charts_dir))
    observations = build_observations(snapshots, charts, horizons)
    report = summarize(observations, horizons)
    report["source"] = {
        "scoreSnapshotCount": len(snapshots),
        "chartTickerCount": len(charts),
        "pointInTimeCandidateMembership": True,
    }
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
