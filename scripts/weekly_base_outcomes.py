"""Forward outcomes for first appearances on the archived Weekly Birth shortlist."""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
import json
from math import isfinite
import re
from statistics import fmean, median

from early_trend_outcomes import pair_signals, prior_features
from market_actions import holding_return_pct
from weekly_birth import LABELS

SCHEMA = "weekly-base-outcomes-v1"
HORIZONS = (5, 20, 63, 126)
STAGES = {label: str(stage) for stage, label in LABELS.items() if stage > 0}


def _shortlist(path, day, point, source):
    try:
        report = json.loads(path.read_bytes())
        rows = report["selected"]
        if (report["schemaVersion"] != "weekly-birth-shadow-audit-v1"
                or report["sessionDate"] != day or report["runId"] != point["runId"]
                or not re.fullmatch(r"[a-f0-9]{64}", report["unifiedManifestSha256"])
                or (day == source["sessionDate"] and
                    report["unifiedManifestSha256"] != source["unifiedManifestSha256"])
                or not isinstance(rows, list) or len(rows) != report["selectedCount"] or len(rows) > 15):
            return None
        selection = {}
        for row in rows:
            ticker = row["ticker"]
            if not re.fullmatch(r"[A-Z0-9._-]{1,20}", ticker) or ticker in selection:
                return None
            selection[ticker] = STAGES[row["stage"]]
        return selection
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def _measure(events, valuation, calendar, horizon):
    pending = missing = pair_pending = pair_missing = paired = 0
    outcomes = defaultdict(list)
    comparisons = defaultdict(list)
    for index, ticker, control in events:
        paired += control is not None
        if index + 1 + horizon >= len(calendar):
            pending += 1
            pair_pending += control is not None
            continue
        signal_return = valuation(ticker, index, horizon)
        if signal_return is None:
            missing += 1
        else:
            outcomes[index].append(signal_return)
        if control is not None:
            control_return = valuation(control, index, horizon)
            if signal_return is None or control_return is None:
                pair_missing += 1
            else:
                comparisons[index].append((signal_return, control_return))
    values = [value for day in outcomes.values() for value in day]
    daily_pairs = [(fmean(left for left, _ in day), fmean(right for _, right in day))
                   for day in comparisons.values()]
    return {
        "observed": len(values), "dates": len(outcomes), "pending": pending, "missing": missing,
        "meanPct": round(fmean(map(fmean, outcomes.values())), 3) if outcomes else None,
        "medianPct": round(median(values), 3) if values else None,
        "positivePct": round(100 * sum(value > 0 for value in values) / len(values), 2) if values else None,
        "matched": {
            "paired": paired, "observed": sum(map(len, comparisons.values())), "dates": len(daily_pairs),
            "pending": pair_pending, "missing": pair_missing,
            "signalPct": round(fmean(left for left, _ in daily_pairs), 3) if daily_pairs else None,
            "controlPct": round(fmean(right for _, right in daily_pairs), 3) if daily_pairs else None,
            "differencePp": round(fmean(left - right for left, right in daily_pairs), 3) if daily_pairs else None,
        },
    }


def report(directory, points, prices, calendar, actions, source):
    as_of = source["sessionDate"]
    if not calendar or calendar[-1] != as_of:
        raise ValueError("Weekly Base outcomes and exchange calendar are not aligned")
    by_day = {point["sessionDate"]: point for point in points}
    expected = sorted(path.stem for path in directory.glob("????-??-??.json") if path.stem <= as_of)
    observations = {}
    for day in expected:
        if day in by_day and day in calendar:
            selection = _shortlist(directory / (day + ".json"), day, by_day[day], source)
            if selection is not None:
                observations[day] = selection
    if as_of not in observations:
        raise ValueError("Latest Weekly Birth shortlist is missing or does not match the Review session")

    events = defaultdict(list)
    seen = set()
    censored = missing_coverage = comparable_days = 0
    for index, day in enumerate(calendar):
        selection = observations.get(day)
        if selection is None:
            continue
        first = selection.keys() - seen
        seen.update(selection)
        previous_day = calendar[index - 1] if index else None
        if previous_day not in observations:
            censored += len(first)
            continue
        comparable_days += 1
        point, previous = by_day[day], by_day[previous_day]
        eligible = first & point["stages"].keys() & previous["stages"].keys()
        missing_coverage += len(first - eligible)
        if not eligible:
            continue
        features = prior_features(point, previous, calendar, index, prices, actions)
        paired = dict(pair_signals(eligible, selection.keys() | observations[previous_day].keys(), features))
        for ticker in sorted(eligible):
            event = (index, ticker, paired.get(ticker))
            events["all"].append(event)
            events[selection[ticker]].append(event)

    @lru_cache(maxsize=None)
    def valuation(ticker, index, horizon):
        value = holding_return_pct(ticker, calendar[index + 1], calendar[index + 1 + horizon], prices, actions)
        return value if value is not None and isfinite(value) else None

    def group(key):
        subset = events[key]
        return {"entries": len(subset), "signalDates": len({event[0] for event in subset}),
                "outcomes": {str(horizon): _measure(subset, valuation, calendar, horizon) for horizon in HORIZONS}}

    first_day = min(observations)
    return {
        "schemaVersion": SCHEMA, "asOf": as_of, "firstSession": first_day,
        "archiveSessions": len(observations), "comparableSessions": comparable_days,
        "latestSelected": len(observations[as_of]),
        "missingSessions": [day for day in calendar if day >= first_day and day not in observations],
        "rejectedArchives": sorted(set(expected) - observations.keys()),
        "unknownFirstDate": censored, "missingPriorOrCurrentCoverage": missing_coverage,
        "groups": {key: group(key) for key in ("all", *STAGES.values())},
    }
