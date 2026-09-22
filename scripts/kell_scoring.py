#!/usr/bin/env python3
"""Transparent Oliver Kell-style scoring for already-selected StockScout candidates.

This module never discovers or adds candidates. It only scores a supplied candidate's
existing OHLCV history. Definitions are deterministic proxies inspired by Oliver Kell's
publicly discussed screens/cycle concepts; they are not claimed to reproduce proprietary
screen formulas.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

MODEL_VERSION = "kell-overlay-v1"

WEIGHTS = {
    "52w_high": 8,
    "unusual_volume": 10,
    "bull_snort": 12,
    "doubler": 8,
    "gapper": 8,
    "strength_on_down_day": 8,
    "ema_readiness": 10,
    "wedge_pop": 10,
    "ema_crossback": 8,
    "base_n_break": 8,
    "tightening": 5,
    "breakout_proximity": 5,
}


def _bars(rows: list | None) -> list[dict[str, float | str]]:
    out: list[dict[str, float | str]] = []
    for row in rows or []:
        if isinstance(row, list) and len(row) >= 6:
            source = {
                "time": row[0], "open": row[1], "high": row[2],
                "low": row[3], "close": row[4], "volume": row[5],
            }
        elif isinstance(row, dict):
            source = row
        else:
            continue
        try:
            bar = {
                "time": str(source.get("time") or source.get("date") or ""),
                "open": float(source["open"]),
                "high": float(source["high"]),
                "low": float(source["low"]),
                "close": float(source["close"]),
                "volume": float(source.get("volume") or 0.0),
            }
        except (KeyError, TypeError, ValueError):
            continue
        if all(math.isfinite(float(bar[key])) for key in ("open", "high", "low", "close", "volume")):
            out.append(bar)
    return out


def _ema(values: list[float], window: int) -> list[float | None]:
    if not values:
        return []
    alpha = 2.0 / (window + 1.0)
    current = values[0]
    out: list[float | None] = []
    for i, value in enumerate(values):
        current = value if i == 0 else value * alpha + current * (1.0 - alpha)
        out.append(current if i + 1 >= window else None)
    return out


def _range_pct(sample: list[dict[str, Any]]) -> float | None:
    if not sample:
        return None
    low = min(float(x["low"]) for x in sample)
    high = max(float(x["high"]) for x in sample)
    return (high / low - 1.0) * 100.0 if low > 0 else None


def _return_pct(closes: list[float], sessions: int) -> float | None:
    if len(closes) <= sessions or closes[-sessions - 1] <= 0:
        return None
    return (closes[-1] / closes[-sessions - 1] - 1.0) * 100.0


def _true_range_pct(bar: dict[str, Any], prev_close: float) -> float:
    high = float(bar["high"])
    low = float(bar["low"])
    tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
    return tr / prev_close * 100.0 if prev_close > 0 else 0.0


def _fmt(value: float | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _criterion(hit: bool | None, max_points: int, detail: str) -> dict:
    return {
        "hit": hit,
        "points": max_points if hit is True else 0,
        "max_points": max_points,
        "available": hit is not None,
        "detail": detail,
    }


def score_candidate(chart_rows: list | None, benchmark_rows: list | None = None) -> dict:
    """Return additive Kell overlay fields for one existing StockScout candidate."""
    bars = _bars(chart_rows)
    bench = _bars(benchmark_rows)
    empty = {
        "kell_52w_high": None,
        "kell_unusual_volume": None,
        "kell_rvol_3x": None,
        "kell_bull_snort": None,
        "kell_doubler": None,
        "kell_gapper": None,
        "kell_strength_on_down_day": None,
        "kell_ema_readiness": None,
        "kell_wedge_pop": None,
        "kell_ema_crossback": None,
        "kell_base_n_break": None,
        "kell_tightening": None,
        "kell_breakout_proximity": None,
        "kell_breakout_proximity_pct": None,
        "kell_score": 0.0,
        "score_breakdown": {
            "model_version": MODEL_VERSION,
            "points": 0,
            "possible_points": 0,
            "criteria": {},
        },
        "kell_metrics": {},
    }
    if len(bars) < 21:
        return empty

    closes = [float(x["close"]) for x in bars]
    volumes = [float(x["volume"]) for x in bars]
    last = bars[-1]
    prev = bars[-2]
    prev_close = float(prev["close"])
    close = float(last["close"])
    last_range = float(last["high"]) - float(last["low"])
    close_location = (
        (close - float(last["low"])) / last_range * 100.0
        if last_range > 0 else 50.0
    )
    ret_1d = (close / prev_close - 1.0) * 100.0 if prev_close > 0 else None
    gap_pct = (float(last["open"]) / prev_close - 1.0) * 100.0 if prev_close > 0 else None

    vol_base = sum(volumes[-21:-1]) / 20.0
    rvol20 = volumes[-1] / vol_base if vol_base > 0 else None

    high_window = bars[-252:] if len(bars) >= 252 else bars
    high_52w = max(float(x["high"]) for x in high_window)
    prior_high_window = bars[-253:-1] if len(bars) >= 253 else bars[:-1]
    prior_52w_high = max((float(x["high"]) for x in prior_high_window), default=None)
    distance_52w = (close / high_52w - 1.0) * 100.0 if high_52w > 0 else None
    new_52w_high = (
        prior_52w_high is not None and float(last["high"]) >= prior_52w_high
    )
    near_52w = distance_52w is not None and distance_52w >= -3.0

    ret_3m = _return_pct(closes, 63)
    ret_6m = _return_pct(closes, 126)

    ema10 = _ema(closes, 10)
    ema20 = _ema(closes, 20)
    e10 = ema10[-1]
    e20 = ema20[-1]
    e10_5 = ema10[-6] if len(ema10) >= 6 else None
    e20_5 = ema20[-6] if len(ema20) >= 6 else None
    dist_e10 = (close / e10 - 1.0) * 100.0 if e10 not in (None, 0) else None
    ema_ready = (
        e10 is not None and e20 is not None and e10_5 is not None and e20_5 is not None
        and close >= e10 >= e20
        and e10 > e10_5 and e20 >= e20_5
        and dist_e10 is not None and dist_e10 <= 8.0
    )

    prior10 = bars[-11:-1]
    prior20 = bars[-21:-1]
    prior40 = bars[-41:-1] if len(bars) >= 41 else []
    range10 = _range_pct(prior10)
    range20 = _range_pct(prior20)
    range40 = _range_pct(prior40)
    prior10_high = max(float(x["high"]) for x in prior10) if prior10 else None
    prior20_high = max(float(x["high"]) for x in prior20) if prior20 else None

    wedge_contracted = (
        range10 is not None and range20 is not None and range20 > 0
        and range10 <= range20 * 0.70
    )
    wedge_pop = (
        wedge_contracted
        and prior10_high is not None and close > prior10_high
        and rvol20 is not None and rvol20 >= 1.5
        and close_location >= 65.0
    )

    prev_e10 = ema10[-2] if len(ema10) >= 2 else None
    prev_e20 = ema20[-2] if len(ema20) >= 2 else None
    recent_cross_window = range(max(0, len(bars) - 6), len(bars) - 1)
    was_below = any(
        (
            ema10[i] is not None and closes[i] <= float(ema10[i])
        ) or (
            ema20[i] is not None and closes[i] <= float(ema20[i])
        )
        for i in recent_cross_window
    )
    ema_crossback = (
        e10 is not None and e20 is not None
        and close > e10 and close > e20
        and e10 >= e20 * 0.995
        and was_below
        and close_location >= 55.0
    )

    base_before_break = (
        range20 is not None and range40 is not None
        and range20 <= 18.0 and range40 <= 30.0
    )
    base_n_break = (
        base_before_break
        and prior20_high is not None and close > prior20_high
        and rvol20 is not None and rvol20 >= 1.3
        and close_location >= 60.0
    )

    tr = [
        _true_range_pct(bars[i], float(bars[i - 1]["close"]))
        for i in range(1, len(bars))
    ]
    recent_tr = median(tr[-10:]) if len(tr) >= 10 else None
    prior_tr_slice = tr[-30:-10] if len(tr) >= 30 else []
    prior_tr = median(prior_tr_slice) if prior_tr_slice else None
    tightening = (
        recent_tr is not None and prior_tr is not None and prior_tr > 0
        and recent_tr <= prior_tr * 0.75
    )
    if not tightening and range10 is not None and range40 is not None and range40 > 0:
        tightening = range10 <= range40 * 0.55

    breakout_proximity_pct = (
        (close / prior20_high - 1.0) * 100.0
        if prior20_high not in (None, 0) else None
    )
    breakout_proximity = (
        breakout_proximity_pct is not None
        and -3.0 <= breakout_proximity_pct <= 1.5
    )

    unusual_volume = rvol20 is not None and rvol20 >= 2.0
    rvol_3x = rvol20 is not None and rvol20 >= 3.0
    bull_snort = (
        ret_1d is not None and ret_1d >= 4.0
        and rvol20 is not None and rvol20 >= 2.0
        and close_location >= 70.0
    )
    doubler = (
        (ret_6m is not None and ret_6m >= 100.0)
        or (ret_3m is not None and ret_3m >= 50.0)
    )
    gapper = gap_pct is not None and gap_pct >= 3.0

    strength_down_day: bool | None = None
    benchmark_ret = None
    relative_outperformance = None
    if len(bench) >= 2:
        b_prev = float(bench[-2]["close"])
        b_close = float(bench[-1]["close"])
        if b_prev > 0:
            benchmark_ret = (b_close / b_prev - 1.0) * 100.0
            if ret_1d is not None:
                relative_outperformance = ret_1d - benchmark_ret
                strength_down_day = (
                    benchmark_ret < 0.0
                    and ret_1d >= 0.0
                    and relative_outperformance >= 1.5
                    and close_location >= 60.0
                )

    criteria = {
        "52w_high": _criterion(
            near_52w or new_52w_high, WEIGHTS["52w_high"],
            f"distance={_fmt(distance_52w)}%; new_high={new_52w_high}",
        ),
        "unusual_volume": _criterion(
            unusual_volume, WEIGHTS["unusual_volume"],
            f"RVOL20={_fmt(rvol20, 2)}x; threshold=2.0x",
        ),
        "bull_snort": _criterion(
            bull_snort, WEIGHTS["bull_snort"],
            f"ret1d={_fmt(ret_1d)}%; RVOL20={_fmt(rvol20, 2)}x; close_location={_fmt(close_location)}%",
        ),
        "doubler": _criterion(
            doubler if ret_3m is not None or ret_6m is not None else None,
            WEIGHTS["doubler"],
            f"ret3m={_fmt(ret_3m)}%; ret6m={_fmt(ret_6m)}%; thresholds=50%/100%",
        ),
        "gapper": _criterion(
            gapper, WEIGHTS["gapper"],
            f"opening_gap={_fmt(gap_pct)}%; threshold=3%",
        ),
        "strength_on_down_day": _criterion(
            strength_down_day, WEIGHTS["strength_on_down_day"],
            (
                f"SPY={_fmt(benchmark_ret)}%; stock={_fmt(ret_1d)}%; "
                f"relative={_fmt(relative_outperformance)}%"
                if benchmark_ret is not None
                else "benchmark OHLCV unavailable; criterion excluded from denominator"
            ),
        ),
        "ema_readiness": _criterion(
            ema_ready, WEIGHTS["ema_readiness"],
            f"close={_fmt(close, 2)}; EMA10={_fmt(e10, 2)}; EMA20={_fmt(e20, 2)}; distEMA10={_fmt(dist_e10)}%",
        ),
        "wedge_pop": _criterion(
            wedge_pop, WEIGHTS["wedge_pop"],
            f"prior10/prior20 contraction={wedge_contracted}; RVOL20={_fmt(rvol20, 2)}x; close>10Dhigh={bool(prior10_high and close > prior10_high)}",
        ),
        "ema_crossback": _criterion(
            ema_crossback, WEIGHTS["ema_crossback"],
            f"was_below_10/20_in_prior5={was_below}; close_above_10/20={bool(e10 and e20 and close > e10 and close > e20)}",
        ),
        "base_n_break": _criterion(
            base_n_break if range40 is not None else None, WEIGHTS["base_n_break"],
            f"range20={_fmt(range20)}%; range40={_fmt(range40)}%; breakout20D={bool(prior20_high and close > prior20_high)}",
        ),
        "tightening": _criterion(
            tightening if recent_tr is not None else None, WEIGHTS["tightening"],
            f"medianTR10={_fmt(recent_tr)}%; priorTR20={_fmt(prior_tr)}%; range10={_fmt(range10)}%; range40={_fmt(range40)}%",
        ),
        "breakout_proximity": _criterion(
            breakout_proximity, WEIGHTS["breakout_proximity"],
            f"distance_to_prior20D_high={_fmt(breakout_proximity_pct)}%; target=-3.0%..+1.5%",
        ),
    }

    points = sum(x["points"] for x in criteria.values() if x["available"])
    possible = sum(x["max_points"] for x in criteria.values() if x["available"])
    score = round(points / possible * 100.0, 1) if possible else 0.0

    return {
        "kell_52w_high": near_52w or new_52w_high,
        "kell_unusual_volume": unusual_volume,
        "kell_rvol_3x": rvol_3x,
        "kell_bull_snort": bull_snort,
        "kell_doubler": doubler if ret_3m is not None or ret_6m is not None else None,
        "kell_gapper": gapper,
        "kell_strength_on_down_day": strength_down_day,
        "kell_ema_readiness": ema_ready,
        "kell_wedge_pop": wedge_pop,
        "kell_ema_crossback": ema_crossback,
        "kell_base_n_break": base_n_break if range40 is not None else None,
        "kell_tightening": tightening if recent_tr is not None else None,
        "kell_breakout_proximity": breakout_proximity,
        "kell_breakout_proximity_pct": breakout_proximity_pct,
        "kell_score": score,
        "score_breakdown": {
            "model_version": MODEL_VERSION,
            "points": points,
            "possible_points": possible,
            "criteria": criteria,
        },
        "kell_metrics": {
            "rvol20": rvol20,
            "ret_1d_pct": ret_1d,
            "ret_3m_pct": ret_3m,
            "ret_6m_pct": ret_6m,
            "gap_pct": gap_pct,
            "close_location_pct": close_location,
            "distance_to_52w_high_pct": distance_52w,
            "new_52w_high": new_52w_high,
            "ema10": e10,
            "ema20": e20,
            "range10_pct": range10,
            "range20_pct": range20,
            "range40_pct": range40,
            "breakout_proximity_pct": breakout_proximity_pct,
            "benchmark_ret_1d_pct": benchmark_ret,
            "relative_outperformance_pct": relative_outperformance,
        },
    }


def enrich_snapshot(snapshot: dict, benchmark_rows: list | None = None) -> dict:
    """Enrich an existing snapshot in-place without adding/removing/reordering candidates."""
    candidates = snapshot.get("candidates") or []
    original_tickers = [str(item.get("ticker") or "") for item in candidates]
    for item in candidates:
        item.update(score_candidate(item.get("chartBars") or [], benchmark_rows))
    assert [str(item.get("ticker") or "") for item in candidates] == original_tickers
    snapshot["kellScoring"] = {
        "modelVersion": MODEL_VERSION,
        "scope": "existing-candidates-only",
        "candidateCount": len(candidates),
        "candidateGenerationChanged": False,
        "benchmark": "SPY" if benchmark_rows else "unavailable-in-stored-snapshot",
    }
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    source = Path(args.input)
    snapshot = json.loads(source.read_text(encoding="utf-8"))
    before = [item.get("ticker") for item in snapshot.get("candidates") or []]
    enrich_snapshot(snapshot)
    after = [item.get("ticker") for item in snapshot.get("candidates") or []]
    if before != after:
        raise AssertionError("Kell overlay changed candidate membership/order")

    scores = sorted(
        (
            (str(item.get("ticker") or ""), float(item.get("kell_score") or 0.0))
            for item in snapshot.get("candidates") or []
        ),
        key=lambda x: (-x[1], x[0]),
    )
    summary = {
        "status": "ok",
        "sessionDate": (snapshot.get("source") or {}).get("sessionDate"),
        "candidateCount": len(before),
        "candidateCountPreserved": before == after,
        "scoreCoverage": sum(item.get("score_breakdown", {}).get("possible_points", 0) > 0 for item in snapshot.get("candidates") or []),
        "topKellScores": scores[:10],
    }
    if args.output:
        Path(args.output).write_text(
            json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
