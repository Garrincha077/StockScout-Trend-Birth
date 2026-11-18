"""Compare the Kell swing plan, former shortlist and momentum on archived EODs."""

from bisect import bisect_left
from collections import Counter, defaultdict
import argparse
import json
from math import isfinite
from pathlib import Path
from statistics import fmean

try:
    from .kell_scoring import _ema
    from .kell_swing import MODEL, MIN_DOLLAR_VOLUME, MIN_PRICE, SETUPS, build_plan, priority
    from .market_actions import read_actions
    from .market_sessions import exchange_sessions
except ImportError:
    from kell_scoring import _ema
    from kell_swing import MODEL, MIN_DOLLAR_VOLUME, MIN_PRICE, SETUPS, build_plan, priority
    from market_actions import read_actions
    from market_sessions import exchange_sessions

SCENARIOS = {"20bp": 0.2, "50bp": 0.5}
HORIZONS = (5, 10, 20)
STRATEGIES = ("swing", "legacy", "momentum")
ACTIONS_PATH = Path(__file__).with_name("data") / "review-market-actions-v1.json"
BREADTH_THRESHOLD_PP = 0.5
BREADTH_REGIMES = ("rising", "steady", "falling", "unknown")
EXECUTION_STATUSES = ("pending", "corporateAction", "missingBars", "unmatchedClose", "invalidLevels", "evaluable")
COHORT_SCHEMA = "kell-swing-execution-cohorts-v1"


def breadth_index(payload, day, run):
    points = payload.get("points") or []
    days = [point["sessionDate"] for point in points]
    if (payload.get("schemaVersion") != "trend-birth-market-internals-v1"
            or (payload.get("latestSessionDate"), payload.get("latestRunId")) != (day, run)
            or not points or days != sorted(set(days)) or (days[-1], points[-1]["runId"]) != (day, run)):
        raise ValueError("Kell breadth history does not match the active EOD")
    return dict(zip(days, points))


def breadth_regime(snapshot, days, index, context):
    day = snapshot["sessionDate"]
    point = context.get(day)
    run = snapshot["source"].get("runId")
    if (not point or not index or not run or point.get("runId") != run
            or point.get("previousSessionDate") != days[index - 1]):
        return "unknown"
    delta = point.get("matchedQualityDeltaPp")
    if not isinstance(delta, (int, float)) or not isfinite(delta):
        return "unknown"
    if delta >= BREADTH_THRESHOLD_PP:
        return "rising"
    if delta <= -BREADTH_THRESHOLD_PP:
        return "falling"
    return "steady"


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


