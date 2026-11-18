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
CASE_SCHEMA = "weekly-base-cases-v1"
CASE_FILE = "weekly-base-cases.json"
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


def _measure(events, horizon):
    pending = missing = pair_pending = pair_missing = paired = 0
    outcomes = defaultdict(list)
    comparisons = defaultdict(list)
    for day, case in events:
        outcome = case["outcomes"][str(horizon)]
        signal, control = outcome["signal"], outcome["control"]
        paired += control is not None
        if signal["status"] == "pending":
            pending += 1
            pair_pending += control is not None
            continue
        signal_return = signal["returnPct"]
        if signal_return is None:
            missing += 1
        else:
            outcomes[day].append(signal_return)
        if control is not None:
            control_return = control["returnPct"]
            if signal_return is None or control_return is None:
                pair_missing += 1
            else:
                comparisons[day].append((signal_return, control_return))
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


def date_at(schedule, index):
    return schedule[index] if index < len(schedule) else None


def _valuation(ticker, entry, exit_day, as_of, prices, archived_days, actions):
    quotes = prices.get(ticker, {})
    entry_close = quotes.get(entry) if entry and entry <= as_of else None
    exit_close = quotes.get(exit_day) if exit_day and exit_day <= as_of else None
    outcome = {"entryClose": entry_close, "exitClose": exit_close, "returnPct": None, "reasons": []}
    if exit_day is None or exit_day > as_of:
        return {**outcome, "status": "pending"}
    for label, day, close in (("entry", entry, entry_close), ("exit", exit_day, exit_close)):
        if day not in archived_days:
            outcome["reasons"].append(label + "_session")
        elif close is None:
            outcome["reasons"].append(label + "_quote")
    if not outcome["reasons"]:
        value = holding_return_pct(ticker, entry, exit_day, prices, actions)
        if value is not None and isfinite(value):
            return {**outcome, "status": "measured", "returnPct": value}
        outcome["reasons"].append("valuation")
    return {**outcome, "status": "missing"}


def report(directory, points, prices, calendar, actions, source, *, schedule=None, cases=None):
    as_of = source["sessionDate"]
    if not calendar or calendar[-1] != as_of:
        raise ValueError("Weekly Base outcomes and exchange calendar are not aligned")
    schedule = calendar if schedule is None else schedule
    if tuple(schedule[:len(calendar)]) != tuple(calendar):
        raise ValueError("Weekly Base schedule differs from the realized exchange calendar")
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

    @lru_cache(maxsize=None)
    def valuation(ticker, entry, exit_day):
        return _valuation(ticker, entry, exit_day, as_of, prices, by_day, actions)

    events = defaultdict(list)
    case_days = []
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
        entry = date_at(schedule, index + 1)
        exits = {str(h): date_at(schedule, index + 1 + h) for h in HORIZONS}
        rows = []
        for ticker in sorted(eligible):
            control = paired.get(ticker)
            outcomes = {}
            for horizon, exit_day in exits.items():
                outcomes[horizon] = {"signal": valuation(ticker, entry, exit_day),
                                     "control": valuation(control, entry, exit_day) if control else None}
            row = {"ticker": ticker, "stage": selection[ticker], "controlTicker": control,
                   "matchStatus": "paired" if control else "unmatched" if ticker in features else "missing_features",
                   "outcomes": outcomes}
            rows.append(row)
            event = (day, row)
            events["all"].append(event)
            events[selection[ticker]].append(event)
        case_days.append({"signalDate": day, "entryDate": entry, "exitDates": exits, "cases": rows})

    def group(key):
        subset = events[key]
        return {"entries": len(subset), "signalDates": len({event[0] for event in subset}),
                "outcomes": {str(horizon): _measure(subset, horizon) for horizon in HORIZONS}}

    first_day = min(observations)
    result = {
        "schemaVersion": SCHEMA, "asOf": as_of, "firstSession": first_day,
        "archiveSessions": len(observations), "comparableSessions": comparable_days,
        "latestSelected": len(observations[as_of]),
        "missingSessions": [day for day in calendar if day >= first_day and day not in observations],
        "rejectedArchives": sorted(set(expected) - observations.keys()),
        "unknownFirstDate": censored, "missingPriorOrCurrentCoverage": missing_coverage,
        "groups": {key: group(key) for key in ("all", *STAGES.values())},
    }
    if cases is not None:
        result["caseCount"] = len(events["all"])
        cases.update({"schemaVersion": CASE_SCHEMA, "source": source, "asOf": as_of,
                      "caseCount": result["caseCount"], "days": case_days})
    return result
