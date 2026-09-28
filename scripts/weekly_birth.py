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
MODEL_VERSION = "weinstein-stage2a-v4-bottom-crash"


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


def completed_weekly_bars(rows: Iterable, benchmark_rows: Iterable | None = None) -> list[dict]:
    benchmark = {}
    for row in benchmark_rows or []:
        if isinstance(row, (list, tuple)) and len(row) >= 5:
            day, close = _date(row[0]), _number(row[4])
        elif isinstance(row, dict):
            day = _date(row.get("time") or row.get("date"))
            close = _number(row.get("close"))
        else:
            continue
        if day and close and close > 0:
            benchmark[day] = close
    weeks: list[dict] = []
    for raw in rows or []:
        if isinstance(raw, (list, tuple)) and len(raw) >= 6:
            stamp, opened, high, low, close, volume = raw[:6]
            embedded_rs = _number(raw[6]) if len(raw) >= 7 else None
        elif isinstance(raw, dict):
            stamp = raw.get("time") or raw.get("date")
            opened, high, low, close, volume = (
                raw.get("open"), raw.get("high"), raw.get("low"), raw.get("close"), raw.get("volume")
            )
            embedded_rs = _number(raw.get("rs") or raw.get("relativeStrength") or raw.get("relative_strength"))
        else:
            continue
        day = _date(stamp)
        values = [_number(value) for value in (opened, high, low, close)]
        if day is None or any(value is None or value <= 0 for value in values):
            continue
        opened, high, low, close = values
        spy_close = benchmark.get(day)
        rs_ratio = embedded_rs if embedded_rs and embedded_rs > 0 else (
            close / spy_close * 100 if spy_close else None
        )
        key = (day.isocalendar().year, day.isocalendar().week)
        if weeks and weeks[-1]["key"] == key:
            week = weeks[-1]
            week["high"] = max(week["high"], high)
            week["low"] = min(week["low"], low)
            week["close"] = close
            week["volume"] += _number(volume) or 0
            week["lastDay"] = day
            week["rsRatio"] = rs_ratio
        else:
            weeks.append({
                "key": key, "time": day.isoformat(), "lastDay": day,
                "open": opened, "high": high, "low": low, "close": close,
                "volume": _number(volume) or 0,
                "rsRatio": rs_ratio,
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
    for length in range(min(130, len(weeks) - 1), 38, -1):
        window = weeks[-length:]
        floor = min(bar["low"] for bar in window)
        ceiling = max(bar["high"] for bar in window[:-8])
        depth = 100 * (ceiling - floor) / ceiling
        drift = 100 * abs(window[-9]["close"] / window[0]["close"] - 1)
        base_closes = [bar["close"] for bar in window[:-8]]
        total_move = sum(abs(right - left) for left, right in zip(base_closes, base_closes[1:]))
        efficiency = abs(base_closes[-1] - base_closes[0]) / total_move if total_move else 0
        start = len(weeks) - length
        new_high_weeks = high_prefix[len(weeks) - 8] - high_prefix[min(len(weeks) - 8, start + 26)]
        # A two-year climb that merely pauses near its high is not a base.
        if 0 <= depth <= 50 and drift <= 20 and new_high_weeks <= 3 and efficiency <= 0.45:
            return length, depth, ceiling, new_high_weeks, efficiency
    return None


def _resistance(weeks: list[dict], pivot: float) -> float | None:
    # Nearby swing highs belong to the entry/pivot zone. Counting each one as
    # a separate overhead wall made a dense base look like it had no runway.
    # The next supply zone starts more than 6% beyond the pivot. Older highs
    # still count, including those from before a crash.
    highs = [bar["high"] for bar in weeks[:-1]]
    # Local swing highs approximate overhead supply without asserting who traded.
    swings = [
        highs[index] for index in range(2, len(highs) - 2)
        if highs[index] >= max(highs[index - 2:index] + highs[index + 1:index + 3])
    ]
    # A five-year window can begin at the old crash peak; do not erase that
    # supply level merely because the local-swing test lacks left neighbors.
    swings.extend((max(highs[:2]), max(highs[-2:])))
    above = sorted(high for high in swings if high > pivot * 1.06)
    return above[0] if above else None


def _crash_base(weeks: list[dict], evidence: dict) -> tuple[int, float, float, int, float] | None:
    """Use Bottom's detected secular age, but measure today's local launch shelf ourselves."""
    if evidence.get("crashBaseTriggered") is not True:
        return None
    age = _number(evidence.get("crashBaseAgeWeeks"))
    drawdown = _number(evidence.get("crashBaseDrawdown5yPct"))
    if age is None or age < 52 or drawdown is None or drawdown < 35:
        return None
    shelf = weeks[-34:-8]
    pivot = max(bar["high"] for bar in shelf)
    floor = min(bar["low"] for bar in shelf)
    depth = 100 * (pivot - floor) / pivot
    closes = [bar["close"] for bar in shelf]
    highs = [bar["high"] for bar in shelf]
    new_high_weeks = sum(
        high > max(highs[index - 13:index]) * 1.001
        for index, high in enumerate(highs) if index >= 13
    )
    move = sum(abs(right - left) for left, right in zip(closes, closes[1:]))
    efficiency = abs(closes[-1] - closes[0]) / move if move else 0
    # The secular crash can be deep, but the current 26-week shelf must have
    # stopped trending down. Its own depth is reported separately from the
    # Bottom detector's full multi-year base.
    if depth > 45 or efficiency > 0.5 or new_high_weeks > 3:
        return None
    return int(age), depth, pivot, new_high_weeks, efficiency


def _mansfield_rs(weeks: list[dict]) -> tuple[float | None, float | None]:
    ratios = [bar.get("rsRatio") for bar in weeks]
    if len(ratios) < 56 or any(value is None or value <= 0 for value in ratios[-56:]):
        return None, None
    def reading(end: int) -> float:
        window = ratios[end - 52:end]
        return 100 * (window[-1] / (sum(window) / 52) - 1)
    latest = reading(len(ratios))
    return latest, latest - reading(len(ratios) - 4)


def evaluate_weekly_birth(
    rows: Iterable,
    benchmark_rows: Iterable | None = None,
    *,
    bottom_evidence: dict | None = None,
    chart_source: str | None = None,
) -> dict:
    weeks = completed_weekly_bars(rows, benchmark_rows)
    bottom_evidence = bottom_evidence or {}
    crash_age = _number(bottom_evidence.get("crashBaseAgeWeeks"))
    crash_drawdown = _number(bottom_evidence.get("crashBaseDrawdown5yPct"))
    rejected = {
        "modelVersion": MODEL_VERSION, "stage": 0, "stageLabel": LABELS[0], "eligible": False,
        "score": 0, "checks": {},
        "metrics": {
            "bottomCrashBaseTriggered": bottom_evidence.get("crashBaseTriggered") is True,
            "bottomCrashBaseAgeWeeks": crash_age,
            "bottomCrashDrawdown5yPct": crash_drawdown,
        },
        "rejectReasons": [],
        "chartSource": chart_source,
    }
    if len(weeks) < 156:
        return {**rejected, "rejectReasons": ["weekly_history_under_156_weeks"]}
    base = _base(weeks)
    base_kind = "measured-range"
    if base is None:
        base = _crash_base(weeks, bottom_evidence)
        base_kind = "bottom-crash-recovery"
    if base is None:
        if bottom_evidence.get("crashBaseTriggered") is True:
            reason = (
                "bottom_crash_age_under_52_weeks" if crash_age is None or crash_age < 52 else
                "bottom_crash_drawdown_under_35_pct" if crash_drawdown is None or crash_drawdown < 35 else
                "bottom_crash_no_current_shelf"
            )
        else:
            reason = "no_recent_39_to_130_week_base"
        return {**rejected, "rejectReasons": [reason]}

    base_weeks, depth, pivot, new_high_weeks, base_efficiency = base
    closes = [bar["close"] for bar in weeks]
    price = closes[-1]
    base_start = len(closes) - base_weeks
    prebase_slope30_26w = (
        100 * (_sma(closes[:base_start], 30) / _sma(closes[:base_start - 26], 30) - 1)
        if base_start >= 56 else None
    )
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
    prior_slope30 = 100 * (_sma(closes[:-4], 30) / _sma(closes[:-8], 30) - 1)
    prior_slope30_13w = 100 * (_sma(closes[:-4], 30) / _sma(closes[:-17], 30) - 1)
    rs, rs_change = _mansfield_rs(weeks)
    resistance = _resistance(weeks, pivot)
    runway = 100 * (resistance / max(price, pivot) - 1) if resistance else None
    runway_from_price = 100 * (resistance / price - 1) if resistance else None
    # "Blue sky" is meaningful only at the prospective entry pivot. If price
    # sits far below an old base ceiling, intervening highs remain overhead.
    blue_sky = resistance is None and len(weeks) >= 156 and price >= pivot * 0.92
    crash_prebreakout_runway = (
        bottom_evidence.get("crashBaseTriggered") is True
        and -8 <= 100 * (price / pivot - 1) <= 0
        and runway_from_price is not None and runway_from_price >= 12
    )
    runway_basis = (
        "blue-sky" if blue_sky else
        "pivot" if runway is not None and runway >= 12 else
        "price-before-pivot" if crash_prebreakout_runway else
        "insufficient"
    )
    prior_volumes = [bar["volume"] for bar in weeks[-5:-1]]
    volume_ratio = (weeks[-1]["volume"] / (sum(prior_volumes) / 4)
                    if len(prior_volumes) == 4 and sum(prior_volumes) > 0 else None)
    # A close above the pre-launch pivot is a fresh first attempt only when
    # it happened within the eight-week launch window.
    launch = closes[-8:]
    prelaunch = closes[-34:-8]
    recent_range26 = 100 * (max(prelaunch) - min(prelaunch)) / max(prelaunch)
    tight_prelaunch = closes[-20:-8]
    recent_range = 100 * (max(tight_prelaunch) - min(tight_prelaunch)) / max(tight_prelaunch)
    launch_advance = 100 * (price / prelaunch[-1] - 1)
    crossings = [index for index, close in enumerate(launch) if close > pivot and (index == 0 or launch[index - 1] <= pivot)]
    breakout_age = 7 - crossings[-1] if crossings else None
    near_pivot = -5 <= 100 * (price / pivot - 1) <= 0
    crash_source = bottom_evidence.get("crashBaseTriggered") is True
    rs_improving = rs is not None and rs_change is not None and (
        (rs >= 0 and rs_change >= 0.25) or (rs >= -2 and rs_change >= 1)
    )
    crash_rs_repair = crash_source and rs is not None and rs_change is not None and rs >= -5 and rs_change >= 0.25
    ma_turn = slope30 >= -0.25 and prior_slope30 <= 1 and (
        slope30 - prior_slope30 >= 0.15 or (abs(prior_slope30) <= 0.5 and slope30 >= 0)
    )
    checks = {
        "longBase": base_weeks >= 39,
        "baseDepthOk": depth <= 50,
        "weeklyMaCompressed": ma_spread <= 6,
        "weeklyMaNear": ma_spread <= 8,
        "recentBaseTight": recent_range <= 14,
        "maSlopeTurn": ma_turn,
        "maPrior13wFlat": prior_slope30_13w <= 4,
        "priorBaseTrendQuiet": prebase_slope30_26w is None or prebase_slope30_26w <= 8,
        "mansfieldRsImproving": rs_improving,
        "breakoutVolumeConfirmed": volume_ratio is not None and volume_ratio >= 2,
        "aboveSma30w": price >= ma["sma30w"],
        "notExtended": -6 <= extension <= 10,
        "launchNotChased": launch_advance <= 10,
        "clearRunway": runway_basis != "insufficient",
        "nearPivot": near_pivot,
        "freshBreakout": breakout_age is not None and breakout_age <= 2 and price > pivot,
    }
    checks["earlyBreakoutOrPrebreakout"] = price <= pivot or (
        checks["freshBreakout"] and checks["breakoutVolumeConfirmed"]
    )
    reasons = [key for key in (
        "longBase", "baseDepthOk", "weeklyMaNear", "recentBaseTight",
        "maSlopeTurn", "maPrior13wFlat", "priorBaseTrendQuiet", "mansfieldRsImproving", "aboveSma30w", "notExtended", "launchNotChased", "clearRunway",
        "earlyBreakoutOrPrebreakout",
    ) if not checks[key]]
    stage = 0
    if checks["longBase"] and checks["baseDepthOk"] and checks["clearRunway"]:
        stage = 1
        if all(checks[key] for key in ("weeklyMaCompressed", "recentBaseTight", "maSlopeTurn", "maPrior13wFlat", "priorBaseTrendQuiet", "mansfieldRsImproving", "aboveSma30w", "notExtended", "launchNotChased")):
            stage = 2
            if near_pivot:
                stage = 3
            elif checks["freshBreakout"] and checks["breakoutVolumeConfirmed"]:
                stage = 4
    checks["stage1Watch"] = (
        stage == 1 and checks["weeklyMaCompressed"]
        and recent_range <= 10 and -6 <= extension <= 6
        and checks["launchNotChased"]
        and price <= pivot
        and rs is not None and rs_change is not None
        and rs >= -4 and rs_change >= 0.5
        and slope30 >= -0.5 and prior_slope30 <= 1
        and checks["maPrior13wFlat"]
        and checks["priorBaseTrendQuiet"]
    )
    checks["crashBaseWatch"] = (
        crash_source and stage >= 1 and price <= pivot
        and -8 <= 100 * (price / pivot - 1)
        and ma_spread <= 8 and recent_range <= 14
        and -6 <= extension <= 6 and checks["launchNotChased"]
        and checks["aboveSma30w"] and crash_rs_repair
        and -0.5 <= slope30 <= 1.5 and prior_slope30 <= 0.75
        and checks["maPrior13wFlat"]
        and checks["priorBaseTrendQuiet"]
    )
    score = round(
        min(base_weeks, 104) / 104 * 20
        + max(0, 1 - ma_spread / 8) * 20
        + (20 if checks["clearRunway"] else 0)
        + (15 if checks["maSlopeTurn"] and checks["aboveSma30w"] else 0)
        + (15 if checks["mansfieldRsImproving"] else 0)
        + (10 if checks["nearPivot"] or checks["freshBreakout"] else 0)
        + (5 if checks["breakoutVolumeConfirmed"] else 0), 1,
    )
    eligible = (
        (stage >= 2 and checks["notExtended"] and checks["earlyBreakoutOrPrebreakout"])
        or checks["stage1Watch"] or checks["crashBaseWatch"]
    )
    return {
        "modelVersion": MODEL_VERSION, "stage": stage, "stageLabel": LABELS[stage],
        "eligible": eligible,
        "score": score, "checks": checks,
        "chartSource": chart_source,
        "metrics": {
            "baseKind": base_kind,
            "localShelfWeeks": 26 if base_kind == "bottom-crash-recovery" else None,
            "bottomCrashBaseTriggered": crash_source,
            "bottomCrashBaseAgeWeeks": crash_age,
            "bottomCrashDrawdown5yPct": crash_drawdown,
            "baseWeeks": base_weeks, "baseDepthPct": round(depth, 2),
            "baseNewHighWeeks": new_high_weeks,
            "baseEfficiency": round(base_efficiency, 3),
            "recentBaseRangePct26w": round(recent_range26, 2),
            "recentBaseRangePct12w": round(recent_range, 2),
            "launchAdvancePct8w": round(launch_advance, 2),
            "weeklyMaClusterPct": round(ma_spread, 2),
            "maSlope30wPct4w": round(slope30, 2),
            "maPriorSlope30wPct4w": round(prior_slope30, 2),
            "maPriorSlope30wPct13w": round(prior_slope30_13w, 2),
            "maPreBaseSlope30wPct26w": round(prebase_slope30_26w, 2) if prebase_slope30_26w is not None else None,
            "maPreBaseTrendMeasured": prebase_slope30_26w is not None,
            "mansfieldRsPct": round(rs, 2) if rs is not None else None,
            "mansfieldRsChangePct4w": round(rs_change, 2) if rs_change is not None else None,
            "breakoutVolumeRatio4w": round(volume_ratio, 2) if volume_ratio is not None else None,
            "pivotPrice": round(pivot, 4), "resistancePrice": round(resistance, 4) if resistance else None,
            "pivotDistancePct": round(100 * (price / pivot - 1), 2),
            "runwayPct": round(runway, 2) if runway is not None else None,
            "runwayFromPricePct": round(runway_from_price, 2) if runway_from_price is not None else None,
            "runwayBasis": runway_basis,
            "pivotZoneUpperPrice": round(pivot * 1.06, 4),
            "blueSkyConfirmed": blue_sky,
            "extensionPct": round(extension, 2), "weeksSinceBreakout": breakout_age,
            **{key: round(value, 4) for key, value in ma.items()},
        },
        "rejectReasons": [] if eligible else reasons,
    }


def weekly_shortlist(items: Iterable[dict], limit: int = 15) -> list[dict]:
    selected = [item for item in items if (item.get("weeklyBirth") or {}).get("eligible")]
    selected.sort(key=lambda item: (
        -(item["weeklyBirth"]["stage"]),
        -(2 if (item["weeklyBirth"].get("metrics") or {}).get("bottomCrashBaseTriggered")
          else 1 if item["weeklyBirth"].get("chartSource") == "bottom-fishing" else 0),
        -float(item["weeklyBirth"]["score"]),
        str(item.get("ticker") or ""),
    ))
    return selected[:limit]


def weekly_research_watch(items: Iterable[dict], limit: int = 5) -> list[dict]:
    """Bottom Crash near-misses for chart review, never confirmed selections."""
    watch = []
    for item in items:
        evidence = item.get("weeklyBirth") or {}
        metrics = evidence.get("metrics") or {}
        if evidence.get("eligible") or evidence.get("chartSource") != "bottom-fishing":
            continue
        if metrics.get("bottomCrashBaseTriggered") is not True:
            continue
        prebase = metrics.get("maPreBaseSlope30wPct26w")
        rs = metrics.get("mansfieldRsPct")
        rs_change = metrics.get("mansfieldRsChangePct4w")
        pivot_distance = metrics.get("pivotDistancePct")
        runway = metrics.get("runwayPct")
        def measured(key: str, fallback: float) -> float:
            value = metrics.get(key)
            return float(value) if value is not None else fallback
        if any(value is None for value in (prebase, rs, rs_change, pivot_distance)):
            continue
        if not (
            measured("baseWeeks", 0) >= 52
            and measured("weeklyMaClusterPct", 99) <= 8
            and measured("recentBaseRangePct12w", 99) <= 30
            and measured("maPriorSlope30wPct13w", 99) <= 4
            and prebase <= 8
            and -5 <= rs and rs_change >= -2
            and -20 <= pivot_distance <= 4
            and ((runway is not None and runway >= 12) or metrics.get("blueSkyConfirmed") is True)
            and -6 <= measured("extensionPct", 99) <= 10
            and -0.5 <= measured("maSlope30wPct4w", -99) <= 2
            and measured("launchAdvancePct8w", 99) <= 15
        ):
            continue
        watch.append(item)
    watch.sort(key=lambda item: (
        float(item["weeklyBirth"]["metrics"]["recentBaseRangePct12w"]),
        abs(float(item["weeklyBirth"]["metrics"]["pivotDistancePct"])),
        float(item["weeklyBirth"]["metrics"]["weeklyMaClusterPct"]),
        str(item.get("ticker") or ""),
    ))
    return watch[:limit]
