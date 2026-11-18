"""Publish the small, dated decision feed for the active Review snapshot."""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from early_trend_birth import MODEL as EARLY_MODEL, PHASE_ORDER
from kell_swing import MODEL as KELL_MODEL
from market_sessions import session_date
from pack_review_storage import raw_bytes
from publish_review_snapshot import encode, write_changed
from review_archive_io import archive_for_day, read_archive

SCHEMA = "trend-birth-review-changes-v1"
KEYS = ("runId", "sessionDate", "unifiedManifestSha256")
STRATEGIES = {
    "early": ("trendBirthCandidateIndex", "earlyTrend", "earlyTrendBirth", EARLY_MODEL, "phase", "invalidation"),
    "kell": ("unifiedCandidateIndex", "kellSwing", "kellSwing", KELL_MODEL, "state", "stop"),
}
ORDER = ("level_broken", "invalidated", "triggered", "advanced", "extended",
         "appeared", "lost", "state_changed", "setup_changed", "left_list", "joined_list")
LIMIT = 24


def identity(row):
    return {key: row[key] for key in KEYS}


def previous_session(calendar, day):
    sessions = [row[0] for row in calendar["sessions"]]
    if calendar.get("schemaVersion") != "xnys-eod-sessions-v1" or sessions != sorted(set(sessions)):
        raise ValueError("Invalid EOD calendar for change feed")
    if day not in sessions:
        raise ValueError("Change feed day is outside the EOD calendar")
    index = sessions.index(day)
    return sessions[index - 1] if index else None


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value > 0 else None


def supports(snapshot, strategy):
    if strategy == "early":
        return (snapshot.get("earlyTrendResearch") or {}).get("model") == EARLY_MODEL
    return isinstance((snapshot.get("shortlists") or {}).get("kellSwing"), list)


def observations(snapshot, strategy):
    index, field, shortlist, model, state_key, _ = STRATEGIES[strategy]
    day = snapshot["source"]["sessionDate"]
    candidates = snapshot.get(index)
    if not isinstance(candidates, list):
        raise ValueError("Missing full candidate index: " + index)
    listed = {row["ticker"] for row in snapshot.get("shortlists", {}).get(shortlist, [])}
    result = {}
    for row in candidates:
        ticker = row["ticker"]
        if ticker in result:
            raise ValueError("Duplicate change-feed ticker: " + ticker)
        signal = row.get(field) or {}
        if signal and (signal.get("model") != model or signal.get("sessionDate") != day):
            raise ValueError("Invalid change-feed plan provenance: " + ticker)
        radar = row.get("trendBirth") or {}
        close = (number(radar.get("metrics", {}).get("price"))
                 if radar.get("available") is True and session_date(radar.get("barDate")) == day else None)
        close = (number(signal.get("signalClose")) or close) if strategy == "kell" else close
        result[ticker] = {"state": signal.get(state_key), "setup": signal.get("setup"),
                          "close": close, "listed": ticker in listed, "plan": signal}
    return result


def reference_closes(snapshot, day, tickers):
    # A prior fixed price can be reused only when the current feed still reports
    # the same value for that past session. This catches adjusted chart history.
    closes = {}
    for group in (snapshot.get("candidates", []), snapshot.get("kellCandidates", []),
                  snapshot.get("trendBirthCandidateIndex", []), *(
                      rows for rows in snapshot.get("shortlists", {}).values() if isinstance(rows, list)
                  )):
        for row in group:
            ticker = row["ticker"]
            if ticker not in tickers or ticker in closes:
                continue
            for bar in (row.get("chartBars") or [])[-6:]:
                if not isinstance(bar, dict) and (not isinstance(bar, list) or len(bar) < 5):
                    continue
                stamp, close = ((bar.get("time") or bar.get("date"), bar.get("close"))
                                if isinstance(bar, dict) else (bar[0], bar[4]))
                if session_date(stamp) == day and number(close):
                    closes[ticker] = close
                    break
    return closes


def difference(before, after, reference, stop_key):
    old, new = before["state"], after["state"]
    level = number(before["plan"].get(stop_key))
    if (level is not None and reference is not None and
            math.isclose(reference, before["close"], rel_tol=1e-6, abs_tol=1e-4) and
            before["close"] > level >= after["close"]):
        return "level_broken", level
    if old == new:
        if before["setup"] != after["setup"]:
            return "setup_changed", None
        if before["listed"] != after["listed"]:
            return ("joined_list" if after["listed"] else "left_list"), None
        return None, None
    if new in ("triggered", "extended", "invalidated"):
        return new, None
    if old is None:
        return "appeared", None
    if new is None:
        return "lost", None
    if old in PHASE_ORDER and new in PHASE_ORDER and PHASE_ORDER[new] < PHASE_ORDER[old]:
        return "advanced", None
    return "state_changed", None


def public(row):
    return {key: row[key] for key in ("state", "setup", "close", "listed")}


