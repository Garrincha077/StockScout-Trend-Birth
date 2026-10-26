"""Fail before Git publication if an EOD bundle is stale, mixed or incomplete.

Only local, already generated inputs. No provider calls or archive repairs.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from archive_trend_birth_closes import extract, load_prices
from trend_birth_intelligence import all_points, load_months, point_from_snapshot
from validate_unified_review_bundle import identity


def read(path):
    return json.loads(path.read_bytes())


def expected_session(calendar, now):
    if (calendar.get("schemaVersion") != "xnys-eod-sessions-v1" or
            calendar.get("publicationGraceHours") != 4 or now.utcoffset() is None):
        raise ValueError("Invalid EOD calendar/policy")
    today = now.astimezone(timezone.utc).date().isoformat()
    if not calendar["validFrom"] <= today <= calendar["validThrough"]:
        raise ValueError("EOD calendar expired or outside supported range")
    sessions = calendar["sessions"]
    if not sessions or any(i and sessions[i - 1][0] >= row[0] for i, row in enumerate(sessions)):
        raise ValueError("EOD calendar unordered")
    due = [day for day, close in sessions
           if datetime.fromisoformat(close) + timedelta(hours=4) <= now]
    if not due:
        raise ValueError("No completed expected EOD session")
    return due[-1]


def validate(directory, calendar, now, previous=None):
    expected = expected_session(calendar, now)
    publication = read(directory / "publication.json")
    raw = (directory / "latest.json").read_bytes()
    latest = json.loads(raw)
    source = latest.get("source") or {}
    run, day, sha = identity(source)
    closes = dict(calendar["sessions"])
    if day not in closes or datetime.fromisoformat(closes[day]) > now:
        raise ValueError("Source is not a completed XNYS session")
    if day < expected:
        raise ValueError(f"Stale EOD source: expected {expected}, received {day}")
    if (publication.get("runId"), publication.get("sessionDate"),
            publication.get("unifiedManifestSha256")) != (run, day, sha):
        raise ValueError("Publication/source identity mismatch")
    if publication.get("sha256") != hashlib.sha256(raw).hexdigest():
        raise ValueError("Publication content digest mismatch")
    if identity(read(directory / "kell-latest.json").get("source") or {}) != (run, day, sha):
        raise ValueError("Kell source identity mismatch")
    points = all_points(load_months(directory / "trend-birth-ticker-history"))
    if not points or points[-1] != point_from_snapshot(latest):
        raise ValueError("Current stage archive differs from Review")
    quotes = load_prices(directory / "trend-birth-price-history")
    if quotes.get(day) != extract(latest, points[-1]):
        raise ValueError("Current EOD quote archive differs from Review")
    point = quotes[day]
    expected_quotes = point["expectedEvaluated"]
    if not expected_quotes or point["priceCount"] / expected_quotes < 0.99:
        raise ValueError("Current evaluated-ticker price coverage below 99%")
    if previous:
        prior = previous["sessionDate"]
        if day < prior:
            raise ValueError("EOD rollback")
        gaps = [session for session in closes if prior < session <= day and session not in quotes]
        if gaps:
            raise ValueError("New EOD session gap: " + ", ".join(gaps))
    internals = read(directory / "trend-birth-market-internals.json")
    composite = read(directory / "trend-birth-composite-backtest.json")
    forward = read(directory / "trend-birth-stage-forward.json")
    if (internals.get("latestSessionDate"), internals.get("latestRunId")) != (day, run):
        raise ValueError("Market internals source mismatch")
    if (composite.get("latestActual") or {}).get("sessionDate") != day or not composite.get("actualHistory"):
        raise ValueError("Composite EOD mismatch")
    if any(composite["actualHistory"][-1].get(key) != composite["latestActual"].get(key)
           for key in ("sessionDate", "score")):
        raise ValueError("Composite latest/history mismatch")
    if forward.get("asOf") != day or forward.get("exchangeSessions", [None])[-1] != day:
        raise ValueError("Forward EOD/calendar mismatch")
    return {"status": "ok", "sessionDate": day, "runId": run,
            "expectedSessionDate": expected, "priceCount": point["priceCount"],
            "expectedEvaluated": expected_quotes, "minimumPriceCoveragePct": 99,
            "checkedAt": now.isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("lab/data"))
    parser.add_argument("--calendar", type=Path, default=Path("lab/data/exchange-sessions-v1.json"))
    parser.add_argument("--previous-publication", type=Path)
    parser.add_argument("--now", help="Explicit aware timestamp for reproducible offline tests")
    args = parser.parse_args()
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    print(json.dumps(validate(args.directory, read(args.calendar), now,
                              read(args.previous_publication) if args.previous_publication else None)))


if __name__ == "__main__":
    main()
