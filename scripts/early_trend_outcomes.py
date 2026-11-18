"""Mature Early Trend Birth cohorts from permanent, dated stages and quotes."""

from collections import Counter
from math import ceil, isfinite, log
from statistics import fmean, median

try:
    from .market_actions import holding_return_pct
except ImportError:
    from market_actions import holding_return_pct

HORIZONS = (20, 63, 126, 252)
COHORTS = ("early", "daily4", "weekly")
MATCHED_SCHEMA = "trend-birth-matched-cohorts-v1"
MATCHED_COHORTS = ("early", "daily4")
MATCHED_HORIZONS = (5, *HORIZONS)
MATCH_LOOKBACK = 20
MAX_PRICE_RATIO = 2
MAX_MOMENTUM_GAP = 10


def first_entries(points, calendar, *, daily_history=False):
    """Count a new appearance after a previously observed eligible session."""
    positions = {day: index for index, day in enumerate(calendar)}
    seen = {name: {} for name in COHORTS}
    result = []
    previous = None
    for point in points:
        early = point.get("earlyTrend")
        if early is None and not daily_history:
            previous = None
            continue
        day = point["sessionDate"]
        index = positions[day]
        selections = {"daily4": {name for name, stage in point["stages"].items() if stage[0] == 4}}
        if early is not None:
            selections.update(early=set(early["shortlist"]), weekly=set(early["weekly"]))
        entries = {name: set() for name in COHORTS}
        if previous is not None and previous[0] == index - 1:
            _, prior_point, prior_names = previous
            for key, selected in selections.items():
                if key not in prior_names or (
                    key == "early" and prior_point["earlyTrend"]["model"] != early["model"]
                ):
                    continue
                for name in selected - prior_names[key]:
                    if name in prior_point["stages"] and index - seen[key].get(name, -1000) >= 63:
                        entries[key].add(name)
                        seen[key][name] = index
            result.append((point, entries))
        previous = (index, point, selections)
    return result


def prior_features(current, prior, calendar, index, prices, actions):
    previous = index - 1
    if previous < MATCH_LOOKBACK:
        return {}
    start, end = calendar[previous - MATCH_LOOKBACK], calendar[previous]
    features = {}
    for ticker in current["stages"].keys() & prior["stages"].keys():
        close = prices.get(ticker, {}).get(end)
        if close is None or not isfinite(close) or close <= 0:
            continue
        momentum = holding_return_pct(ticker, start, end, prices, actions)
        if momentum is not None and isfinite(momentum):
            features[ticker] = (prior["stages"][ticker][0], log(close), momentum)
    return features


def pair_signals(signals, excluded, features):
    """Match before looking at outcomes; use each control once per cohort and date."""
    candidates = {}
    controls = [[], [], [], [], []]
    for ticker in features.keys() - excluded - signals:
        stage, price, momentum = features[ticker]
        controls[stage].append((ticker, price, momentum))
    price_limit = log(MAX_PRICE_RATIO)
    for ticker in signals & features.keys():
        stage, price, momentum = features[ticker]
        ranked = []
        for peer, peer_price, peer_momentum in controls[stage]:
            price_gap, momentum_gap = abs(price - peer_price), abs(momentum - peer_momentum)
            if price_gap <= price_limit + 1e-12 and momentum_gap <= MAX_MOMENTUM_GAP + 1e-12:
                ranked.append((price_gap / price_limit + momentum_gap / MAX_MOMENTUM_GAP, peer))
        candidates[ticker] = [peer for _, peer in sorted(ranked)]
    used = set()
    pairs = []
    for ticker in sorted(candidates, key=lambda name: (len(candidates[name]), name)):
        peer = next((name for name in candidates[ticker] if name not in used), None)
        if peer is not None:
            used.add(peer)
            pairs.append((ticker, peer))
    return pairs


def matched_outcomes(points, prices, calendar, actions):
    positions = {day: index for index, day in enumerate(calendar)}
    by_day = {point["sessionDate"]: point for point in points}
    cohort_days = {key: [] for key in MATCHED_COHORTS}
    counts = {key: Counter() for key in MATCHED_COHORTS}
    for point, entries in first_entries(points, calendar, daily_history=True):
        if not any(entries[key] for key in MATCHED_COHORTS):
            continue
        index = positions[point["sessionDate"]]
        prior = by_day[calendar[index - 1]]
        features = prior_features(point, prior, calendar, index, prices, actions)
        for key in MATCHED_COHORTS:
            signals = entries[key]
            if not signals:
                continue
            if key == "early":
                early = point["earlyTrend"]
                excluded = set(early.get("candidates", early["shortlist"]))
            else:
                excluded = {ticker for ticker, stage in point["stages"].items() if stage[0] == 4}
            pairs = pair_signals(signals, excluded, features)
            counts[key].update(signals=len(signals), missingFeatures=len(signals - features.keys()),
                               paired=len(pairs), signalDates=1)
            if pairs:
                cohort_days[key].append((index, pairs))
    groups = {}
    for key in MATCHED_COHORTS:
        count = counts[key]
        outcomes = {}
        for horizon in MATCHED_HORIZONS:
            daily = []
            pending = missing = observed = 0
            for index, pairs in cohort_days[key]:
                start = index + 1
                end = start + horizon
                if end >= len(calendar):
                    pending += len(pairs)
                    continue
                samples = []
                for signal, control in pairs:
                    left = holding_return_pct(signal, calendar[start], calendar[end], prices, actions)
                    right = holding_return_pct(control, calendar[start], calendar[end], prices, actions)
                    if left is None or right is None or not all(map(isfinite, (left, right))):
                        missing += 1
                    else:
                        samples.append((left, right))
                if samples:
                    observed += len(samples)
                    daily.append((fmean(left for left, _ in samples), fmean(right for _, right in samples)))
            differences = [left - right for left, right in daily]
            outcomes[str(horizon)] = {
                "pending": pending, "missingPairPrices": missing, "observed": observed,
                "observedDates": len(daily), "positiveDates": sum(delta > 0 for delta in differences),
                "signalReturnPct": round(fmean(left for left, _ in daily), 3) if daily else None,
                "controlReturnPct": round(fmean(right for _, right in daily), 3) if daily else None,
                "differencePp": round(fmean(differences), 3) if differences else None,
            }
        groups[key] = {
            "signals": count["signals"], "signalDates": count["signalDates"], "paired": count["paired"],
            "missingFeatures": count["missingFeatures"],
            "unmatched": count["signals"] - count["paired"] - count["missingFeatures"],
            "outcomes": outcomes,
        }
    return {
        "schemaVersion": MATCHED_SCHEMA, "asOf": calendar[-1] if calendar else None, "groups": groups,
        "earlyObservedSessions": sum("earlyTrend" in point for point in points),
        "dailyObservedSessions": len(points),
        "lookbackSessions": MATCH_LOOKBACK, "maxPriceRatio": MAX_PRICE_RATIO,
        "maxMomentumGapPp": MAX_MOMENTUM_GAP,
        "method": "Controls from the same evaluated date, same previous radar stage, with price and momentum "
                  "measured through the preceding close. Closest controls without reuse per date and cohort. "
                  "No sector or liquidity matching. Pairs fixed before outcomes. Next close to horizon close; "
                  "equal weight per observed signal date; gross returns, known corporate actions only.",
    }


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
        "matched": matched_outcomes(points, prices, calendar, actions),
        "definition": "Adjacent archived sessions, first new entry per 63-session cooldown. "
                      "Next close to horizon close, equal signal-date weights. Leader = top decile "
                      "of the signal-date eligible universe with both exit and entry quotes.",
    }