def replay(snapshots, charts, days, actions, top=5, *, complete_pairs=False, breadth=None):
    history = history_index(charts)
    calendar_index = {day: i for i, day in enumerate(days)}
    exclusions = defaultdict(set)
    for action in actions:
        exclusions[action.ticker].add(action.day)
    paired = defaultdict(list)
    totals = defaultdict(Counter)
    execution = {key: [] for key in SCENARIOS}
    matched_picks = Counter()
    selected_dates = Counter()
    plan_rows = {horizon: [] for horizon in HORIZONS}
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
        regime = breadth_regime(snapshot, days, index, breadth) if breadth is not None else None
        for horizon in HORIZONS:
            window = days[index + 1:index + horizon + 1]
            if regime is not None:
                for item in proposed:
                    result = check_execution(item["kellSwing"], day, window, horizon, item["future"],
                                             exclusions[item["ticker"]])
                    plan_rows[horizon].append((day, item["kellSwing"]["setup"], regime, *result))
            if len(window) != horizon:
                continue
            selected_dates[horizon] += 1
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
            if all(cohorts.values()) and (not complete_pairs or all(len(rows) == count for rows in cohorts.values())):
                matched_picks[horizon] += count
                paired[horizon].append({key: fmean(value) for key, value in cohorts.items()})
    comparison = {}
    for horizon in HORIZONS:
        rows = paired[horizon]
        comparison[str(horizon)] = {
            "pairedDates": len(rows),
            "selectedDates": selected_dates[horizon],
            "pairedSelectionsPerStrategy": matched_picks[horizon] if complete_pairs else None,
            "coverage": dict(totals[horizon]),
            "returnPctByCost": {
                label: {key: round(fmean(row[key] for row in rows) - cost, 3)
                        for key in STRATEGIES} if rows else None
                for label, cost in SCENARIOS.items()
            },
        }
    result = {
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
    if breadth is not None:
        result["planExecution"] = execution_cohorts(plan_rows)
    return result


def has_published_plan(snapshot):
    return any("swing" in row for row in snapshot["candidates"])


def _matches_anchor(actual, stored):
    return isinstance(stored, (int, float)) and stored > 0 and abs(actual - stored) <= max(0.005, stored * .00005)


def _valid_bar(bar):
    return bar and bar["low"] <= min(bar["open"], bar["close"]) <= max(bar["open"], bar["close"]) <= bar["high"]


def _scenario_results(filled):
    results = {}
    for label, cost in SCENARIOS.items():
        values = [tuple(value - cost / 100 * ratio for value in bounds) for bounds, ratio in filled]
        results[label] = [round(fmean(side), 3) for side in zip(*values)] if values else None
    return results


def check_execution(plan, day, window, horizon, bars, action_days):
    if len(window) < horizon:
        return "pending", None
    if any(session in action_days for session in window):
        return "corporateAction", None
    if not _valid_bar(bars.get(day)) or any(not _valid_bar(bars.get(session)) for session in window):
        return "missingBars", None
    if not _matches_anchor(bars[day]["close"], plan.get("signalClose")):
        return "unmatchedClose", None
    stop, pivot, limit = (plan.get(key) for key in ("stop", "pivot", "maxEntry"))
    if not all(isinstance(level, (int, float)) and isfinite(level) for level in (stop, pivot, limit)) or not 0 < stop < pivot <= limit:
        return "invalidLevels", None
    return "evaluable", fills(plan, [bars[session] for session in window])


def execution_summary(rows):
    count = Counter(row[3] for row in rows)
    executed = [row[4] for row in rows if row[4] is not None]
    return {
        "selected": len(rows), **{key: count[key] for key in EXECUTION_STATUSES},
        "signalDates": len({row[0] for row in rows}),
        "fillDates": len({row[0] for row in rows if row[4] is not None}),
        "fills": len(executed), "ambiguousFills": sum(bounds[0] != bounds[1] for bounds, _ in executed),
        "netRByCost": _scenario_results(executed),
    }


def execution_cohorts(rows):
    return {
        "outcomes": {str(horizon): execution_summary(rows[horizon]) for horizon in HORIZONS},
        "bySetup": {
            name: {str(horizon): execution_summary([row for row in rows[horizon] if row[1] == name])
                   for horizon in HORIZONS} for name in SETUPS
        },
        "byBreadth": {
            name: {str(horizon): execution_summary([row for row in rows[horizon] if row[2] == name])
                   for horizon in HORIZONS} for name in BREADTH_REGIMES
        },
    }


def published_execution(snapshots, charts, days, actions, top, breadth):
    calendar_index = {day: index for index, day in enumerate(days)}
    bars_by_ticker = {ticker: {bar["date"]: bar for bar in rows} for ticker, rows in charts.items()}
    exclusions = defaultdict(set)
    for action in actions:
        exclusions[action.ticker].add(action.day)
    rows = {horizon: [] for horizon in HORIZONS}
    observations = []
    for snapshot in snapshots:
        day = snapshot["sessionDate"]
        if day not in calendar_index:
            continue
        observations.append(day)
        proposals = [{**row, "kellSwing": row["swing"]} for row in snapshot["candidates"]
                     if (row.get("swing") or {}).get("state") == "triggered"
                     and row["swing"].get("model") == MODEL and row["swing"].get("sessionDate") == day]
        selections = sorted(proposals, key=priority)[:top]
        index = calendar_index[day]
        start = index + 1
        regime = breadth_regime(snapshot, days, index, breadth)
        for horizon in HORIZONS:
            window = days[start:start + horizon]
            for item in selections:
                ticker, plan = item["ticker"], item["kellSwing"]
                result = check_execution(plan, day, window, horizon, bars_by_ticker.get(ticker, {}), exclusions[ticker])
                rows[horizon].append((day, plan["setup"], regime, *result))
    return {
        "firstSession": observations[0] if observations else None,
        "sessionCount": len(observations),
        **execution_cohorts(rows),
    }


def build_statistics(snapshots, charts, days, actions, top=5, *, breadth=None):
    calendar = set(days)
    observed = [snapshot for snapshot in snapshots if snapshot["sessionDate"] in calendar
                and not snapshot["source"].get("recovered")]
    published = [snapshot for snapshot in observed if has_published_plan(snapshot)]
    # Use only sessions preceding the first real plan publication for reconstruction.
    boundary = published[0]["sessionDate"] if published else None
    historical = [snapshot for snapshot in observed if boundary is None or snapshot["sessionDate"] < boundary]
    context = breadth or {}
    reconstructed = replay(historical, charts, days, actions, top, complete_pairs=True, breadth=context)
    execution = published_execution(published, charts, days, actions, top, context)
    return {
        "schemaVersion": "kell-swing-statistics-v1",
        "asOf": days[-1],
        "horizons": list(HORIZONS),
        "maxSelectionsPerSession": top,
        "published": execution,
        "reconstructed": {"sessionCount": len(historical), "comparisons": reconstructed["comparisons"]},
        "executionCohorts": {
            "schemaVersion": COHORT_SCHEMA, "asOf": days[-1], "breadthThresholdPp": BREADTH_THRESHOLD_PP,
            "historical": reconstructed["planExecution"],
        },
    }


def main():
    try:
        from .kell_forward_validation import load_chart_store, load_score_snapshots
    except ImportError:
        from kell_forward_validation import load_chart_store, load_score_snapshots
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores-dir", type=Path, required=True)
    parser.add_argument("--charts-dir", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--actions", type=Path, default=ACTIONS_PATH)
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
