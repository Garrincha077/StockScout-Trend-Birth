"""Detect a base beginning to repair with evidence available at the EOD cutoff."""

from statistics import median

try:
    from .market_sessions import session_date
    from .trend_birth_radar import normalize_bars
except ImportError:
    from market_sessions import session_date
    from trend_birth_radar import normalize_bars

MODEL = "early-trend-birth-v1"
SHORTLIST_SIZE = 15
HISTORY = 126
PHASE_ORDER = {"confirmed": 0, "reclaim": 1, "stabilizing": 2}


def relative_trajectory(bars, benchmark):
    """Measure 20-session relative changes on the ticker's actual dates."""
    keys = [session_date(bars[i]["time"]) for i in (-41, -21, -1)]
    market = [benchmark.get(key) for key in keys]
    if any(price is None or price <= 0 for price in market):
        return None, None
    stock = [bars[i]["close"] for i in (-41, -21, -1)]
    relative = [close / base for close, base in zip(stock, market)]
    recent = 100 * (relative[2] / relative[1] - 1)
    earlier = 100 * (relative[1] / relative[0] - 1)
    return recent, recent - earlier


def evaluate(rows, expected_day, benchmark, daily_stage=None, weekly=None):
    # Work on the passed slice only. All references precede the confirmation bar.
    bars = normalize_bars(rows[-HISTORY - 1:])
    if len(bars) < HISTORY + 1:
        return None
    days = [session_date(bar["time"]) for bar in bars]
    if days[-1] != expected_day or any(day is None for day in days):
        return None
    if any(previous >= day for previous, day in zip(days, days[1:])):
        return None
    if any(not 0 < bar["low"] <= bar["close"] <= bar["high"] for bar in bars):
        return None

    price = bars[-1]["close"]
    structural_high = max(bar["high"] for bar in bars[:-20])
    support = min(bar["low"] for bar in bars[-46:-5])
    invalidation = support * 0.985
    if price < 3 or price <= invalidation or price > support * 1.2 or price > structural_high * 0.85:
        return None

    lows = [bar["low"] for bar in bars[-41:-5]]
    first_test = next((i for i, low in enumerate(lows) if low <= support * 1.025), len(lows))
    retest = any(low <= support * 1.025 for low in lows[first_test + 5:])
    higher_low = min(bar["low"] for bar in bars[-10:-1]) >= support * 1.02
    reclaimed = any(bar["low"] < support and bar["close"] >= support * 1.005 for bar in bars[-5:])
    daily_ranges = [(bar["high"] - bar["low"]) / bar["close"] for bar in bars[-30:]]
    compressed = median(daily_ranges[-10:]) <= 0.8 * median(daily_ranges[:-10])
    relative20, relative_change = relative_trajectory(bars, benchmark)
    improving_rs = relative20 is not None and relative20 >= 0 and relative_change >= 2
    evidence = [
        name for name, active in (
            ("support_retest", retest), ("higher_low", higher_low), ("support_reclaim", reclaimed),
            ("range_compression", compressed), ("relative_strength_turn", improving_rs),
        ) if active
    ]
    recovered_close = price > median(bar["close"] for bar in bars[-11:-1])
    if not recovered_close or len(evidence) < 2 or not (retest or higher_low or reclaimed):
        return None
    pivot = max(bar["high"] for bar in bars[-11:-1])
    weekly = weekly or {}
    established = (daily_stage or 0) >= 3 or (weekly.get("stage") or 0) >= 3
    phase = "confirmed" if price > pivot and established else "reclaim" if reclaimed or price > pivot else "stabilizing"
    return {
        "model": MODEL, "sessionDate": expected_day, "phase": phase, "evidence": evidence,
        "baseSessions": 41, "baseSupport": round(support, 4), "invalidation": round(invalidation, 4),
        "reclaimPivot": round(pivot, 4), "riskToInvalidationPct": round(100 * (price / invalidation - 1), 2),
        "drawdownPct": round(100 * (price / structural_high - 1), 2),
        "relativeStrength20Pct": round(relative20, 2) if relative20 is not None else None,
        "relativeStrengthChangePp": round(relative_change, 2) if relative_change is not None else None,
        "dailyStage": daily_stage, "weeklyStage": weekly.get("stage"),
        "weeklyBaseWeeks": (weekly.get("metrics") or {}).get("baseWeeks"),
    }


def priority(row):
    info = row["earlyTrend"]
    return (PHASE_ORDER[info["phase"]], -len(info["evidence"]), info["riskToInvalidationPct"], row["ticker"])
