"""Additive, as-observed closes for stage transitions after candidate eligibility ends.

The evaluated-only V2 price archive is immutable. Supplemental observations live
in separate content-addressed files and never backfill before the policy cutoff.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import urllib.request
from urllib.parse import quote
from zoneinfo import ZoneInfo

from archive_trend_birth_closes import load_prices
from trend_birth_intelligence import all_points, load_months, write_json
from validate_unified_review_bundle import identity

POINT_SCHEMA = "trend-birth-outcome-close-v1"
HEALTH_SCHEMA = "trend-birth-outcome-tracking-v1"
NY = ZoneInfo("America/New_York")


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return sha256(encode(value)).hexdigest()


def load_policy(path):
    value = json.loads(path.read_text())
    if (value.get("schemaVersion") != "trend-birth-outcome-policy-v1" or
            value.get("maxHorizon") != 60 or value.get("provider") != "yahoo-chart-v8" or
            not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.get("startAfterSessionDate", ""))):
        raise ValueError("Unsupported outcome tracking policy")
    return value


def active_tickers(points, calendar, day):
    positions = {d: i for i, (d, _close) in enumerate(calendar["sessions"])}
    if day not in positions:
        raise ValueError("Tracking day outside exchange calendar")
    wanted = set()
    for old, current in zip(points, points[1:]):
        signal = current["sessionDate"]
        if signal > day:
            raise ValueError("Future stage observation in tracking inputs")
        if signal < calendar["validFrom"]:
            continue  # more than 60 sessions old; never keep an unbounded watchlist
        if signal not in positions:
            raise ValueError("Stage date outside exchange sessions")
        # Keep through the next-close entry + 60 complete holding sessions.
        if positions[day] > positions[signal] + 61:
            continue
        wanted.update(t for t, value in current["stages"].items()
                      if t in old["stages"] and value[0] != old["stages"][t][0])
    return sorted(wanted)


def capture_window(day, close, now):
    # Let delayed daily feeds settle; never label a just-closed intraday bar EOD.
    return (now >= datetime.fromisoformat(close) + timedelta(minutes=20) and
            now.astimezone(NY).date().isoformat() == day)


def parse_quote(payload, ticker, day, close, now, host):
    if not capture_window(day, close, now):
        return None, "outside_same_market_day_capture_window"
    results = (payload.get("chart") or {}).get("result") or []
    if len(results) != 1 or not isinstance(results[0], dict):
        return None, "provider_no_result"
    result = results[0]
    meta = result.get("meta") or {}
    if (meta.get("symbol") != ticker or meta.get("currency") != "USD" or
            meta.get("exchangeTimezoneName") != "America/New_York"):
        return None, "provider_symbol_currency_or_venue_mismatch"
    stamp = meta.get("regularMarketTime")
    value = meta.get("regularMarketPrice")
    if (type(stamp) not in (int, float) or not math.isfinite(stamp) or
            type(value) not in (int, float) or not math.isfinite(value) or value <= 0):
        return None, "invalid_provider_quote"
    traded = datetime.fromtimestamp(stamp, tz=timezone.utc)
    if (traded.astimezone(NY).date().isoformat() != day or traded > now or
            traded.timestamp() > datetime.fromisoformat(close).timestamp() + 60):
        return None, "provider_quote_date_mismatch"
    stamps = result.get("timestamp") or []
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quotes.get("close") or []
    observed = []
    for i, bar_stamp in enumerate(stamps):
        if type(bar_stamp) not in (int, float) or not math.isfinite(bar_stamp):
            return None, "invalid_provider_bar_timestamp"
        bar_day = datetime.fromtimestamp(bar_stamp, tz=timezone.utc).astimezone(NY).date().isoformat()
        if bar_day > day:
            return None, "future_provider_bar"
        if bar_day == day and i < len(closes):
            observed.append(closes[i])
    if (len(observed) != 1 or type(observed[0]) not in (int, float) or
            not math.isfinite(observed[0]) or not math.isclose(value, observed[0], rel_tol=1e-5, abs_tol=1e-4)):
        return None, "provider_close_not_confirmed"
    return {"price": float(value), "provider": "yahoo-chart-v8", "host": host,
            "ticker": ticker, "currency": "USD", "exchangeTimezoneName": "America/New_York",
            "confirmedDailyClose": observed[0],
            "sessionDate": day, "regularMarketTime": stamp, "observedAt": now.isoformat(),
            "priceBasis": "reported-regular-close-no-dividends", "corporateActionsVerified": False}, None


def fetch_quote(ticker, day, close, now):
    if not capture_window(day, close, now):
        return None, "outside_same_market_day_capture_window"
    reason = "provider_request_failed"
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        url = f"https://{host}/v8/finance/chart/{quote(ticker, safe='')}?range=5d&interval=1d&includePrePost=false"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "StockScout-Trend-Birth-Lab/0.2"})
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.load(response)
            # Record receipt time, including requests that cross market midnight.
            observed = datetime.now(timezone.utc)
            result, reason = parse_quote(payload, ticker, day, close, observed, host)
            if result:
                return result, None
        except Exception:
            reason = "provider_request_failed"
    return None, reason


def validate_point(point, primary, policy, calendar):
    day = point.get("sessionDate")
    run, source_day, _sha = identity(point.get("source") or {})
    if (point.get("schemaVersion") != POINT_SCHEMA or day != source_day or
            day <= policy["startAfterSessionDate"] or day not in primary or
            run != primary[day]["runId"] or point.get("policySha256") != digest(policy) or
            point.get("primaryQuoteSha256") != digest(primary[day])):
        raise ValueError("Supplemental quote provenance mismatch")
    tracked = point.get("trackedTickers")
    prices, missing, proof = point.get("prices"), point.get("missing"), point.get("provenance")
    if (not isinstance(tracked, list) or tracked != sorted(set(tracked)) or
            any(not re.fullmatch(r"[A-Z0-9._-]{1,20}", t) for t in tracked) or
            not all(isinstance(x, dict) for x in (prices, missing, proof))):
        raise ValueError("Invalid supplemental quote partition")
    needed = set(tracked) - set(primary[day]["prices"])
    if set(prices) & set(missing) or set(prices) | set(missing) != needed or set(proof) != set(prices):
        raise ValueError("Incomplete supplemental quote partition")
    closes = dict(calendar["sessions"])
    for ticker, price in prices.items():
        p = proof[ticker]
        observed = datetime.fromisoformat(p["observedAt"])
        stamp = datetime.fromtimestamp(p["regularMarketTime"], tz=timezone.utc)
        if (type(price) not in (int, float) or not math.isfinite(price) or price <= 0 or
                p.get("price") != price or p.get("provider") != policy["provider"] or
                p.get("ticker") != ticker or p.get("currency") != "USD" or
                p.get("exchangeTimezoneName") != "America/New_York" or
                type(p.get("confirmedDailyClose")) not in (int, float) or
                not math.isfinite(p["confirmedDailyClose"]) or
                not math.isclose(price, p["confirmedDailyClose"], rel_tol=1e-5, abs_tol=1e-4) or
                p.get("host") not in ("query1.finance.yahoo.com", "query2.finance.yahoo.com") or
                p.get("sessionDate") != day or p.get("corporateActionsVerified") is not False or
                p.get("priceBasis") != "reported-regular-close-no-dividends" or
                not capture_window(day, closes[day], observed) or stamp > observed or
                stamp.timestamp() > datetime.fromisoformat(closes[day]).timestamp() + 60 or
                stamp.astimezone(NY).date().isoformat() != day):
            raise ValueError("Invalid as-observed supplemental close")
    if any(not isinstance(reason, str) or not reason for reason in missing.values()):
        raise ValueError("Missing supplemental quote reason")
    return point


def load_observations(directory, primary, policy, calendar):
    selected = {}
    for path in sorted(directory.glob("*.json")):
        point = json.loads(path.read_text())
        if path.name != point.get("sessionDate", "") + "--" + digest(point) + ".json":
            raise ValueError("Supplemental content-address mismatch")
        validate_point(point, primary, policy, calendar)
        day = point["sessionDate"]
        old = selected.get(day)
        if old:
            if (old["trackedTickers"] != point["trackedTickers"] or
                    identity(old["source"]) != identity(point["source"]) or
                    not (set(old["prices"]) <= set(point["prices"]) or set(point["prices"]) <= set(old["prices"])) or
                    any(t in old["prices"] and (old["prices"][t] != p or old["provenance"][t] != point["provenance"][t])
                        for t, p in point["prices"].items())):
                raise ValueError("Conflicting immutable supplemental closes")
        if old is None or len(point["prices"]) > len(old["prices"]):
            selected[day] = point
    return selected


def merged_closes(primary, observations):
    return {day: {**point, "prices": {**point["prices"], **observations.get(day, {}).get("prices", {})}}
            for day, point in primary.items()}


def health(source, policy, tracked, primary, point=None):
    day = source["sessionDate"]
    enabled = day > policy["startAfterSessionDate"]
    covered = len(set(tracked) & set(primary[day]["prices"]))
    prices = (point or {}).get("prices", {})
    missing = (point or {}).get("missing", {})
    return {"schemaVersion": HEALTH_SCHEMA, "asOf": day, "source": source,
            "policySha256": digest(policy), "startAfterSessionDate": policy["startAfterSessionDate"],
            "enabled": enabled, "trackedCount": len(tracked), "primaryCoveredCount": covered,
            "supplementalCount": len(prices), "missingCount": len(missing),
            "status": "waiting-for-next-session" if not enabled else "partial" if missing else "complete",
            "calibrationApproved": False, "historyBackfilled": False,
            "pointId": digest(point) if point else None}


def validate_health(value, source, policy, points, primary, observations, calendar):
    tracked = active_tickers(points, calendar, source["sessionDate"])
    point = observations.get(source["sessionDate"])
    expected = health(source, policy, tracked, primary, point)
    if source["sessionDate"] > policy["startAfterSessionDate"] and (
            point is None or point["trackedTickers"] != tracked or identity(point["source"]) != identity(source)):
        raise ValueError("Current supplemental observation missing or misaligned")
    if value != expected:
        raise ValueError("Outcome tracking health mismatch")
    return expected


def build(latest, stages_dir, prices_dir, directory, policy, calendar, output, now=None, fetcher=fetch_quote):
    snapshot = json.loads(latest.read_text())
    source = {key: snapshot["source"][key] for key in ("runId", "sessionDate", "unifiedManifestSha256")}
    identity(source)
    day = source["sessionDate"]
    points, primary = all_points(load_months(stages_dir)), load_prices(prices_dir)
    if not points or points[-1]["sessionDate"] != day or day not in primary:
        raise ValueError("Tracking inputs have different current sessions")
    wanted = active_tickers(points, calendar, day)
    observations = load_observations(directory, primary, policy, calendar)
    current = observations.get(day)
    if day > policy["startAfterSessionDate"]:
        if current and (current["trackedTickers"] != wanted or identity(current["source"]) != identity(source)):
            raise ValueError("Current immutable tracking demand changed")
        point = {"schemaVersion": POINT_SCHEMA, "sessionDate": day, "source": source,
                 "policySha256": digest(policy), "primaryQuoteSha256": digest(primary[day]),
                 "trackedTickers": wanted, "prices": dict((current or {}).get("prices", {})),
                 "provenance": dict((current or {}).get("provenance", {})), "missing": {}}
        needed = sorted(set(wanted) - set(primary[day]["prices"]) - set(point["prices"]))
        now = now or datetime.now(timezone.utc)
        close = dict(calendar["sessions"])[day]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda ticker: fetcher(ticker, day, close, now), needed))
        for ticker, (record, reason) in zip(needed, results):
            if record:
                point["prices"][ticker] = record["price"]
                point["provenance"][ticker] = record
            else:
                point["missing"][ticker] = reason
        validate_point(point, primary, policy, calendar)
        # A retry may add observations, never replace a previously recorded close.
        if current is None or len(point["prices"]) > len(current["prices"]):
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / (day + "--" + digest(point) + ".json")
            if target.exists() and json.loads(target.read_text()) != point:
                raise ValueError("Immutable supplemental collision")
            write_json(target, point)
            current = point
        observations[day] = current
    value = health(source, policy, wanted, primary, current)
    validate_health(value, source, policy, points, primary, observations, calendar)
    write_json(output, value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latest", type=Path, default=Path("lab/data/latest.json"))
    parser.add_argument("--stages-dir", type=Path, default=Path("lab/data/trend-birth-ticker-history"))
    parser.add_argument("--prices-dir", type=Path, default=Path("lab/data/trend-birth-price-history"))
    parser.add_argument("--directory", type=Path, default=Path("lab/data/trend-birth-outcome-quotes"))
    parser.add_argument("--policy", type=Path, default=Path("lab/data/trend-birth-outcome-policy.json"))
    parser.add_argument("--calendar", type=Path, default=Path("lab/data/exchange-sessions-v1.json"))
    parser.add_argument("--output", type=Path, default=Path("lab/data/trend-birth-outcome-tracking.json"))
    args = parser.parse_args()
    print(json.dumps(build(args.latest, args.stages_dir, args.prices_dir, args.directory,
                           load_policy(args.policy), json.loads(args.calendar.read_text()), args.output)))


if __name__ == "__main__":
    main()
