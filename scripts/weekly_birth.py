"""Point-in-time weekly structure for early trend discovery.

All measurements come from completed weekly OHLCV bars. The output exposes
reasons and raw measurements so a reviewer can disagree with the ranking.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from statistics import median
from typing import Iterable

LABELS = {0: "Rejected", 1: "Long Base", 2: "Compressed", 3: "Ready", 4: "Trigger"}


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _date(value):
    if isinstance(value, (int, float)) or str(value or "").isdigit():
        stamp = float(value)
        if stamp > 1_000_000_000_000:
            stamp /= 1000
        try:
            return datetime.fromtimestamp(stamp, timezone.utc).date()
        except (ValueError, OverflowError, OSError):
            return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def completed_weekly_bars(rows: Iterable) -> list[dict]:
    weeks: list[dict] = []
    for raw in rows or []:
        if isinstance(raw, (list, tuple)) and len(raw) >= 6:
            stamp, opened, high, low, close, volume = raw[:6]
        elif isinstance(raw, dict):
            stamp = raw.get("time") or raw.get("date")
            opened, high, low, close, volume = (
                raw.get("open"), raw.get("high"), raw.get("low"), raw.get("close"), raw.get("volume")
            )
        else:
            continue
        day = _date(stamp)
        values = [_number(value) for value in (opened, high, low, close)]
        if day is None or any(value is None or value <= 0 for value in values):
            continue
        opened, high, low, close = values
        key = (day.isocalendar().year, day.isocalendar().week)
        if weeks and weeks[-1]["key"] == key:
            week = weeks[-1]
            week["high"] = max(week["high"], high)
            week["low"] = min(week["low"], low)
            week["close"] = close
            week["volume"] += _number(volume) or 0
            week["lastDay"] = day
        else:
            weeks.append({
                "key": key, "time": day.isoformat(), "lastDay": day,
                "open": opened, "high": high, "low": low, "close": close,
                "volume": _number(volume) or 0,
            })
    # A Monday-Thursday terminal week has not settled. Earlier weeks are complete
    # because a later week's bar is present.
    if weeks and weeks[-1]["lastDay"].weekday() < 4:
        weeks.pop()
    return weeks


def _ema(values: list[float], length: int) -> float:
    alpha = 2 / (length + 1)
    current = values[0]
    for value in values[1:]:
        current = alpha * value + (1 - alpha) * current
    return current


def _sma(values: list[float], length: int) -> float:
    return sum(values[-length:]) / length


def _base(weeks: list[dict]) -> tuple[int, float, float, int, float] | None:
    """Choose the longest recent nontrending range; keep the last 8 weeks as a launch window."""
    highs = [week["high"] for week in weeks]
    high_prefix = [0]
    for index, high in enumerate(highs):
        new_high = index >= 26 and high > max(highs[index - 26:index]) * 1.001
        high_prefix.append(high_prefix[-1] + int(new_high))
    for length in range(min(104, len(weeks) - 1), 51, -1):
        window = weeks[-length:]
        floor = min(bar["low"] for bar in window)
        ceiling = max(bar["high"] for bar in window[:-8])
        depth = 100 * (ceiling - floor) / ceiling
        drift = 100 * abs(window[-9]["close"] / window[0]["close"] - 1)
        base_closes = [bar["close"] for bar in window[:-8]]
        total_move = sum(abs(right - left) for left, right in zip(base_closes, base_closes[1:]))
        efficiency = abs(base_closes[-1] - base_closes[0]) / total_move if total_move else 0
        start = len(weeks) - length
        new_high_weeks = high_prefix[len(weeks) - 8] - high_prefix[start + 26]
        # A two-year climb that merely pauses near its high is not a base.
        if 0 <= depth <= 35 and drift <= 15 and new_high_weeks <= 3 and efficiency <= 0.45:
            return length, depth, ceiling, new_high_weeks, efficiency
    return None


def _resistance(weeks: list[dict], base_weeks: int, pivot: float) -> float | None:
    older = weeks[:-base_weeks]
    if not older:
        return None
    highs = [bar["high"] for bar in older]
    # Local swing highs approximate overhead supply without asserting who traded.
    swings = [
        highs[index] for index in range(2, len(highs) - 2)
        if highs[index] >= max(highs[index - 2:index] + highs[index + 1:index + 3])
    ]
    above = sorted(high for high in swings if high > pivot * 1.01)
    return above[0] if above else None


def evaluate_weekly_birth(rows: Iterable) -> dict:
    weeks = completed_weekly_bars(rows)
    rejected = {
        "stage": 0, "stageLabel": LABELS[0], "eligible": False,
        "score": 0, "checks": {}, "metrics": {}, "rejectReasons": [],
    }
    if len(weeks) < 156:
        return {**rejected, "rejectReasons": ["weekly_history_under_156_weeks"]}
    base = _base(weeks)
    if base is None:
        return {**rejected, "rejectReasons": ["no_recent_52_to_104_week_base"]}

    base_weeks, depth, pivot, new_high_weeks, base_efficiency = base
    closes = [bar["close"] for bar in weeks]
    price = closes[-1]
    ma = {
        "ema10w": _ema(closes, 10),
        "ema20w": _ema(closes, 20),
        "sma30w": _sma(closes, 30),
        "sma40w": _sma(closes, 40),
    }
    ma_spread = 100 * (max(ma.values()) - min(ma.values())) / price
    ma_center = median(ma.values())
    extension = 100 * (price / ma_center - 1)
    slope30 = 100 * (_sma(closes, 30) / _sma(closes[:-4], 30) - 1)
    resistance = _resistance(weeks, base_weeks, pivot)
    runway = 100 * (resistance / pivot - 1) if resistance else None
    # A close above the pre-launch pivot is a fresh first attempt only when
    # it happened within the eight-week launch window.
    launch = closes[-8:]
    prelaunch = closes[-34:-8]
    recent_range = 100 * (max(prelaunch) - min(prelaunch)) / max(prelaunch)
    launch_advance = 100 * (price / prelaunch[-1] - 1)
    crossings = [index for index, close in enumerate(launch) if close > pivot and (index == 0 or launch[index - 1] <= pivot)]
    breakout_age = 7 - crossings[-1] if crossings else None
    near_pivot = -5 <= 100 * (price / pivot - 1) <= 0
    checks = {
        "longBase": base_weeks >= 52,
        "baseDepthOk": depth <= 35,
        "weeklyMaCompressed": ma_spread <= 6,
        "weeklyMaNear": ma_spread <= 8,
        "recentBaseTight": recent_range <= 18,
        "maSlopeTurn": slope30 >= -0.5,
        "aboveSma30w": price >= ma["sma30w"],
        "notExtended": extension <= 12,
        "launchNotChased": launch_advance <= 12,
        "clearRunway": runway is None or runway >= 12,
        "nearPivot": near_pivot,
        "freshBreakout": breakout_age is not None and breakout_age <= 8 and price > pivot,
    }
    reasons = [key for key in (
        "longBase", "baseDepthOk", "weeklyMaNear", "recentBaseTight",
        "maSlopeTurn", "aboveSma30w", "notExtended", "launchNotChased", "clearRunway",
    ) if not checks[key]]
    stage = 0
    if checks["longBase"] and checks["baseDepthOk"] and checks["clearRunway"]:
        stage = 1
        if all(checks[key] for key in ("weeklyMaCompressed", "recentBaseTight", "maSlopeTurn", "aboveSma30w", "notExtended", "launchNotChased")):
            stage = 2
            if near_pivot:
                stage = 3
            elif checks["freshBreakout"]:
                stage = 4
    score = round(
        min(base_weeks, 104) / 104 * 25
        + max(0, 1 - ma_spread / 8) * 25
        + (20 if checks["clearRunway"] else 0)
        + (15 if checks["maSlopeTurn"] and checks["aboveSma30w"] else 0)
        + (15 if checks["nearPivot"] or checks["freshBreakout"] else 0), 1,
    )
    return {
        "stage": stage, "stageLabel": LABELS[stage], "eligible": stage >= 2 and checks["notExtended"],
        "score": score, "checks": checks,
        "metrics": {
            "baseWeeks": base_weeks, "baseDepthPct": round(depth, 2),
            "baseNewHighWeeks": new_high_weeks,
            "baseEfficiency": round(base_efficiency, 3),
            "recentBaseRangePct26w": round(recent_range, 2),
            "launchAdvancePct8w": round(launch_advance, 2),
            "weeklyMaClusterPct": round(ma_spread, 2),
            "maSlope30wPct4w": round(slope30, 2),
            "pivotPrice": round(pivot, 4), "resistancePrice": round(resistance, 4) if resistance else None,
            "runwayPct": round(runway, 2) if runway is not None else None,
            "extensionPct": round(extension, 2), "weeksSinceBreakout": breakout_age,
            **{key: round(value, 4) for key, value in ma.items()},
        },
        "rejectReasons": reasons,
    }


def weekly_shortlist(items: Iterable[dict], limit: int = 15) -> list[dict]:
    selected = [item for item in items if (item.get("weeklyBirth") or {}).get("eligible")]
    selected.sort(key=lambda item: (
        -(item["weeklyBirth"]["stage"]),
        -float(item["weeklyBirth"]["score"]),
        str(item.get("ticker") or ""),
    ))
    return selected[:limit]
