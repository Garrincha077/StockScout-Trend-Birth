#!/usr/bin/env python3
"""Build compact Kell browser data plus lazy-load chart shards.

The full review snapshot remains the reproducible source of truth. The browser
payload keeps filters/metrics small and places OHLCV history in deterministic
chunks so the UI only downloads charts that become visible.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

METRIC_KEYS = (
    "price", "rvol", "rsi14", "emaGapPct", "slope50", "slope30w",
    "swingState", "baseLike", "setup", "actionability",
)
KELL_METRIC_KEYS = (
    "ret_3m_pct", "ret_6m_pct", "ret_ytd_pct", "gap_pct", "rvol20",
    "beta", "beta_source", "revenue_yoy_pct", "eps_yoy_pct", "rs_rank", "weekly_ema10",
    "breakout_proximity_pct",
)


def pick(source: dict, keys: tuple[str, ...]) -> dict:
    return {key: source.get(key) for key in keys if key in source}


def compact_bar(row) -> list | None:
    """Normalize one chart row to [date, O, H, L, C, volume]."""
    if isinstance(row, list):
        if len(row) < 6:
            return None
        values = [row[0], *row[1:6]]
    elif isinstance(row, dict):
        values = [
            row.get("time") or row.get("date"),
            row.get("open"),
            row.get("high"),
            row.get("low"),
            row.get("close"),
            row.get("volume") or 0,
        ]
    else:
        return None
    if not values[0]:
        return None
    try:
        numeric = [float(value) for value in values[1:]]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in numeric[:4]):
        return None
    return [values[0], *numeric]


def compact_candidate(item: dict, chart_shard: int | None = None) -> dict:
    bars = item.get("chartBars") or []
    out = {
        "ticker": item.get("ticker"),
        "sources": list(item.get("sources") or []),
        "metrics": pick(item.get("metrics") or {}, METRIC_KEYS),
        "kell_metrics": pick(item.get("kell_metrics") or {}, KELL_METRIC_KEYS),
        "kell_score": item.get("kell_score"),
        "kell_cycle_stage": item.get("kell_cycle_stage"),
        "kell_stage": item.get("kell_stage") or {},
        "kell_breakout_proximity_pct": item.get("kell_breakout_proximity_pct"),
        "kellScreens": list(item.get("kellScreens") or item.get("kell_screens") or []),
        "kellSetups": list(item.get("kellSetups") or item.get("kell_setups") or []),
        "kellContext": list(item.get("kellContext") or []),
        "chartBarsCount": len(bars),
        "weeklyChartBarsCount": len(item.get("weeklyChartBars") or []),
    }
    if chart_shard is not None:
        out["chartShard"] = chart_shard
    return out


def write_chart_shards(
    candidates: list[dict],
    charts_dir: Path,
    src: dict,
    chunk_size: int,
) -> dict:
    if chunk_size < 1:
        raise ValueError("chart chunk size must be positive")
    charts_dir.mkdir(parents=True, exist_ok=True)
    for stale in charts_dir.glob("shard-*.json"):
        stale.unlink()

    shard_count = (len(candidates) + chunk_size - 1) // chunk_size
    chart_candidate_count = 0
    chart_bar_count = 0
    weekly_chart_candidate_count = 0
    weekly_chart_bar_count = 0
    for shard_index in range(shard_count):
        chunk = candidates[shard_index * chunk_size:(shard_index + 1) * chunk_size]
        charts: dict[str, list] = {}
        for item in chunk:
            ticker = str(item.get("ticker") or "")
            daily = [bar for row in (item.get("chartBars") or []) if (bar := compact_bar(row)) is not None]
            weekly = [bar for row in (item.get("weeklyChartBars") or []) if (bar := compact_bar(row)) is not None]
            if ticker and len(daily) >= 2:
                charts[ticker] = {"daily": daily, "weekly": weekly}
                chart_candidate_count += 1
                chart_bar_count += len(daily)
                if len(weekly) >= 2:
                    weekly_chart_candidate_count += 1
                    weekly_chart_bar_count += len(weekly)
        payload = {
            "schemaVersion": "kell-chart-shard-v2",
            "source": {
                "runId": src.get("runId"),
                "sessionDate": src.get("sessionDate"),
            },
            "shard": shard_index,
            "charts": charts,
        }
        (charts_dir / f"shard-{shard_index:03d}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    return {
        "schemaVersion": "kell-chart-shard-v2",
        "basePath": "data/kell-charts",
        "shardCount": shard_count,
        "chunkSize": chunk_size,
        "chartCandidateCount": chart_candidate_count,
        "chartBarCount": chart_bar_count,
        "weeklyChartCandidateCount": weekly_chart_candidate_count,
        "weeklyChartBarCount": weekly_chart_bar_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--charts-dir")
    parser.add_argument("--chart-chunk-size", type=int, default=48)
    args = parser.parse_args()

    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    src = source.get("source") or {}
    source_candidates = list(source.get("kellCandidates") or [])

    chart_data = None
    if args.charts_dir:
        chart_data = write_chart_shards(
            source_candidates,
            Path(args.charts_dir),
            src,
            args.chart_chunk_size,
        )

    out = {
        "schemaVersion": "kell-compact-v4",
        "source": {
            "runId": src.get("runId"),
            "sessionDate": src.get("sessionDate"),
            "readOnly": True,
        },
        "kellScoring": source.get("kellScoring") or {},
        "kellCandidateCount": source.get("kellCandidateCount", 0),
        "kellChartData": chart_data,
        "kellCandidates": [
            compact_candidate(
                item,
                (index // args.chart_chunk_size) if chart_data is not None else None,
            )
            for index, item in enumerate(source_candidates)
        ],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "ok",
        "sessionDate": out["source"]["sessionDate"],
        "kellCandidates": len(out["kellCandidates"]),
        "chartCandidates": (chart_data or {}).get("chartCandidateCount", 0),
        "chartShards": (chart_data or {}).get("shardCount", 0),
        "bytes": output.stat().st_size,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
