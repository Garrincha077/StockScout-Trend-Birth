"""Mature Early Trend Birth cohorts from permanent, dated stages and quotes."""

from collections import Counter
from math import ceil
from statistics import fmean, median

try:
    from .market_actions import holding_return_pct
except ImportError:
    from market_actions import holding_return_pct

HORIZONS = (20, 63, 126, 252)
COHORTS = ("early", "daily4", "weekly")


def first_entries(points, calendar):
    """Count a new appearance after a previously observed eligible session."""
    positions = {day: index for index, day in enumerate(calendar)}
    seen = {name: {} for name in COHORTS}
    result = []
    previous = None
    for point in points:
        early = point.get("earlyTrend")
        if early is None:
            previous = None
            continue
        day = point["sessionDate"]
        index = positions[day]
        selections = {
            "early": set(early["shortlist"]),
            "weekly": set(early["weekly"]),
            "daily4": {name for name, stage in point["stages"].items() if stage[0] == 4},
        }
        entries = {name: set() for name in COHORTS}
        if previous is not None and previous[0] == index - 1:
            _, prior_point, prior_names = previous
            for key, selected in selections.items():
                for name in selected - prior_names[key]:
                    if name in prior_point["stages"] and index - seen[key].get(name, -1000) >= 63:
                        entries[key].add(name)
                        seen[key][name] = index
            result.append((point, entries))
        previous = (index, point, selections)
    return result


def report(points, prices, calendar, actions):
    positions = {day: index for index, day in enumerate(calendar)}
    entries = first_entries(points, calendar)
    first = {key: {} for key in COHORTS}
    for point, names in entries:
        for key in COHORTS:
            for name in names[key]:
                first[key].setdefault(name, positions[point["sessionDate"]])
    lead = {}
    for other in ("daily4", "weekly"):
        matched = first["early"].keys() & first[other].keys()
        distances = [first[other][ticker] - first["early"][ticker] for ticker in matched]
        lead[other] = {
            "matched": len(distances), "earlier": sum(value > 0 for value in distances),
            "same": distances.count(0), "later": sum(value < 0 for value in distances),
            "medianSessions": median(distances) if distances else None,
        }
    horizons = {}
    for horizon in HORIZONS:
        metrics = {key: Counter() for key in COHORTS}
        returns = {key: [] for key in COHORTS}
        excess = {key: [] for key in COHORTS}
        for point, cohort in entries:
            if not any(cohort.values()):
                continue
            start = positions[point["sessionDate"]] + 1
            end = start + horizon
            matured = end < len(calendar)
            for key, names in cohort.items():
                metrics[key]["matured" if matured else "pending"] += len(names)
            if not matured:
                continue
            samples = {}
            for ticker in point["stages"]:
                value = holding_return_pct(ticker, calendar[start], calendar[end], prices, actions)
                if value is not None:
                    samples[ticker] = value
            if len(samples) < 20:
                continue
            benchmark = median(samples.values())
            leaders = set(sorted(samples, key=lambda ticker: (-samples[ticker], ticker))[:ceil(len(samples) * 0.1)])
            for key, names in cohort.items():
                observed = names & samples.keys()
                metrics[key]["leaderOpportunities"] += len(leaders)
                metrics[key]["leadersCaptured"] += len(leaders & observed)
                metrics[key]["nonLeaderAlerts"] += len(observed - leaders)
                metrics[key]["belowUniverseMedian"] += sum(samples[ticker] < benchmark for ticker in observed)
                metrics[key]["observed"] += len(observed)
                if observed:
                    day_mean = fmean(samples[ticker] for ticker in observed)
                    returns[key].append(day_mean)
                    excess[key].append(day_mean - benchmark)
        horizons[str(horizon)] = {}
        for key in COHORTS:
            status = {name: metrics[key][name] for name in (
                "matured", "pending", "observed", "leaderOpportunities", "leadersCaptured",
                "nonLeaderAlerts", "belowUniverseMedian",
            )}
            status["missingMatured"] = status["matured"] - status["observed"]
            status["leadersMissed"] = status["leaderOpportunities"] - status["leadersCaptured"]
            status["signalDates"] = len(returns[key])
            status["meanPct"] = round(fmean(returns[key]), 3) if returns[key] else None
            status["excessPct"] = round(fmean(excess[key]), 3) if excess[key] else None
            horizons[str(horizon)][key] = status
    return {
        "schemaVersion": "early-trend-outcomes-v1",
        "observedSessions": sum("earlyTrend" in point for point in points),
        "firstCandidates": {key: len(first[key]) for key in COHORTS},
        "lead": lead, "horizons": horizons,
        "definition": "Adjacent archived sessions, first new entry per 63-session cooldown. "
                      "Next close to horizon close, equal signal-date weights. Leader = top decile "
                      "of the signal-date eligible universe with both exit and entry quotes.",
    }
