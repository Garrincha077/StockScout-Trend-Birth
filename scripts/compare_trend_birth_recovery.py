"""Build an isolated V3 replay and event/outcome comparison. Never mutate V2."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from archive_trend_birth_closes import load_prices
from recover_trend_birth_eod import RADAR_SHA256, PINNED_MANIFESTS, validate_observed_watchlist
from preserve_unified_eod_evidence import SOURCES
from trend_birth_intelligence import SCOPE, all_points, load_months, _point_counts
import trend_birth_stage_forward as forward


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def validate_recovered(value):
    source = value.get("source") or {}
    tracked = validate_observed_watchlist(source.get("trackedInput") or {})
    expected_prior = {"2026-10-15":"2026-10-14", "2026-10-19":"2026-10-16"}
    pinned = next((row for row in SOURCES if row["sessionDate"] == source.get("sessionDate")), None)
    if (value.get("schemaVersion") != "trend-birth-recovered-input-v3" or value.get("scope") != SCOPE or
        pinned is None or source.get("originalArtifact") != pinned or
        source.get("radarSha256") != RADAR_SHA256 or
        source.get("unifiedManifestSha256") != PINNED_MANIFESTS.get(source.get("sessionDate")) or
        tracked["sourceSessionDate"] != expected_prior.get(source.get("sessionDate")) or
        source.get("trackedMembershipExactOnRecoveredSession") is not False or
        source.get("observedByTrendBirthOnSession") is not False or source.get("networkFallbacks") != 0):
        raise ValueError("Unverified recovery input/provenance")
    if source["runId"] != source["sessionDate"]+"-eod-"+str(pinned["workflowRunId"])+"-1":
        raise ValueError("Recovered run differs from original artifact")
    point, close = value["stagePoint"], value["closePoint"]
    _point_counts(point)
    for row in (point, close):
        if row["sessionDate"] != source["sessionDate"] or row["runId"] != source["runId"]:
            raise ValueError("Recovery source/session mismatch")
    if (set(close["prices"]) != set(point["stages"]) or close["priceCount"] != len(close["prices"]) or
        close["expectedEvaluated"] != point["evaluatedCount"]):
        raise ValueError("Recovery close/stage universe mismatch")
    forward._price_series({close["sessionDate"]: close})


def replay(points, closes, calendar, as_of):
    if set(closes) != {p["sessionDate"] for p in points}:
        raise ValueError("Replay price/stage dates differ")
    for point in points:
        close = closes[point["sessionDate"]]
        if close["runId"] != point["runId"] or close["expectedEvaluated"] != point["evaluatedCount"]:
            raise ValueError("Replay source identity mismatch")
    events = forward._events(points)
    forward._mature(events, forward._price_series(closes), calendar)
    return events, forward.report(events, calendar, as_of, closes)


def event_map(events):
    return {(row["sessionDate"], event[0], event[1], event[2]):
            {"previousSessionDate": row["previousSessionDate"], "outcomes": event[3]}
            for row in events for event in row["events"]}


def compare(stages, prices, baseline_report, recovered_dir, output, baseline_commit):
    outcomes_dir = stages.parent / "trend-birth-forward-eod-history"
    protected = [stages.resolve(), prices.resolve(), baseline_report.resolve(), recovered_dir.resolve()]
    if outcomes_dir.exists():
        protected.append(outcomes_dir.resolve())
    out = output.resolve()
    if output.exists() or any(out == p or out in p.parents or p in out.parents for p in protected):
        raise ValueError("V3 output must be new and separate from all inputs")
    baseline_paths = [*stages.glob("????-??.json"), *prices.glob("????-??.json"),
                      *outcomes_dir.glob("????-??.json"), baseline_report]
    hashes = {str(p): digest(p) for p in baseline_paths}
    points = all_points(load_months(stages))
    closes = load_prices(prices)
    published = json.loads(baseline_report.read_bytes())
    calendar = published.get("exchangeSessions")
    if not calendar or calendar[-1] != published["asOf"]:
        raise ValueError("A verified aligned exchange calendar is required")
    before_events, before = replay(points, closes, calendar, published["asOf"])
    # Prove that a fresh replay reproduces every published baseline sample/value.
    for key in ("byHorizon", "stageTransitions", "dataQuality"):
        if before[key] != published[key]:
            raise ValueError("Baseline replay does not reproduce published V2: " + key)
    after_points, after_closes = copy.deepcopy(points), copy.deepcopy(closes)
    recovery_files = sorted(recovered_dir.glob("????-??-??.json"))
    if {p.stem for p in recovery_files} != {s["sessionDate"] for s in SOURCES}:
        raise ValueError("Exactly the two pinned missing sessions are required")
    for path in recovery_files:
        recovered = json.loads(path.read_bytes())
        validate_recovered(recovered)
        day = recovered["source"]["sessionDate"]
        if day in after_closes or any(p["sessionDate"] == day for p in after_points):
            raise ValueError("Recovery would overwrite an observed EOD session")
        after_points.append(recovered["stagePoint"])
        after_closes[day] = recovered["closePoint"]
    after_points.sort(key=lambda point: point["sessionDate"])
    after_events, after = replay(after_points, after_closes, calendar, published["asOf"])
    after["schemaVersion"] = "trend-birth-stage-forward-v3"
    after["priceSource"] = "observed V2 closes plus reconstructed pinned Unified EOD inputs"
    after["reconstructedSessions"] = sorted(row["sessionDate"] for row in SOURCES)
    after["calibrationApproved"] = False
    for stages_for_horizon in after["byHorizon"].values():
        for row in stages_for_horizon.values():
            row["eligibleForCalibration"] = False
    old, new = event_map(before_events), event_map(after_events)
    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    shared = old.keys() & new.keys()
    predecessor_changes = sorted(key for key in shared if old[key]["previousSessionDate"] != new[key]["previousSessionDate"])
    outcome_changes = sorted(key for key in shared if old[key]["outcomes"] != new[key]["outcomes"])
    result = {
        "schemaVersion": "trend-birth-recovery-comparison-v3", "scope": SCOPE, "asOf": published["asOf"],
        "baselineCommit": baseline_commit, "baselineReplayMatchesPublished": True,
        "baselineInputSha256": {str(p.relative_to(stages.parent)) if p.is_relative_to(stages.parent) else p.name: hashes[str(p)] for p in baseline_paths},
        "recoveredInputSha256": {p.name: digest(p) for p in recovery_files},
        "before": before, "after": after,
        "events": {"added": added, "removed": removed, "changedPredecessor": predecessor_changes,
                   "changedOutcomes": [{"event": key, "before": old[key], "after": new[key]} for key in outcome_changes]},
        "migration": {"activated": False, "v2InputsUntouched": True,
                      "productionSelectionChanged": False, "compositeRecalibrated": False,
                      "calibrationApproved": False, "requiresVersionedMigration": True,
                      "rollback": "Continue serving the unchanged V2 archives/report; V3 has no production pointer"},
        "limitations": ["Recovered sessions were recomputed, not originally observed by Trend Birth",
                        "Tracked membership uses the last observed prior EOD; exact intervening owner state is unknown",
                        "Missing/stale archived charts remain unavailable; no contemporary Yahoo fallback",
                        "Retained quote contract is not a corporate-action/delisting quality certification",
                        "20D/60D sample maturity and independent holdout are still required"],
    }
    if any(digest(p) != hashes[str(p)] for p in baseline_paths):
        raise ValueError("V2 inputs changed during replay")
    # V3 schemas deliberately cannot be passed silently to the V1/V2 publishers.
    for name, rows, schema in (("stage-history", after_points, "trend-birth-ticker-month-v3"),
                               ("price-history", list(after_closes.values()), "trend-birth-close-month-v3"),
                               ("outcomes", after_events, "trend-birth-forward-month-v3")):
        months = {}
        for row in sorted(rows, key=lambda r: r["sessionDate"]):
            months.setdefault(row["sessionDate"][:7], []).append(row)
        for month, sessions in months.items():
            write(output / name / (month + ".json"), {"schemaVersion": schema, "scope": SCOPE, "month": month, "sessions": sessions})
    write(output / "comparison.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("stages", "prices", "baseline-report", "recovered", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--baseline-commit", required=True)
    args = parser.parse_args()
    result = compare(args.stages, args.prices, args.baseline_report, args.recovered, args.output, args.baseline_commit)
    print(json.dumps({"before": result["before"]["dataQuality"], "after": result["after"]["dataQuality"],
                      "events": {key: len(value) for key, value in result["events"].items()}}), flush=True)


if __name__ == "__main__":
    main()
