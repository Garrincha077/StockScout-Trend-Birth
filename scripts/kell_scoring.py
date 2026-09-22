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

MODEL_VERSION = "kell-overlay-v4-screen-stage-setup"

# Keep discovery, structural stage, actionable setup and supporting context distinct.
# These are output-contract groups; they do not alter the underlying Unified universe.
DISCOVERY_FIELDS = (
    "kell_52w_high",
    "kell_unusual_volume",
    "kell_rvol_3x",
    "kell_bull_snort",
    "kell_momentum_3m_50",
    "kell_doubler_ytd",
    "kell_gapper",
    "kell_strength_on_down_day",
    "kell_rs_leader",
)
SETUP_FIELDS = (
    "kell_buyable_gap_proxy",
    "kell_wedge_pop",
    "kell_ema_crossback",
    "kell_base_n_break",
    "kell_tightening",
    "kell_breakout_proximity",
)

WEIGHTS = {
    "name_selection": 8,
    "growth_context": 8,
    "rs_leader": 6,
    "52w_high": 5,
    "unusual_volume": 5,
    "bull_snort": 8,
    "momentum_3m_50": 6,
    "doubler_ytd": 8,
    "gapper": 6,
    "buyable_gap_proxy": 8,
    "strength_on_down_day": 6,
    "rs_divergence": 10,
    "weekly_trend": 8,
    "ema_readiness": 6,
    "wedge_pop": 12,
    "ema_crossback": 10,
    "base_n_break": 12,
    "tightening": 4,
    "breakout_proximity": 4,
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


def _year(value: Any) -> int | None:
    try:
        return int(str(value)[:4])
    except (TypeError, ValueError):
        return None


def _ytd_return_pct(bars: list[dict[str, Any]]) -> float | None:
    """Calendar YTD performance versus the last available close of the prior year."""
    if len(bars) < 2:
        return None
    current_year = _year(bars[-1].get("time"))
    if current_year is None:
        return None
    prior_year_close = None
    for bar in reversed(bars[:-1]):
        bar_year = _year(bar.get("time"))
        if bar_year is not None and bar_year < current_year:
            prior_year_close = float(bar["close"])
            break
    if prior_year_close is None or prior_year_close <= 0:
        return None
    return (float(bars[-1]["close"]) / prior_year_close - 1.0) * 100.0


def _beta_from_aligned(
    aligned: list[tuple[dict[str, Any], float]],
    lookback: int = 126,
    min_observations: int = 60,
) -> float | None:
    """Estimate daily beta from aligned stock/SPY closes without adding external data."""
    sample = aligned[-(lookback + 1):]
    pairs: list[tuple[float, float]] = []
    for i in range(1, len(sample)):
        stock_prev = float(sample[i - 1][0]["close"])
        stock_now = float(sample[i][0]["close"])
        bench_prev = float(sample[i - 1][1])
        bench_now = float(sample[i][1])
        if stock_prev <= 0 or bench_prev <= 0:
            continue
        pairs.append((stock_now / stock_prev - 1.0, bench_now / bench_prev - 1.0))
    if len(pairs) < min_observations:
        return None
    stock_mean = sum(x for x, _ in pairs) / len(pairs)
    bench_mean = sum(y for _, y in pairs) / len(pairs)
    covariance = sum((x - stock_mean) * (y - bench_mean) for x, y in pairs)
    variance = sum((y - bench_mean) ** 2 for _, y in pairs)
    return covariance / variance if variance > 0 else None


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


def score_candidate(
    chart_rows: list | None,
    benchmark_rows: list | None = None,
    candidate_context: dict | None = None,
) -> dict:
    """Return a transparent Kell-style overlay for one existing StockScout candidate.

    v3 separates Kell's published Screening Guide formulas from the Cycle-of-Price-
    Action proxies. Core screens use the published price/volume/gap/YTD/beta rules;
    Wedge Pop, EMA Crossback, Base n' Break and related readiness fields remain
    transparent reproducible proxies rather than proprietary formulas.
    """
    bars = _bars(chart_rows)
    bench = _bars(benchmark_rows)
    context = candidate_context or {}

    def context_number(*names: str) -> float | None:
        for name in names:
            try:
                value = float(context.get(name))
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                return value
        return None

    fundamental_support = context.get("fundamentalSupport")
    revenue_yoy = context_number("revenueYoY", "revenue_yoy", "revenueGrowth", "salesGrowth")
    eps_yoy = context_number("epsYoY", "eps_yoy", "epsGrowth", "earningsGrowth")
    growth_available = fundamental_support is not None or revenue_yoy is not None or eps_yoy is not None
    growth_context: bool | None = None
    if growth_available:
        if revenue_yoy is not None and eps_yoy is not None:
            growth_context = revenue_yoy >= 25.0 and eps_yoy >= 25.0
        elif revenue_yoy is not None:
            growth_context = revenue_yoy >= 25.0
        elif eps_yoy is not None:
            growth_context = eps_yoy >= 25.0
        else:
            growth_context = bool(fundamental_support)

    rs_rank = context_number("rsRank", "rsRating", "rs_rank", "rs_rating")
    rs_leader: bool | None = rs_rank >= 90.0 if rs_rank is not None else None
    context_beta = context_number("beta", "beta1Y", "beta_1y", "beta60m", "beta_60m")

    empty = {
        "kell_52w_high": None,
        "kell_unusual_volume": None,
        "kell_rvol_3x": None,
        "kell_bull_snort": None,
        "kell_momentum_3m_50": None,
        "kell_doubler_ytd": None,
        "kell_doubler_6m": None,
        "kell_doubler": None,
        "kell_gapper": None,
        "kell_buyable_gap_proxy": None,
        "kell_strength_on_down_day": None,
        "kell_down_market_context": None,
        "kell_rs_divergence": None,
        "kell_name_selection_ok": None,
        "kell_growth_context": growth_context,
        "kell_rs_leader": rs_leader,
        "kell_weekly_trend_ok": None,
        "kell_ema_readiness": None,
        "kell_reversal_extension": None,
        "kell_exhaustion_extension": None,
        "kell_wedge_drop": None,
        "kell_wedge_pop": None,
        "kell_ema_crossback": None,
        "kell_base_n_break": None,
        "kell_tightening": None,
        "kell_ttftl_warning": None,
        "kell_breakout_proximity": None,
        "kell_breakout_proximity_pct": None,
        "kell_cycle_stage": "unavailable",
        "kell_stage": {
            "primary": "unavailable",
            "confidence": 0.0,
            "basis": ["insufficient_history"],
        },
        "kell_screens": [],
        "kell_setups": [],
        "kell_focus": None,
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
    avg_volume20 = sum(volumes[-20:]) / 20.0
    rvol20 = volumes[-1] / vol_base if vol_base > 0 else None
    liquid_screen_base = close > 20.0 and avg_volume20 > 500_000.0
    name_selection_ok = liquid_screen_base

    high_window = bars[-252:] if len(bars) >= 252 else bars
    high_52w = max(float(x["high"]) for x in high_window)
    prior_high_window = bars[-253:-1] if len(bars) >= 253 else []
    prior_52w_high = max((float(x["high"]) for x in prior_high_window), default=None)
    distance_52w = (close / high_52w - 1.0) * 100.0 if high_52w > 0 else None
    new_52w_high: bool | None = (
        float(last["high"]) >= prior_52w_high if prior_52w_high is not None else None
    )
    near_52w = distance_52w is not None and distance_52w >= -3.0

    ret_3m = _return_pct(closes, 63)
    ret_6m = _return_pct(closes, 126)
    ret_ytd = _ytd_return_pct(bars)
    momentum_3m_50 = ret_3m is not None and ret_3m >= 50.0
    doubler_6m = ret_6m is not None and ret_6m >= 100.0
    doubler_ytd = liquid_screen_base and ret_ytd is not None and ret_ytd > 100.0

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
        and dist_e10 is not None and -1.0 <= dist_e10 <= 5.0
    )

    prior10 = bars[-11:-1]
    prior20 = bars[-21:-1]
    prior40 = bars[-41:-1] if len(bars) >= 41 else []
    range10 = _range_pct(prior10)
    range20 = _range_pct(prior20)
    range40 = _range_pct(prior40)
    prior10_high = max((float(x["high"]) for x in prior10), default=None)
    prior20_high = max((float(x["high"]) for x in prior20), default=None)

    tr = [
        _true_range_pct(bars[i], float(bars[i - 1]["close"]))
        for i in range(1, len(bars))
    ]
    recent_tr5 = median(tr[-5:]) if len(tr) >= 5 else None
    prior_tr15_slice = tr[-20:-5] if len(tr) >= 20 else []
    prior_tr15 = median(prior_tr15_slice) if prior_tr15_slice else None
    recent_vol5 = sum(volumes[-5:]) / 5.0 if len(volumes) >= 5 else None
    prior_vol15 = sum(volumes[-20:-5]) / 15.0 if len(volumes) >= 20 else None
    inside_bars_5 = 0
    for i in range(max(1, len(bars) - 5), len(bars)):
        if (
            float(bars[i]["high"]) <= float(bars[i - 1]["high"])
            and float(bars[i]["low"]) >= float(bars[i - 1]["low"])
        ):
            inside_bars_5 += 1
    tr_contracted = (
        recent_tr5 is not None and prior_tr15 is not None and prior_tr15 > 0
        and recent_tr5 <= prior_tr15 * 0.75
    )
    volume_dryup = (
        recent_vol5 is not None and prior_vol15 is not None and prior_vol15 > 0
        and recent_vol5 <= prior_vol15 * 0.85
    )
    tightening = tr_contracted and (volume_dryup or inside_bars_5 >= 2)

    def wedge_event(index: int) -> bool:
        if index < 25 or index >= len(bars):
            return False
        e10_i, e20_i = ema10[index], ema20[index]
        e10_p, e20_p = ema10[index - 1], ema20[index - 1]
        if None in (e10_i, e20_i, e10_p, e20_p):
            return False
        cluster_i = max(float(e10_i), float(e20_i))
        cluster_p = max(float(e10_p), float(e20_p))
        crossed = closes[index] > cluster_i and closes[index - 1] <= cluster_p
        below_count = sum(
            1
            for j in range(index - 5, index)
            if ema10[j] is not None and ema20[j] is not None
            and closes[j] <= max(float(ema10[j]), float(ema20[j]))
        )
        ema_gap_pct = abs(float(e10_i) / float(e20_i) - 1.0) * 100.0 if float(e20_i) > 0 else 999.0
        short_range = _range_pct(bars[index - 5:index])
        long_range = _range_pct(bars[index - 15:index])
        contracted = (
            short_range is not None and long_range is not None and long_range > 0
            and short_range <= long_range * 0.70
        )
        recent_high = max(float(x["high"]) for x in bars[index - 5:index])
        prior_high = max(float(x["high"]) for x in bars[index - 10:index - 5])
        works_lower = recent_high <= prior_high * 1.02
        return crossed and below_count >= 3 and ema_gap_pct <= 1.5 and contracted and works_lower

    wedge_pop = wedge_event(len(bars) - 1)

    # Book-grounded Cycle-of-Price-Action proxies. Kell describes these
    # qualitatively, so the numerical thresholds below are explicit lab proxies.
    sma50 = sum(closes[-50:]) / 50.0 if len(closes) >= 50 else None
    sma200 = sum(closes[-200:]) / 200.0 if len(closes) >= 200 else None
    prior60 = bars[-61:-1] if len(bars) >= 61 else []
    prior60_low = min((float(x["low"]) for x in prior60), default=None)
    support_refs = [value for value in (sma50, sma200, prior60_low) if value not in (None, 0)]
    support_distance_pct = (
        min(abs(float(last["low"]) / float(value) - 1.0) * 100.0 for value in support_refs)
        if support_refs else None
    )
    support_rejection = (
        support_distance_pct is not None and support_distance_pct <= 2.0
        and any(close >= float(value) * 0.995 for value in support_refs)
    )
    downside_extension_pct = (
        (float(last["low"]) / float(e10) - 1.0) * 100.0
        if e10 not in (None, 0) else None
    )
    bullish_reversal_bar = (
        close > float(last["open"])
        and close > prev_close
        and close_location >= 65.0
    )
    reversal_volume = rvol20 is not None and rvol20 >= 1.5
    reversal_extension = bool(
        downside_extension_pct is not None and downside_extension_pct <= -5.0
        and support_rejection
        and bullish_reversal_bar
        and reversal_volume
    )

    def exhaustion_event(index: int) -> bool:
        if index < 25 or index >= len(bars):
            return False
        e10_i = ema10[index]
        if e10_i in (None, 0):
            return False
        row = bars[index]
        row_close = closes[index]
        prev_row_close = closes[index - 1]
        dist = (float(row["high"]) / float(e10_i) - 1.0) * 100.0
        row_range = float(row["high"]) - float(row["low"])
        row_close_location = (
            (row_close - float(row["low"])) / row_range * 100.0
            if row_range > 0 else 50.0
        )
        base_start = max(0, index - 20)
        prior_vols = volumes[base_start:index]
        vol_base_i = sum(prior_vols) / len(prior_vols) if prior_vols else 0.0
        rvol_i = float(row["volume"]) / vol_base_i if vol_base_i > 0 else 0.0
        gap_i = (
            (float(row["open"]) / prev_row_close - 1.0) * 100.0
            if prev_row_close > 0 else 0.0
        )
        recent_highs = [float(x["high"]) for x in bars[max(0, index - 20):index]]
        new_high = not recent_highs or float(row["high"]) >= max(recent_highs)
        tr_reference = median(tr[max(0, index - 6):index]) if index >= 2 and tr[max(0, index - 6):index] else 0.0
        extension_threshold = max(8.0, tr_reference * 3.0)
        blowoff_clue = rvol_i >= 1.5 or gap_i >= 3.0 or row_close_location <= 45.0
        return new_high and dist >= extension_threshold and blowoff_clue

    exhaustion_extension = exhaustion_event(len(bars) - 1)
    recent_exhaustion_index = None
    for i in range(max(25, len(bars) - 16), len(bars) - 1):
        if exhaustion_event(i):
            recent_exhaustion_index = i

    wedge_drop = False
    if recent_exhaustion_index is not None and len(bars) >= 2:
        e10_now, e20_now = ema10[-1], ema20[-1]
        e10_prev, e20_prev = ema10[-2], ema20[-2]
        if None not in (e10_now, e20_now, e10_prev, e20_prev):
            prior_above = closes[-2] >= min(float(e10_prev), float(e20_prev))
            current_below = close < min(float(e10_now), float(e20_now))
            wedge_drop = prior_above and current_below

    recent_pop_index = None
    for i in range(max(25, len(bars) - 16), len(bars) - 1):
        if wedge_event(i):
            recent_pop_index = i

    first_retest = False
    current_touch = False
    current_support = False
    if recent_pop_index is not None and e10 is not None and e20 is not None:
        current_touch = float(last["low"]) <= max(float(e10), float(e20)) * 1.01
        current_support = close >= min(float(e10), float(e20)) * 0.995
        prior_touch = False
        for j in range(recent_pop_index + 1, len(bars) - 1):
            if ema10[j] is None or ema20[j] is None:
                continue
            if float(bars[j]["low"]) <= max(float(ema10[j]), float(ema20[j])) * 1.01:
                prior_touch = True
                break
        first_retest = not prior_touch
    ema_crossback = (
        recent_pop_index is not None
        and first_retest and current_touch and current_support
        and close_location >= 45.0
    )

    base_support_count = 0
    if len(bars) >= 31:
        for j in range(len(bars) - 11, len(bars) - 1):
            if ema20[j] is not None and closes[j] >= float(ema20[j]) * 0.98:
                base_support_count += 1
    base_contracted = (
        range10 is not None and range20 is not None and range20 > 0
        and range10 <= range20 * 0.80
    )
    base_breakout = prior10_high is not None and close > prior10_high
    base_n_break = (
        len(bars) >= 31
        and base_contracted
        and base_support_count >= 8
        and base_breakout
        and close_location >= 55.0
    )

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
        liquid_screen_base
        and unusual_volume
        and ret_1d is not None and ret_1d > 0.0
    )

    gapper = liquid_screen_base and gap_pct is not None and gap_pct > 3.0
    gap_unfilled = gap_pct is not None and gap_pct > 3.0 and float(last["low"]) > prev_close
    buyable_gap_proxy = (
        gapper
        and gap_unfilled
        and prior20_high is not None and float(last["open"]) > prior20_high
        and rvol20 is not None and rvol20 >= 1.5
    )
    gap_held_pct = None
    if gapper and float(last["open"]) > prev_close:
        gap_size = float(last["open"]) - prev_close
        gap_held_pct = (close - prev_close) / gap_size * 100.0 if gap_size > 0 else None

    bench_by_date = {str(x["time"]): float(x["close"]) for x in bench}
    aligned = [
        (bar, bench_by_date[str(bar["time"])])
        for bar in bars
        if str(bar["time"]) in bench_by_date and bench_by_date[str(bar["time"])] > 0
    ]
    benchmark_ret = None
    relative_outperformance = None
    stock_ret20 = None
    benchmark_ret20 = None
    rs_divergence: bool | None = None
    if len(aligned) >= 2:
        stock_prev = float(aligned[-2][0]["close"])
        stock_now = float(aligned[-1][0]["close"])
        bench_prev = float(aligned[-2][1])
        bench_now = float(aligned[-1][1])
        if stock_prev > 0 and bench_prev > 0:
            aligned_stock_ret1 = (stock_now / stock_prev - 1.0) * 100.0
            benchmark_ret = (bench_now / bench_prev - 1.0) * 100.0
            relative_outperformance = aligned_stock_ret1 - benchmark_ret

    estimated_beta = _beta_from_aligned(aligned)
    beta = context_beta if context_beta is not None else estimated_beta
    beta_source = "unified" if context_beta is not None else ("estimated-SPY-126d" if estimated_beta is not None else "unavailable")
    beta_ok: bool | None = beta > 1.0 if beta is not None else None
    screen_52w_high: bool | None = (
        None if new_52w_high is None or beta_ok is None
        else bool(liquid_screen_base and new_52w_high and beta_ok)
    )
    strength_down_day: bool | None = (
        None if beta_ok is None or ret_1d is None
        else bool(liquid_screen_base and beta_ok and ret_1d > 0.0)
    )
    down_market_context: bool | None = (
        benchmark_ret <= -1.0 if benchmark_ret is not None else None
    )

    if len(aligned) >= 21:
        stock_20 = [float(x[0]["close"]) for x in aligned[-21:]]
        bench_20 = [float(x[1]) for x in aligned[-21:]]
        stock_ret20 = (stock_20[-1] / stock_20[0] - 1.0) * 100.0 if stock_20[0] > 0 else None
        benchmark_ret20 = (bench_20[-1] / bench_20[0] - 1.0) * 100.0 if bench_20[0] > 0 else None
        stock_recent_low = min(float(x[0]["low"]) for x in aligned[-10:])
        stock_prior_low = min(float(x[0]["low"]) for x in aligned[-20:-10])
        bench_recent_low = min(float(x[1]) for x in aligned[-10:])
        bench_prior_low = min(float(x[1]) for x in aligned[-20:-10])
        higher_low_vs_lower_low = stock_recent_low > stock_prior_low and bench_recent_low < bench_prior_low
        holds_green_in_correction = (
            benchmark_ret20 is not None and stock_ret20 is not None
            and benchmark_ret20 < 0.0 and stock_ret20 >= 0.0
        )
        rs_divergence = higher_low_vs_lower_low or holds_green_in_correction

    weekly_closes: list[float] = []
    weekly_keys: list[str] = []
    for bar in bars:
        stamp = str(bar["time"])[:10]
        try:
            year, month, day = (int(part) for part in stamp.split("-"))
            import datetime as _dt
            iso = _dt.date(year, month, day).isocalendar()
            key = f"{iso.year}-{iso.week:02d}"
        except (ValueError, TypeError):
            continue
        if weekly_keys and weekly_keys[-1] == key:
            weekly_closes[-1] = float(bar["close"])
        else:
            weekly_keys.append(key)
            weekly_closes.append(float(bar["close"]))
    weekly_ema10_series = _ema(weekly_closes, 10)
    weekly_ema10 = weekly_ema10_series[-1] if weekly_ema10_series else None
    weekly_ema10_3 = weekly_ema10_series[-4] if len(weekly_ema10_series) >= 4 else None
    weekly_trend_ok: bool | None = None
    if weekly_ema10 is not None and weekly_ema10_3 is not None:
        weekly_trend_ok = (
            weekly_closes[-1] >= float(weekly_ema10)
            and float(weekly_ema10) >= float(weekly_ema10_3)
        )

    range15 = _range_pct(bars[-16:-1]) if len(bars) >= 16 else None
    ttftl_warning: bool | None = None
    if range15 is not None and range40 is not None and benchmark_ret20 is not None and stock_ret20 is not None:
        ttftl_warning = (
            range40 > 0 and range15 <= range40 * 0.45
            and stock_ret20 < benchmark_ret20
        )

    bearish_ema_structure = (
        e10 is not None and e20 is not None
        and close < max(float(e10), float(e20))
        and float(e10) < float(e20)
    )
    if reversal_extension:
        cycle_stage = "reversal_extension"
        stage_confidence = 0.85
        stage_basis = ["downside_extension_from_10ema", "higher_timeframe_support_proxy", "bullish_reversal_bar", "heavy_volume_proxy"]
    elif wedge_pop:
        cycle_stage = "wedge_pop"
        stage_confidence = 0.95
        stage_basis = ["wedge_pop_event", "10_20_ema_recapture"]
    elif ema_crossback:
        cycle_stage = "ema_crossback"
        stage_confidence = 0.95
        stage_basis = ["first_retest_after_wedge_pop", "10_20_ema_support"]
    elif base_n_break:
        cycle_stage = "base_n_break"
        stage_confidence = 0.95
        stage_basis = ["base_contraction", "10_20_ema_support", "10d_breakout"]
    elif wedge_drop:
        cycle_stage = "wedge_drop"
        stage_confidence = 0.90
        stage_basis = ["recent_exhaustion_extension_proxy", "10_20_ema_loss"]
    elif exhaustion_extension:
        cycle_stage = "exhaustion_extension"
        stage_confidence = 0.80
        stage_basis = ["extended_from_10ema", "new_20d_high", "blowoff_volume_gap_or_reversal_clue"]
    elif ema_ready:
        cycle_stage = "trend_ema_support"
        stage_confidence = 0.75
        stage_basis = ["price_above_rising_10_20_ema"]
    elif bearish_ema_structure:
        cycle_stage = "downtrend_repair"
        stage_confidence = 0.70
        stage_basis = ["price_below_bearish_10_20_ema"]
    else:
        cycle_stage = "transition"
        stage_confidence = 0.45
        stage_basis = ["mixed_10_20_ema_structure"]

    core_entry_setup = wedge_pop or ema_crossback or base_n_break
    leadership_signal = any((
        screen_52w_high is True,
        bull_snort,
        momentum_3m_50,
        doubler_ytd,
        rs_leader is True,
    ))
    supportive_context = rs_divergence is True or weekly_trend_ok is True
    kell_focus = (
        name_selection_ok
        and (
            (
                buyable_gap_proxy
                and (rs_leader is True or growth_context is True)
            )
            or (
                core_entry_setup
                and supportive_context
                and leadership_signal
                and growth_context is not False
            )
        )
    )

    criteria = {
        "name_selection": _criterion(
            name_selection_ok, WEIGHTS["name_selection"],
            f"price={_fmt(close,2)}; avgVol20={_fmt(avg_volume20,0)}; Screening Guide daily liquidity base: price>20, avgVol20>500k",
        ),
        "growth_context": _criterion(
            growth_context, WEIGHTS["growth_context"],
            (
                f"fundamentalSupport={fundamental_support}; revenueYoY={_fmt(revenue_yoy)}%; epsYoY={_fmt(eps_yoy)}%; book sales-growth anchor=25%"
                if growth_available
                else "Unified fundamental growth evidence unavailable; criterion excluded"
            ),
        ),
        "rs_leader": _criterion(
            rs_leader, WEIGHTS["rs_leader"],
            f"Unified RS rank={_fmt(rs_rank,0)}; leadership proxy threshold=90" if rs_rank is not None else "Unified RS rank unavailable; criterion excluded",
        ),
        "52w_high": _criterion(
            screen_52w_high, WEIGHTS["52w_high"],
            f"new52wHigh={new_52w_high}; price={_fmt(close,2)}; avgVol20={_fmt(avg_volume20,0)}; beta={_fmt(beta,2)} ({beta_source}); guide requires new high, price>20, avgVol20>500k, beta>1",
        ),
        "unusual_volume": _criterion(
            unusual_volume, WEIGHTS["unusual_volume"],
            f"RVOL20={_fmt(rvol20,2)}x; operational threshold=2.0x",
        ),
        "bull_snort": _criterion(
            bull_snort, WEIGHTS["bull_snort"],
            f"guide: price>20, avgVol20>500k, stock up, RVOL20>=2x (3x preferred); price={_fmt(close,2)}; avgVol20={_fmt(avg_volume20,0)}; RVOL20={_fmt(rvol20,2)}x; ret1d={_fmt(ret_1d)}%",
        ),
        "momentum_3m_50": _criterion(
            momentum_3m_50 if ret_3m is not None else None, WEIGHTS["momentum_3m_50"],
            f"ret3m={_fmt(ret_3m)}%; threshold=50%",
        ),
        "doubler_ytd": _criterion(
            doubler_ytd if ret_ytd is not None else None, WEIGHTS["doubler_ytd"],
            f"guide: price>20, avgVol20>500k, YTD>100%; YTD={_fmt(ret_ytd)}%; avgVol20={_fmt(avg_volume20,0)}",
        ),
        "gapper": _criterion(
            gapper, WEIGHTS["gapper"],
            f"guide: price>20, avgVol20>500k, opening gap>3%; gap={_fmt(gap_pct)}%; price={_fmt(close,2)}; avgVol20={_fmt(avg_volume20,0)}",
        ),
        "buyable_gap_proxy": _criterion(
            buyable_gap_proxy, WEIGHTS["buyable_gap_proxy"],
            f"gap={_fmt(gap_pct)}%; unfilled={gap_unfilled}; open>prior20Dhigh={bool(prior20_high and float(last['open'])>prior20_high)}; RVOL20={_fmt(rvol20,2)}x; catalyst not available in OHLCV",
        ),
        "strength_on_down_day": _criterion(
            strength_down_day, WEIGHTS["strength_on_down_day"],
            f"guide screen: price>20, avgVol20>500k, beta>1, stock up; beta={_fmt(beta,2)} ({beta_source}); stock={_fmt(ret_1d)}%; SPY={_fmt(benchmark_ret)}%; severe-down-day context={down_market_context}",
        ),
        "rs_divergence": _criterion(
            rs_divergence, WEIGHTS["rs_divergence"],
            (
                f"stock20={_fmt(stock_ret20)}%; benchmark20={_fmt(benchmark_ret20)}%; structural higher-low/lower-low or green-vs-red correction"
                if benchmark_ret20 is not None
                else "20-session benchmark history unavailable; criterion excluded"
            ),
        ),
        "weekly_trend": _criterion(
            weekly_trend_ok, WEIGHTS["weekly_trend"],
            f"weeklyClose={_fmt(weekly_closes[-1] if weekly_closes else None,2)}; weeklyEMA10={_fmt(weekly_ema10,2)}; rising={bool(weekly_ema10 is not None and weekly_ema10_3 is not None and weekly_ema10>=weekly_ema10_3)}",
        ),
        "ema_readiness": _criterion(
            ema_ready, WEIGHTS["ema_readiness"],
            f"close={_fmt(close,2)}; EMA10={_fmt(e10,2)}; EMA20={_fmt(e20,2)}; distEMA10={_fmt(dist_e10)}%",
        ),
        "wedge_pop": _criterion(
            wedge_pop, WEIGHTS["wedge_pop"],
            "first recapture of a tight 10/20 EMA cluster after several closes at/below the cluster; prior range contracting/working lower",
        ),
        "ema_crossback": _criterion(
            ema_crossback, WEIGHTS["ema_crossback"],
            f"recent_wedge_pop={recent_pop_index is not None}; first_retest={first_retest}; touches_10/20={current_touch}; supported={current_support}",
        ),
        "base_n_break": _criterion(
            base_n_break, WEIGHTS["base_n_break"],
            f"10D base contraction={base_contracted}; support_count={base_support_count}/10; breakout10D={base_breakout}",
        ),
        "tightening": _criterion(
            tightening if recent_tr5 is not None else None, WEIGHTS["tightening"],
            f"TR5={_fmt(recent_tr5)} vs prior15={_fmt(prior_tr15)}; volume_dryup={volume_dryup}; insideBars5={inside_bars_5}",
        ),
        "breakout_proximity": _criterion(
            breakout_proximity, WEIGHTS["breakout_proximity"],
            f"distance_to_prior20D_high={_fmt(breakout_proximity_pct)}%; target=-3.0%..+1.5%",
        ),
    }

    points = sum(x["points"] for x in criteria.values() if x["available"])
    possible = sum(x["max_points"] for x in criteria.values() if x["available"])
    score = round(points / possible * 100.0, 1) if possible else 0.0

    component_groups = {
        "discovery": (
            "rs_leader", "52w_high", "unusual_volume", "bull_snort",
            "momentum_3m_50", "doubler_ytd", "gapper", "strength_on_down_day",
        ),
        "stage": ("weekly_trend", "ema_readiness"),
        "setup": (
            "buyable_gap_proxy", "wedge_pop", "ema_crossback",
            "base_n_break", "tightening", "breakout_proximity",
        ),
        "context": ("name_selection", "growth_context", "rs_divergence"),
    }
    components = {}
    for group_name, group_fields in component_groups.items():
        group_items = [criteria[name] for name in group_fields if name in criteria and criteria[name]["available"]]
        group_points = sum(item["points"] for item in group_items)
        group_possible = sum(item["max_points"] for item in group_items)
        components[group_name] = {
            "points": group_points,
            "possible_points": group_possible,
            "score": round(group_points / group_possible * 100.0, 1) if group_possible else None,
        }

    screen_state = {
        "kell_52w_high": screen_52w_high,
        "kell_unusual_volume": unusual_volume,
        "kell_rvol_3x": rvol_3x,
        "kell_bull_snort": bull_snort,
        "kell_momentum_3m_50": momentum_3m_50 if ret_3m is not None else None,
        "kell_doubler_ytd": doubler_ytd if ret_ytd is not None else None,
        "kell_gapper": gapper,
        "kell_strength_on_down_day": strength_down_day,
        "kell_rs_leader": rs_leader,
    }
    setup_state = {
        "kell_buyable_gap_proxy": buyable_gap_proxy,
        "kell_wedge_pop": wedge_pop,
        "kell_ema_crossback": ema_crossback,
        "kell_base_n_break": base_n_break,
        "kell_tightening": tightening if recent_tr5 is not None else None,
        "kell_breakout_proximity": breakout_proximity,
    }
    kell_screens = [field for field in DISCOVERY_FIELDS if screen_state.get(field) is True]
    kell_setups = [field for field in SETUP_FIELDS if setup_state.get(field) is True]

    return {
        "kell_52w_high": screen_52w_high,
        "kell_unusual_volume": unusual_volume,
        "kell_rvol_3x": rvol_3x,
        "kell_bull_snort": bull_snort,
        "kell_momentum_3m_50": momentum_3m_50 if ret_3m is not None else None,
        "kell_doubler_ytd": doubler_ytd if ret_ytd is not None else None,
        "kell_doubler_6m": doubler_6m if ret_6m is not None else None,
        "kell_doubler": doubler_ytd if ret_ytd is not None else None,
        "kell_gapper": gapper,
        "kell_buyable_gap_proxy": buyable_gap_proxy,
        "kell_strength_on_down_day": strength_down_day,
        "kell_down_market_context": down_market_context,
        "kell_rs_divergence": rs_divergence,
        "kell_name_selection_ok": name_selection_ok,
        "kell_growth_context": growth_context,
        "kell_rs_leader": rs_leader,
        "kell_weekly_trend_ok": weekly_trend_ok,
        "kell_ema_readiness": ema_ready,
        "kell_reversal_extension": reversal_extension,
        "kell_exhaustion_extension": exhaustion_extension,
        "kell_wedge_drop": wedge_drop,
        "kell_wedge_pop": wedge_pop,
        "kell_ema_crossback": ema_crossback,
        "kell_base_n_break": base_n_break,
        "kell_tightening": tightening if recent_tr5 is not None else None,
        "kell_ttftl_warning": ttftl_warning,
        "kell_breakout_proximity": breakout_proximity,
        "kell_breakout_proximity_pct": breakout_proximity_pct,
        "kell_cycle_stage": cycle_stage,
        "kell_stage": {
            "primary": cycle_stage,
            "confidence": stage_confidence,
            "basis": stage_basis,
        },
        "kell_screens": kell_screens,
        "kell_setups": kell_setups,
        "kell_focus": kell_focus,
        "kell_score": score,
        "score_breakdown": {
            "model_version": MODEL_VERSION,
            "points": points,
            "possible_points": possible,
            "criteria": criteria,
            "components": components,
            "warnings": ["too_tight_for_too_long_relative_weakness"] if ttftl_warning is True else [],
        },
        "kell_metrics": {
            "avg_volume20": avg_volume20,
            "rvol_baseline_volume20": vol_base,
            "fundamental_support": fundamental_support,
            "revenue_yoy_pct": revenue_yoy,
            "eps_yoy_pct": eps_yoy,
            "rs_rank": rs_rank,
            "rvol20": rvol20,
            "ret_1d_pct": ret_1d,
            "ret_3m_pct": ret_3m,
            "ret_6m_pct": ret_6m,
            "ret_ytd_pct": ret_ytd,
            "beta": beta,
            "beta_source": beta_source,
            "gap_pct": gap_pct,
            "gap_unfilled": gap_unfilled,
            "gap_held_pct": gap_held_pct,
            "close_location_pct": close_location,
            "distance_to_52w_high_pct": distance_52w,
            "new_52w_high": new_52w_high,
            "ema10": e10,
            "ema20": e20,
            "range10_pct": range10,
            "range20_pct": range20,
            "range40_pct": range40,
            "inside_bars_5": inside_bars_5,
            "tr5_median_pct": recent_tr5,
            "prior_tr15_median_pct": prior_tr15,
            "volume_dryup": volume_dryup,
            "base_support_count": base_support_count,
            "recent_wedge_pop_sessions_ago": (len(bars) - 1 - recent_pop_index) if recent_pop_index is not None else None,
            "breakout_proximity_pct": breakout_proximity_pct,
            "benchmark_ret_1d_pct": benchmark_ret,
            "relative_outperformance_pct": relative_outperformance,
            "stock_ret_20d_pct": stock_ret20,
            "benchmark_ret_20d_pct": benchmark_ret20,
            "weekly_ema10": weekly_ema10,
            "sma50": sma50,
            "sma200": sma200,
            "prior60_low": prior60_low,
            "support_distance_pct": support_distance_pct,
            "downside_extension_pct": downside_extension_pct,
            "recent_exhaustion_sessions_ago": (len(bars) - 1 - recent_exhaustion_index) if recent_exhaustion_index is not None else None,
        },
    }


def enrich_snapshot(snapshot: dict, benchmark_rows: list | None = None) -> dict:
    """Enrich an existing snapshot in-place without adding/removing/reordering candidates."""
    candidates = snapshot.get("candidates") or []
    original_tickers = [str(item.get("ticker") or "") for item in candidates]
    for item in candidates:
        item.update(score_candidate(item.get("chartBars") or [], benchmark_rows, item))
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
