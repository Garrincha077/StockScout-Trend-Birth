"""Compare the Kell swing plan, former shortlist and momentum on archived EODs."""

from bisect import bisect_left
from collections import Counter, defaultdict
import argparse
import json
from pathlib import Path
from statistics import fmean

try:
    from .kell_forward_validation import load_chart_store, load_score_snapshots
    from .kell_scoring import _ema
    from .kell_swing import MIN_DOLLAR_VOLUME, MIN_PRICE, build_plan, priority
    from .market_actions import read_actions
    from .market_sessions import exchange_sessions
except ImportError:
    from kell_forward_validation import load_chart_store, load_score_snapshots
    from kell_scoring import _ema
    from kell_swing import MIN_DOLLAR_VOLUME, MIN_PRICE, build_plan, priority
    from market_actions import read_actions
    from market_sessions import exchange_sessions

SCENARIOS = {"20bp": 0.2, "50bp": 0.5}
HORIZONS = (5, 10, 20)


def setup_flags(row):
    setups = set(row.get("setups") or [])
    flags = {name: True for name in setups}
    flags["kell_tightening"] = {"kell_tightening", "kell_breakout_proximity"} <= setups
    return flags


def history_index(charts):
    result = {}
    for ticker, rows in charts.items():
        bars = [{"time": row["date"], **row} for row in rows]
        days = tuple(row["date"] for row in bars)
        closes = [row["close"] for row in bars]
        result[ticker] = (bars, days, _ema(closes, 10), _ema(closes, 20))
    return result


def fills(plan, window):
    """5-session limit/stop illustration with bounds for ambiguous OHLC ordering."""
    pivot, stop, limit = plan["pivot"], plan["stop"], plan["maxEntry"]
    first = window[0]
    if first["open"] <= stop or first["open"] > limit or first["high"] < pivot:
        return None
    entry = max(pivot, first["open"])
    risk = entry - stop
    target = entry + 2 * risk
    possible = []
    for index, bar in enumerate(window):
        if index and (bar["open"] <= stop or bar["open"] >= target):
            possible.append(bar["open"])
            break
        stopped, reached = bar["low"] <= stop, bar["high"] >= target
        if stopped:
            possible.append(stop)
            if reached:
                possible.append(target)
                break
            # On an intraday entry, a bar's low could occur before the order.
            if index == 0 and bar["open"] < pivot and bar["close"] > stop:
                continue
            break
        if reached:
            possible.append(target)
            break
    else:
        possible.append(window[-1]["close"])
    return tuple((close - entry) / risk for close in (min(possible), max(possible))), entry / risk


def replay(snapshots, charts, days, actions, top=5):
    history = history_index(charts)
    calendar_index = {day: i for i, day in enumerate(days)}
    exclusions = defaultdict(set)
    for action in actions:
        exclusions[action.ticker].add(action.day)
    paired = defaultdict(list)
    totals = defaultdict(Counter)
    execution = {key: [] for key in SCENARIOS}
    for snapshot in snapshots:
        day = snapshot["sessionDate"]
        index = calendar_index.get(day)
        if snapshot["source"].get("recovered") or index is None or index < 63:
            continue
        candidates = []
        for row in snapshot["candidates"]:
            ticker = row.get("ticker")
            if ticker not in history:
                continue
            bars, dates, ema10, ema20 = history[ticker]
            j = bisect_left(dates, day)
            past = bisect_left(dates, days[index - 63])
            if j < 21 or j == len(dates) or dates[j] != day or dates[past] != days[index - 63]:
                continue
            recent = bars[j - 20:j]
            if (bars[j]["close"] < MIN_PRICE or
                    fmean(b["close"] * b["volume"] for b in recent) < MIN_DOLLAR_VOLUME):
                continue
            price_history = dict(zip(dates[j:j + 22], bars[j:j + 22]))
            plan = build_plan(bars[j - 20:j + 1], setup_flags(row), row.get("stage"), ema10[j], ema20[j], day)
            candidate = {
                **row, "kellSwing": plan, "momentum": bars[j]["close"] / bars[past]["close"] - 1,
                "future": price_history,
            }
            candidates.append(candidate)
        proposed = sorted(
            (row for row in candidates if row["kellSwing"] and row["kellSwing"]["state"] == "triggered"),
            key=priority,
        )[:top]
        count = len(proposed)
        if not count:
            continue
        legacy = sorted(candidates, key=lambda row: (-float(row.get("kell_readiness_score") or 0),
                                                     -float(row.get("kell_score") or 0), row["ticker"]))[:count]
        momentum = sorted(candidates, key=lambda row: (-row["momentum"], row["ticker"]))[:count]
        for horizon in HORIZONS:
            window = days[index + 1:index + horizon + 1]
            if len(window) != horizon:
                continue
            cohorts = {}
            for name, picks in (("swing", proposed), ("legacy", legacy), ("momentum", momentum)):
                totals[horizon][name + "Selected"] += len(picks)
                returns = []
                for item in picks:
                    future = item["future"]
                    if (any(session not in future for session in window) or
                            any(session in exclusions[item["ticker"]] for session in window)):
                        continue
                    bars = [future[session] for session in window]
                    returns.append(100 * (bars[-1]["close"] / bars[0]["open"] - 1))
                    if name == "swing" and horizon == 5:
                        result = fills(item["kellSwing"], bars)
                        if result:
                            bounds, entry_risk_ratio = result
                            for label, cost in SCENARIOS.items():
                                execution[label].append(tuple(value - cost / 100 * entry_risk_ratio for value in bounds))
                totals[horizon][name + "Observed"] += len(returns)
                cohorts[name] = returns
            if all(cohorts.values()):
                paired[horizon].append({key: fmean(value) for key, value in cohorts.items()})
    comparison = {}
    for horizon in HORIZONS:
        rows = paired[horizon]
        comparison[str(horizon)] = {
            "pairedDates": len(rows),
            "coverage": dict(totals[horizon]),
            "returnPctByCost": {
                label: {key: round(fmean(row[key] for row in rows) - cost, 3)
                        for key in ("swing", "legacy", "momentum")} if rows else None
                for label, cost in SCENARIOS.items()
            },
        }
    return {
        "schemaVersion": "kell-swing-replay-v1", "asOf": days[-1],
        "comparisons": comparison,
        "execution5": {
            key: {"fills": len(rows),
                  "netR": [round(fmean(value), 3) for value in zip(*rows)] if rows else None}
            for key, rows in execution.items()
        },
        "method": ("Contemporaneous membership and archived setups, common price and dollar-volume eligibility, "
                   "next-session open comparison on dates with observed results for each strategy. "
                   "New strategy controls the matched shortlist size. Known action windows are excluded after selection. "
                   "Historical charts come from the pinned last-day store. Publication before entry is assumed."),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores-dir", type=Path, required=True)
    parser.add_argument("--charts-dir", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--actions", type=Path,
                        default=Path(__file__).with_name("data") / "review-market-actions-v1.json")
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top must be positive")
    actions, _ = read_actions(args.actions)
    report = replay(load_score_snapshots(args.scores_dir), load_chart_store(args.charts_dir),
                    exchange_sessions(args.as_of), actions, args.top)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
