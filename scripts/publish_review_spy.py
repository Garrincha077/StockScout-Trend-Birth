"""Publish a dated SPY reference for Review charts, inferred from Unified RS."""

import argparse
from collections import defaultdict
from datetime import date
import hashlib
import json
from math import isfinite
from pathlib import Path
import re
from statistics import median

from market_sessions import CALENDAR_PATH, bar_session_date, exchange_sessions
from pack_review_storage import raw_bytes
from publish_review_snapshot import encode, write_changed

SCHEMA = "review-spy-reference-v1"
SOURCE_FIELDS = ("runId", "sessionDate", "unifiedManifestSha256")
MIN_WITNESSES = 5
MIN_AGREEMENT = 0.8
MAX_RELATIVE_DEVIATION = 0.0005
MAX_SESSIONS = 1265


def source(row):
    return {field: row[field] for field in SOURCE_FIELDS}


def implied_close(row):
    try:
        if isinstance(row, list) and len(row) >= 7:
            stock, relative = float(row[4]), float(row[6])
        elif isinstance(row, dict):
            stock = float(row["close"])
            relative = float(row.get("rs") or row.get("relativeStrength") or row.get("relative_strength"))
        else:
            return None
        if not all(isfinite(value) and value > 0 for value in (stock, relative)):
            return None
        close = 100 * stock / relative
        return close if isfinite(close) and close > 0 else None
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def on_exchange_day(day, known, calendar_start):
    return day in known or (day < calendar_start and date.fromisoformat(day).weekday() < 5)


def infer_points(snapshot, exchange_days, calendar_start):
    """Require agreement between different tickers on each independent date."""
    day_set = set(exchange_days)
    as_of = snapshot["source"]["sessionDate"]
    votes = defaultdict(dict)
    for name in ("kellCandidates", "candidates"):
        for item in snapshot.get(name, []):
            ticker = item["ticker"]
            for bar in (item.get("chartBars") or [])[-MAX_SESSIONS:]:
                close = implied_close(bar)
                if close is None:
                    continue
                session = bar_session_date(bar)
                if not session or session > as_of:
                    continue
                # The versioned EOD calendar begins in 2025. Older dates still
                # require agreement across independently named source series.
                if not on_exchange_day(session, day_set, calendar_start):
                    continue
                votes[session].setdefault(ticker, close)
    points = []
    for session, per_ticker in sorted(votes.items()):
        if len(per_ticker) < MIN_WITNESSES:
            continue
        values = list(per_ticker.values())
        center = median(values)
        support = sum(abs(value / center - 1) <= MAX_RELATIVE_DEVIATION for value in values)
        if support >= MIN_WITNESSES and support / len(values) >= MIN_AGREEMENT:
            points.append([session, round(center, 6), support, len(values)])
    return points[-MAX_SESSIONS:]


def relative_path(snapshot_id, digest):
    return f"review-spy-runs/{snapshot_id}--{digest}.json"


def publish(directory, calendar):
    pointer = directory / "publication.json"
    manifest = json.loads(pointer.read_bytes())
    sid = manifest["snapshotId"]
    base = f"data/snapshots/{sid}.json"
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}--[a-f0-9]{64}", sid)
            or sid != f"{manifest['runId']}--{manifest['sha256']}"
            or manifest["snapshotPath"] not in (base, base + ".gz")):
        raise ValueError("Invalid Review snapshot for SPY reference")
    content = raw_bytes(directory / manifest["snapshotPath"].removeprefix("data/"))
    if hashlib.sha256(content).hexdigest() != manifest["sha256"]:
        raise ValueError("SPY reference input differs from the Review snapshot")
    snapshot = json.loads(content)
    if source(snapshot["source"]) != source(manifest):
        raise ValueError("SPY reference input differs from the Review activation")
    start = json.loads(calendar.read_bytes())["validFrom"]
    points = infer_points(snapshot, exchange_sessions(manifest["sessionDate"], calendar), start)
    document = {"schemaVersion": SCHEMA, "snapshotId": sid, "source": source(manifest),
                "benchmark": "SPY", "points": points}
    raw = encode(document)
    digest = hashlib.sha256(raw).hexdigest()
    path = relative_path(sid, digest)
    target = directory / path
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("Immutable SPY reference collision")
    write_changed(target, raw)
    manifest["spyReference"] = {"schemaVersion": SCHEMA, "path": "data/" + path, "sha256": digest,
                                "sessionCount": len(points)}
    validate(directory, manifest, calendar)
    write_changed(pointer, encode(manifest))
    return document


def validate(directory, manifest, calendar):
    ref = manifest["spyReference"]
    sid, digest = manifest["snapshotId"], ref["sha256"]
    path = relative_path(sid, digest)
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}--[a-f0-9]{64}", sid)
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
            or ref["schemaVersion"] != SCHEMA or ref["path"] != "data/" + path):
        raise ValueError("Invalid SPY reference pointer")
    raw = (directory / path).read_bytes()
    document = json.loads(raw)
    points = document["points"]
    if (hashlib.sha256(raw).hexdigest() != digest or document["schemaVersion"] != SCHEMA
            or document["snapshotId"] != sid or document["source"] != source(manifest)
            or document["benchmark"] != "SPY" or len(points) != ref["sessionCount"] or len(points) > MAX_SESSIONS):
        raise ValueError("SPY reference does not match the Review publication")
    sessions = exchange_sessions(manifest["sessionDate"], calendar)
    calendar_days = set(sessions)
    start = json.loads(calendar.read_bytes())["validFrom"]
    previous = ""
    for day, close, support, total in points:
        if (day <= previous or day > manifest["sessionDate"] or date.fromisoformat(day).isoformat() != day
                or not on_exchange_day(day, calendar_days, start)
                or not isfinite(close) or close <= 0
                or type(support) is not int or type(total) is not int
                or not MIN_WITNESSES <= support <= total or support / total < MIN_AGREEMENT):
            raise ValueError("Invalid dated SPY reference point")
        previous = day


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("lab/data"))
    parser.add_argument("--calendar", type=Path, default=CALENDAR_PATH)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    if args.validate:
        manifest = json.loads((args.directory / "publication.json").read_bytes())
        validate(args.directory, manifest, args.calendar)
    else:
        points = publish(args.directory, args.calendar)["points"]
        print(json.dumps({"sessions": len(points), "from": points[0][0] if points else None,
                          "through": points[-1][0] if points else None}))


if __name__ == "__main__":
    main()
