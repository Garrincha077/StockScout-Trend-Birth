"""Build compact point-in-time Trend Birth setup history from daily archives."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

SCHEMA = "trend-birth-quality-history-v1"
STAGES = tuple(str(value) for value in range(5))


def point_from_snapshot(snapshot: dict) -> dict | None:
    radar = snapshot.get("trendBirthRadar") or {}
    if radar.get("schemaVersion") != "trend-birth-radar-v1":
        return None
    source = snapshot.get("source") or {}
    day = str(source.get("sessionDate") or "")
    if dt.date.fromisoformat(day).isoformat() != day:
        raise ValueError("Invalid session date")
    counts = radar.get("stageCounts") or {}
    if not isinstance(counts, dict) or set(counts) != set(STAGES):
        raise ValueError("Incomplete stage counts for " + day)
    if any(type(counts[stage]) is not int or counts[stage] < 0 for stage in STAGES):
        raise ValueError("Invalid stage counts for " + day)
    evaluated = radar.get("evaluatedCount")
    unavailable = radar.get("unavailableCount")
    if (type(evaluated) is not int or evaluated < 0
            or type(unavailable) is not int or unavailable < 0
            or sum(counts.values()) != evaluated):
        raise ValueError("Stage counts do not reconcile for " + day)
    return {
        "sessionDate": day,
        "runId": str(source.get("runId") or ""),
        "scope": str(radar.get("scope") or ""),
        "counts": {stage: counts[stage] for stage in STAGES},
        "evaluatedCount": evaluated,
        "unavailableCount": unavailable,
        "universeCount": evaluated + unavailable,
    }


def build_history(directory: Path) -> dict:
    points = []
    scope = None
    for path in sorted(directory.glob("????-??-??.json")):
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue  # Legacy pre-radar non-JSON archive.
        point = point_from_snapshot(snapshot)
        if point is None:
            continue  # Never fabricate zero observations before radar existed.
        if point["sessionDate"] != path.stem or not point["scope"]:
            raise ValueError("Invalid dated archive: " + path.name)
        if scope is not None and scope != point["scope"]:
            raise ValueError("Incompatible historical Trend Birth scopes")
        scope = point["scope"]
        points.append(point)
    return {"schemaVersion": SCHEMA, "scope": scope, "points": points}


def merge_history(retained: dict | None, observed: dict) -> dict:
    """Keep every verified daily point even if large raw snapshots are later archived elsewhere."""
    if retained is None:
        return observed
    if retained.get("schemaVersion") != SCHEMA or not isinstance(retained.get("points"), list):
        raise ValueError("Existing compact quality history has an invalid schema")
    scopes = {scope for scope in (retained.get("scope"), observed.get("scope")) if scope}
    if len(scopes) > 1:
        raise ValueError("Cannot merge incompatible Trend Birth universes")
    scope = next(iter(scopes), None)
    by_day: dict[str, dict] = {}
    for point in [*retained["points"], *observed["points"]]:
        if not isinstance(point, dict) or point.get("scope") != scope:
            raise ValueError("Invalid retained Trend Birth point scope")
        validated = point_from_snapshot({
            "source": {"sessionDate": point.get("sessionDate"), "runId": point.get("runId")},
            "trendBirthRadar": {
                "schemaVersion": "trend-birth-radar-v1",
                "scope": scope,
                "stageCounts": point.get("counts"),
                "evaluatedCount": point.get("evaluatedCount"),
                "unavailableCount": point.get("unavailableCount"),
            },
        })
        if validated != point:
            raise ValueError("Unverifiable retained Trend Birth point: " + str(point.get("sessionDate")))
        day = point["sessionDate"]
        if day in by_day and by_day[day] != point:
            raise ValueError("Conflicting historical Trend Birth readings for " + day)
        by_day[day] = point
    return {"schemaVersion": SCHEMA, "scope": scope,
            "points": [by_day[day] for day in sorted(by_day)]}



def verify_latest_point(payload: dict, latest_snapshot: dict) -> None:
    """Fail closed if published EOD does not exactly match the newest retained session."""
    latest = point_from_snapshot(latest_snapshot)
    if latest is None or not latest["scope"] or not latest["runId"]:
        raise ValueError("Latest EOD snapshot has no verifiable Trend Birth radar reading")
    points = payload["points"]
    if not points or points[-1] != latest:
        raise ValueError(
            "Latest EOD reading does not match the last retained history point: "
            + latest["sessionDate"]
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--latest", type=Path, help="Verify the latest EOD against the retained history")
    args = parser.parse_args()
    observed = build_history(args.history_dir)
    retained = json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else None
    payload = merge_history(retained, observed)
    if args.latest is not None:
        verify_latest_point(payload, json.loads(args.latest.read_text(encoding="utf-8")))
    data = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.output.exists() or args.output.read_bytes() != data:
        args.output.write_bytes(data)
    print(json.dumps({"sessions": len(payload["points"]), "scope": payload["scope"]}))


if __name__ == "__main__":
    main()
