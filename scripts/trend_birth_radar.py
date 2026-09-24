#!/usr/bin/env python3
"""Transparent 0/4 -> 4/4 trend-birth stage overlay.

This module intentionally stays separate from Kell v5 scoring.  It answers a
simpler question: how far has a candidate progressed through a trend-reset ->
restart sequence?
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Iterable

STAGE_LABELS = {
    0: "NO SETUP / INVALIDATED",
    1: "WATCH",
    2: "WATCH CLOSELY",
    3: "READY",
    4: "TRIGGER",
}

CHECK_LABELS = (
    ("sma50Rising", "SMA50 rising"),
    ("sma30wRising", "SMA30W rising"),
    ("structureValid", "Structure valid"),
    ("notExtended", "Not extended"),
    ("recentPullbackCompression", "Recent pullback + EMA compression"),
    ("ema10Rising", "EMA10 rising"),
    ("ema20NonFalling", "EMA20 non-falling"),
    ("ema10AboveEma20", "EMA10 > EMA20"),
    ("closeAboveShortEmas", "Close > EMA10 & EMA20"),
    ("bullishReexpansion", "Bullish EMA re-expansion"),
)


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def normalize_bars(rows: Iterable) -> list[dict]:
    bars: list[dict] = []
    for row in rows or []:
        if isinstance(row, list) and len(row) >= 6:
            source = {
                "time": row[0],
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5],
            }
        elif isinstance(row, dict):
            source = row
        else:
            continue
        open_ = _finite(source.get("open"))
        high = _finite(source.get("high"))
        low = _finite(source.get("low"))
        close = _finite(source.get("close"))
        if None in (open_, high, low, close):
            continue
        stamp = str(source.get("time") or source.get("date") or "")
        bars.append({
            "time": stamp,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": _finite(source.get("volume")) or 0.0,
        })
    return bars


def _ema(values: list[float], length: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (length + 1.0)
    out = [values[0]]
    for value in values[1:]:
        out.append(alpha * value + (1.0 - alpha) * out[-1])
    return out


def _sma(values: list[float], length: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    total = 0.0
    for index, value in enumerate(values):
        total += value
        if index >= length:
            total -= values[index - length]
        if index >= length - 1:
            out[index] = total / length
    return out


def _wilder_atr(bars: list[dict], length: int = 14) -> list[float | None]:
    tr: list[float] = []
    for index, bar in enumerate(bars):
        previous_close = bars[index - 1]["close"] if index else bar["close"]
        tr.append(max(
            bar["high"] - bar["low"],
            abs(bar["high"] - previous_close),
            abs(bar["low"] - previous_close),
        ))
    out: list[float | None] = [None] * len(tr)
    current = None
    for index, value in enumerate(tr):
        current = value if current is None else ((length - 1) * current + value) / length
        if index >= length - 1:
            out[index] = current
    return out


def _parse_day(value):
    if isinstance(value, (int, float)):
        stamp = float(value)
        if stamp > 1_000_000_000_000:
            stamp /= 1000.0
        try:
            return datetime.fromtimestamp(stamp, tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None

    text = str(value or "").strip()
    try:
        stamp = float(text)
    except ValueError:
        stamp = None
    if stamp is not None:
        if stamp > 1_000_000_000_000:
            stamp /= 1000.0
        try:
            return datetime.fromtimestamp(stamp, tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None

    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _completed_weekly_closes(bars: list[dict]) -> list[float]:
    """Aggregate daily closes by ISO week and ignore an unfinished current week."""
    weeks: list[tuple[object, object, float]] = []
    current_key = None
    for bar in bars:
        day = _parse_day(bar["time"])
        if day is None:
            continue
        iso = day.isocalendar()
        key = (iso.year, iso.week)
        if key != current_key:
            weeks.append((key, day, bar["close"]))
            current_key = key
        else:
            weeks[-1] = (key, day, bar["close"])
    if weeks and weeks[-1][1].weekday() < 4:
        weeks = weeks[:-1]
    return [close for _, _, close in weeks]


def _slope(series: list[float], atr: float, lookback: int = 3) -> float | None:
    if len(series) <= lookback or atr <= 0:
        return None
    return (series[-1] - series[-1 - lookback]) / (lookback * atr)


def evaluate_trend_birth(rows: Iterable) -> dict:
    bars = normalize_bars(rows)
    empty = {
        "stage": 0,
        "stageLabel": STAGE_LABELS[0],
        "available": False,
        "checks": {key: False for key, _ in CHECK_LABELS},
        "metrics": {},
        "missingFor4": [label for _, label in CHECK_LABELS],
    }
    if len(bars) < 170:
        return {**empty, "reason": "insufficient_daily_history"}

    closes = [bar["close"] for bar in bars]
    ema10 = _ema(closes, 10)
    ema20 = _ema(closes, 20)
    sma50 = _sma(closes, 50)
    atr14 = _wilder_atr(bars, 14)

    weekly_close = _completed_weekly_closes(bars)
    sma30w = _sma(weekly_close, 30)
    if (
        len(sma30w) < 35
        or sma30w[-1] is None
        or sma30w[-5] is None
        or sma50[-1] is None
        or sma50[-6] is None
        or atr14[-1] is None
    ):
        return {**empty, "reason": "insufficient_weekly_history"}

    price = closes[-1]
    atr = float(atr14[-1])
    if atr <= 0:
        return {**empty, "reason": "invalid_atr"}

    e10_slope = _slope(ema10, atr)
    e20_slope = _slope(ema20, atr)
    if e10_slope is None or e20_slope is None:
        return {**empty, "reason": "insufficient_slope_history"}

    sma50_rising = float(sma50[-1]) > float(sma50[-6])
    sma30w_rising = float(sma30w[-1]) > float(sma30w[-5])
    structure_valid = price >= float(sma50[-1]) - 1.50 * atr
    not_extended = price <= ema20[-1] + 1.50 * atr

    near_series: list[bool] = []
    compression_series: list[bool] = []
    not_extended_series: list[bool] = []
    for index, close in enumerate(closes):
        if sma50[index] is None or atr14[index] is None or float(atr14[index]) <= 0:
            near_series.append(False)
            compression_series.append(False)
            not_extended_series.append(False)
            continue
        bar_atr = float(atr14[index])
        near_series.append(
            float(sma50[index]) - 0.75 * bar_atr
            <= close
            <= float(sma50[index]) + 1.25 * bar_atr
        )
        compression_series.append(abs(ema10[index] - ema20[index]) <= 0.35 * bar_atr)
        not_extended_series.append(close <= ema20[index] + 1.50 * bar_atr)

    recent_pullback_compression = any(
        near and compressed and sane
        for near, compressed, sane in zip(
            near_series[-10:],
            compression_series[-10:],
            not_extended_series[-10:],
        )
    )
    ema10_flattening = e10_slope >= -0.05
    ema20_flattening = e20_slope >= -0.03
    one_short_ema_rising = e10_slope > 0 or e20_slope > 0
    ema10_rising = e10_slope > 0
    ema20_non_falling = e20_slope >= 0
    ema10_above_ema20 = ema10[-1] > ema20[-1]
    close_above_short_emas = price > ema10[-1] and price > ema20[-1]
    spread = [left - right for left, right in zip(ema10, ema20)]
    fresh_cross = ema10[-1] > ema20[-1] and ema10[-2] <= ema20[-2]
    widening_positive_spread = spread[-1] > 0 and spread[-1] > spread[-2]
    bullish_reexpansion = fresh_cross or widening_positive_spread

    trend_ok = sma50_rising and sma30w_rising and structure_valid and not_extended
    watch_closely = trend_ok and near_series[-1] and compression_series[-1]
    ready = (
        watch_closely
        and ema10_flattening
        and ema20_flattening
        and one_short_ema_rising
    )
    trigger = (
        trend_ok
        and recent_pullback_compression
        and ema10_rising
        and ema20_non_falling
        and ema10_above_ema20
        and close_above_short_emas
        and bullish_reexpansion
    )

    stage = 4 if trigger else 3 if ready else 2 if watch_closely else 1 if trend_ok else 0
    checks = {
        "sma50Rising": sma50_rising,
        "sma30wRising": sma30w_rising,
        "structureValid": structure_valid,
        "notExtended": not_extended,
        "priceNearSma50": near_series[-1],
        "emaCompressed": compression_series[-1],
        "recentPullbackCompression": recent_pullback_compression,
        "ema10FlatteningOrRising": ema10_flattening,
        "ema20FlatteningOrRising": ema20_flattening,
        "oneShortEmaRising": one_short_ema_rising,
        "ema10Rising": ema10_rising,
        "ema20NonFalling": ema20_non_falling,
        "ema10AboveEma20": ema10_above_ema20,
        "closeAboveShortEmas": close_above_short_emas,
        "bullishReexpansion": bullish_reexpansion,
    }
    missing = [label for key, label in CHECK_LABELS if not checks.get(key, False)]

    return {
        "stage": stage,
        "stageLabel": STAGE_LABELS[stage],
        "available": True,
        "barDate": bars[-1]["time"][:10],
        "checks": checks,
        "metrics": {
            "price": price,
            "atr14": atr,
            "ema10": ema10[-1],
            "ema20": ema20[-1],
            "sma50": sma50[-1],
            "sma30w": sma30w[-1],
            "distanceSma50Atr": (price - float(sma50[-1])) / atr,
            "emaSpreadAtr": abs(ema10[-1] - ema20[-1]) / atr,
            "ema10SlopeAtrDay": e10_slope,
            "ema20SlopeAtrDay": e20_slope,
        },
        "missingFor4": missing,
    }


def candidate_priority(item: dict) -> tuple:
    """Transparent ordering for alert/display use; stage remains independent."""
    radar = item.get("trendBirth") or {}
    return (
        int(radar.get("stage") or 0),
        float(item.get("kell_score") or 0.0),
        float(item.get("kell_readiness_score") or 0.0),
        float(item.get("kell_quality_score") or 0.0),
        str(item.get("ticker") or ""),
    )