def strategy_feed(current, prior, strategy):
    if not supports(current, strategy):
        return {"status": "unavailable", "compared": 0, "count": 0, "events": [], "current": []}
    after = observations(current, strategy)
    today = [{"ticker": ticker, **public(row)} for ticker, row in after.items() if row["listed"] and row["state"]]
    # Preserve the app's existing selection order on the opening-day view.
    positions = {row["ticker"]: i for i, row in enumerate(current["shortlists"][STRATEGIES[strategy][2]])}
    today.sort(key=lambda item: positions[item["ticker"]])
    if prior is None or not supports(prior, strategy):
        return {"status": "no_baseline", "compared": 0, "count": 0, "events": [], "current": today}
    before = observations(prior, strategy)
    shared = {ticker for ticker in before.keys() & after.keys()
              if before[ticker]["close"] is not None and after[ticker]["close"] is not None}
    interesting = {ticker for ticker in shared if before[ticker]["state"] or after[ticker]["state"]}
    refs = reference_closes(current, prior["source"]["sessionDate"],
                            {ticker for ticker in interesting if before[ticker]["state"]})
    events = []
    for ticker in interesting:
        old, new = before[ticker], after[ticker]
        event, level = difference(old, new, refs.get(ticker), STRATEGIES[strategy][-1])
        if event:
            events.append({"ticker": ticker, "kind": event, "priorLevel": level,
                           "before": public(old), "after": public(new)})
    events.sort(key=lambda item: (ORDER.index(item["kind"]), not item["after"]["listed"],
                                  not item["before"]["listed"], item["ticker"]))
    return {"status": "compared" if shared else "no_overlap", "compared": len(shared),
            "count": len(events), "events": events[:LIMIT], "current": today}


def build(directory, calendar):
    pointer = directory / "publication.json"
    manifest = json.loads(pointer.read_bytes())
    sid = manifest["snapshotId"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}--[a-f0-9]{64}", sid):
        raise ValueError("Invalid change-feed snapshot ID")
    base = f"data/snapshots/{sid}.json"
    if manifest["snapshotPath"] not in (base, base + ".gz"):
        raise ValueError("Invalid snapshot path for Review change feed")
    raw = raw_bytes(directory / manifest["snapshotPath"].removeprefix("data/"))
    current = json.loads(raw)
    if hashlib.sha256(raw).hexdigest() != manifest["sha256"] or identity(current["source"]) != identity(manifest):
        raise ValueError("Change-feed data differs from current Review")
    day = previous_session(calendar, manifest["sessionDate"])
    prior = None
    if day:
        try:
            prior = read_archive(archive_for_day(directory / "history", day))
        except FileNotFoundError:
            pass
        if prior is not None and prior["source"]["sessionDate"] != day:
            raise ValueError("Prior Review archive session mismatch")
    payload = {"schemaVersion": SCHEMA, "snapshotId": sid, "source": identity(manifest),
               "previousSession": day, "baseline": identity(prior["source"]) if prior else None,
               "strategies": {strategy: strategy_feed(current, prior, strategy) for strategy in STRATEGIES}}
    content = encode(payload)
    digest = hashlib.sha256(content).hexdigest()
    path = f"review-change-runs/{sid}--{digest}.json"
    target = directory / path
    if target.exists() and target.read_bytes() != content:
        raise ValueError("Immutable Review change-feed collision")
    write_changed(target, content)
    manifest["changes"] = {"schemaVersion": SCHEMA, "path": "data/" + path, "sha256": digest}
    validate(directory, manifest, calendar)
    write_changed(pointer, encode(manifest))
    return payload


def validate(directory, manifest, calendar):
    ref = manifest["changes"]
    sid, digest = manifest["snapshotId"], ref["sha256"]
    path = f"review-change-runs/{sid}--{digest}.json"
    if ref["path"] != "data/" + path or ref["schemaVersion"] != SCHEMA or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("Invalid Review change-feed reference")
    content = (directory / path).read_bytes()
    payload = json.loads(content)
    previous = previous_session(calendar, manifest["sessionDate"])
    if (hashlib.sha256(content).hexdigest() != digest or payload["schemaVersion"] != SCHEMA or
            payload["source"] != identity(manifest) or payload["snapshotId"] != sid or
            payload["previousSession"] != previous or set(payload["strategies"]) != set(STRATEGIES) or
            (payload["baseline"] and payload["baseline"]["sessionDate"] != previous)):
        raise ValueError("Review change feed differs from active publication")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("lab/data"))
    parser.add_argument("--calendar", type=Path, default=Path("lab/data/exchange-sessions-v1.json"))
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    calendar = json.loads(args.calendar.read_bytes())
    if args.validate:
        validate(args.directory, json.loads((args.directory / "publication.json").read_bytes()), calendar)
    else:
        payload = build(args.directory, calendar)
        print(json.dumps({key: {"status": value["status"], "changes": value["count"]}
                          for key, value in payload["strategies"].items()}))


if __name__ == "__main__":
    main()
