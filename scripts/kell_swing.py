"""Observable EOD setup and price-risk plan for the Kell swing view."""

from statistics import fmean

try:
    from .market_sessions import session_date
except ImportError:
    from market_sessions import session_date

MODEL = "kell-swing-plan-v1"
MIN_PRICE = 5.0
MIN_DOLLAR_VOLUME = 5_000_000
MAX_STOP_PCT = 8.0
MAX_CHASE_R = 0.5
SETUPS = ("ema_crossback", "wedge_pop", "base_n_break", "buyable_gap_proxy", "tightening")
UNSUITABLE_STAGES = {"exhaustion_extension", "wedge_drop"}


def _pivot_stop(bars, setup, ema_floor):
    last, prev = bars[-1], bars[-2]
    if setup == "ema_crossback":
        return prev["high"] + 0.01, min(last["low"], ema_floor)
    if setup == "wedge_pop":
        return max(bar["high"] for bar in bars[-6:-1]) + 0.01, last["low"]
    if setup == "buyable_gap_proxy":
        return last["open"], last["low"]
    prior = bars[-11:-1]
    return max(bar["high"] for bar in prior) + 0.01, min(ema_floor, min(bar["low"] for bar in prior[-5:]))


def build_plan(bars, setup_flags, stage, ema10, ema20, expected_session=None):
    """Rank an EOD observation without claiming that an order was filled."""
    if len(bars) < 21 or not ema10 or not ema20:
        return None
    last, prev = bars[-1], bars[-2]
    day = session_date(last["time"])
    if not day or (expected_session is not None and day != expected_session):
        return None
    setup = next((name for name in SETUPS if setup_flags.get("kell_" + name)), None)
    if setup is None:
        return None
    price = last["close"]
    avg_dollars = fmean(bar["close"] * bar["volume"] for bar in bars[-21:-1])
    pivot, stop = _pivot_stop(bars, setup, min(ema10, ema20) * 0.995)
    gap = (last["open"] / prev["close"] - 1) * 100 if prev["close"] > 0 else None
    risk = pivot - stop
    risk_pct = 100 * risk / pivot if pivot > 0 else None
    max_entry = min(pivot + MAX_CHASE_R * risk, stop / (1 - MAX_STOP_PCT / 100))
    if stage in UNSUITABLE_STAGES or not 0 < stop < pivot or price <= stop:
        state, reason = "invalidated", "price_or_cycle_invalidation"
    elif price < MIN_PRICE or avg_dollars < MIN_DOLLAR_VOLUME:
        state, reason = "watch", "insufficient_liquidity"
    elif risk_pct > MAX_STOP_PCT:
        state, reason = "watch", "risk_too_wide"
    elif price > max_entry:
        state, reason = "extended", "above_max_entry"
    elif price >= pivot:
        state, reason = "triggered", "pivot_closed_above"
    else:
        state, reason = "watch", "below_pivot"
    return {
        "model": MODEL, "setup": setup, "phase": stage, "sessionDate": day,
        "state": state, "reason": reason, "pivot": round(pivot, 4),
        "stop": round(stop, 4), "maxEntry": round(max_entry, 4) if max_entry >= pivot else None,
        "riskPct": round(risk_pct, 2) if risk_pct is not None else None,
        "gapPct": round(gap, 2) if gap is not None else None,
        "averageDollarVolume20": round(avg_dollars, 2),
        "orderEarliest": "next_session",
    }


def priority(item):
    plan = item["kellSwing"]
    state = {"triggered": 0, "watch": 1, "extended": 2, "invalidated": 3}[plan["state"]]
    risk = plan.get("riskPct")
    return (state, SETUPS.index(plan["setup"]), risk if risk is not None else float("inf"),
            -float(item.get("kell_readiness_score") or 0), item["ticker"])
