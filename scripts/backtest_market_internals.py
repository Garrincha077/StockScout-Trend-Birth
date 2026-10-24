#!/usr/bin/env python3
"""Walk-forward ETF-proxy backtest for Trend Birth market-internals composite.

This is NOT a replay of historical StockScout stock candidates. It reconstructs
stage-like states from adjusted CLOSES of fourteen pre-selected equity ETFs; real
Trend Birth uses full OHLC (ATR), while this proxy uses close-volatility.
The entire multi-year test is out-of-sample by calendar year.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
import hashlib
import io
import json
import math
from pathlib import Path
from statistics import mean, pstdev
from urllib.request import urlopen

SOURCE_COMMIT = "65a079329e379e104495f459e12e76a8f995585a"
SOURCE_URL = "https://raw.githubusercontent.com/manisahni/marketdata/" + SOURCE_COMMIT + "/daily_adjclose.csv"
SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "QQQ", "IWM", "EFA", "EEM", "VNQ")
MIN_ASSETS = 12
HORIZON = 20
STEP = 10
FIELDS = ("breadth", "pressure", "velocity", "acceleration", "flow", "persistence")
PROFILES = (
    ("balanced", (2, 2, 1, 1, 1, 1), (1, 1, 1, 1, 1, 1)),
    ("breadth", (5, 2, 0, 0, 0, 1), (1, 1, 1, 1, 1, 1)),
    ("pressure", (2, 5, 0, 0, 0, 1), (1, 1, 1, 1, 1, 1)),
    ("momentum", (1, 1, 5, 1, 3, 1), (1, 1, 1, 1, 1, 1)),
    ("acceleration", (1, 1, 2, 5, 2, 1), (1, 1, 1, 1, 1, 1)),
    ("flow", (1, 1, 1, 1, 5, 1), (1, 1, 1, 1, 1, 1)),
    ("persistence", (1, 1, 1, 1, 1, 5), (1, 1, 1, 1, 1, 1)),
    ("trend", (3, 3, 2, 1, 2, 3), (1, 1, 1, 1, 1, 1)),
    ("early-birth", (1, 1, 3, 3, 3, 1), (1, 1, 1, 1, 1, 1)),
    ("strong-trend", (3, 3, 0, 0, 0, 3), (1, 1, 1, 1, 1, 1)),
    ("recovery", (2, 2, 3, 3, 3, 1), (-1, -1, 1, 1, 1, 1)),
)
REGIME_YEARS = (2008, 2011, 2015, 2018, 2020, 2022, 2024)
SCHEMA = "trend-birth-composite-backtest-v1"


def _number(s: str) -> float | None:
    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def empty_equity_row(row: dict) -> bool:
    # Entire US equity session missing; VIX/rates alone do not make it a trading day.
    return _number(row.get("SPY")) is None and all(_number(row.get(symbol)) is None for symbol in SECTORS)


def load_prices(csv_text: str) -> tuple[list[date], dict[str, list[float | None]]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    required = set(SECTORS) | {"SPY", "QQQ", "^VIX", "Date"}
    if not required.issubset(reader.fieldnames or ()):
        raise ValueError("Missing required ETF/VIX columns")
    days: list[date] = []
    values = {col: [] for col in required if col != "Date"}
    for row in reader:
        d = date.fromisoformat(row["Date"])
        # Some source rows represent closed exchanges (e.g. US Memorial Day)
        # or an unfinished tail: VIX may be present while every stock/ETF is blank.
        if empty_equity_row(row):
            continue
        if _number(row.get("SPY")) is None:
            raise ValueError("Missing benchmark SPY on a populated equity session: "+d.isoformat())
        if days and d <= days[-1]:
            raise ValueError("Prices are not strictly chronological")
        days.append(d)
        for symbol in values:
            values[symbol].append(_number(row.get(symbol)))
    if len(days) < 4800 or days[0].year > 2004 or days[-1].year < 2025:
        raise ValueError("Historical price data is incomplete")
    i = days.index(date(2020, 3, 16))
    if round(values["^VIX"][i], 2) != 82.69:
        raise ValueError("Source integrity checkpoint failed: VIX 2020-03-16")
    i = days.index(date(2018, 2, 5))
    if round(values["^VIX"][i], 2) != 37.32:
        raise ValueError("Source integrity checkpoint failed: VIX 2018-02-05")
    return days, values


def ema(values: list[float | None], span: int) -> list[float | None]:
    alpha = 2 / (span + 1)
    out = []
    current = None
    for value in values:
        current = None if value is None else value if current is None else (alpha * value + (1-alpha) * current)
        out.append(current)
    return out


def sma(values: list[float | None], span: int) -> list[float | None]:
    out = []
    for i in range(len(values)):
        subset = values[max(0, i-span+1):i+1]
        out.append(mean(subset) if len(subset) == span and all(v is not None for v in subset) else None)
    return out


def stage_history(days: list[date], close: list[float | None]) -> list[int | None]:
    """Close-only APPROXIMATION of the repo's 0..4 hierarchical radar stages."""
    n = len(days)
    e10, e20, s50 = ema(close, 10), ema(close, 20), sma(close, 50)
    daily_move = [None] + [abs(close[i]-close[i-1]) if close[i] is not None and close[i-1] is not None else None for i in range(1,n)]
    volatility = ema(daily_move, 14)
    # The true 14-day ATR uses highs/lows. 1.8 is a FIXED, non-fitted proxy scale.
    atr = [v * 1.8 if v is not None else None for v in volatility]
    weekly = []
    week_ends = []
    current_week = None
    for i, day in enumerate(days):
        iso = day.isocalendar()
        key = (iso.year, iso.week)
        if current_week != key:
            current_week = key
            week_ends.append(i)
            weekly.append(close[i])
        else:
            week_ends[-1] = i
            weekly[-1] = close[i]
    weekly_sma = sma(weekly, 30)
    daily_to_week = []
    w = -1
    for i, day in enumerate(days):
        while w + 1 < len(week_ends) and week_ends[w+1] < i:
            w += 1
        # A week is complete only on Friday, as in the production evaluator.
        if day.weekday() == 4:
            wi = w+1
        else:
            wi = w
        daily_to_week.append(wi)
    near, compressed, sane = [False]*n, [False]*n, [False]*n
    result = [None]*n
    for i in range(n):
        a = atr[i]
        if close[i] is None or s50[i] is None or a is None or a <= 0:
            continue
        near[i] = s50[i]-.75*a <= close[i] <= s50[i]+1.25*a
        compressed[i] = abs(e10[i]-e20[i]) <= .35*a
        sane[i] = close[i] <= e20[i]+1.5*a
    for i in range(170, n):
        wi = daily_to_week[i]
        if wi < 34 or weekly_sma[wi] is None or weekly_sma[wi-4] is None:
            continue
        a = atr[i]
        if any(v is None for v in (a, s50[i], s50[i-5], e10[i], e10[i-3], e20[i], e20[i-3], close[i], close[i-1])):
            continue
        slope10 = (e10[i]-e10[i-3])/(3*a)
        slope20 = (e20[i]-e20[i-3])/(3*a)
        trend = (s50[i] > s50[i-5] and weekly_sma[wi] > weekly_sma[wi-4]
                 and close[i] >= s50[i]-1.5*a and sane[i])
        closely = trend and near[i] and compressed[i]
        ready = closely and slope10 >= -.05 and slope20 >= -.03 and (slope10 > 0 or slope20 > 0)
        spread = e10[i]-e20[i]
        fresh_cross = spread > 0 and e10[i-1] <= e20[i-1]
        expanding = spread > 0 and spread > e10[i-1]-e20[i-1]
        trigger = (trend and any(near[j] and compressed[j] and sane[j] for j in range(i-9,i+1))
                   and slope10 > 0 and slope20 >= 0 and spread > 0
                   and close[i] > e10[i] and close[i] > e20[i] and (fresh_cross or expanding))
        result[i] = 4 if trigger else 3 if ready else 2 if closely else 1 if trend else 0
    return result


def linear_slope(values: list[float], end: int, span: int = 5) -> float | None:
    if end-span+1 < 0 or any(v is None for v in values[end-span+1:end+1]):
        return None
    segment = values[end-span+1:end+1]
    middle = (span-1)/2
    denominator = span*(span*span-1)/12
    return sum((i-middle)*v for i,v in enumerate(segment))/denominator


def percent_rank(value: float, history: list[float]) -> float:
    clean = [x for x in history if x is not None and math.isfinite(x)]
    if len(clean) < 12 or value is None:
        return 50.0
    less = sum(x < value for x in clean)
    same = sum(x == value for x in clean)
    return 100*(less+.5*same)/len(clean)


def feature_rows(days: list[date], prices: dict) -> list[dict | None]:
    stages = {symbol: stage_history(days, prices[symbol]) for symbol in SECTORS}
    qseries: list[float | None] = []
    pseries: list[float | None] = []
    daily = []
    for i, day in enumerate(days):
        state = [stages[s][i] for s in SECTORS]
        state = [stage for stage in state if stage is not None]
        if len(state) < MIN_ASSETS:
            qseries.append(None);pseries.append(None);daily.append(None);continue
        q = sum(s >= 3 for s in state)*100/len(state)
        p = sum(state)*25/len(state)
        qseries.append(q);pseries.append(p)
        v = linear_slope(qseries,i,5)
        pv = linear_slope(qseries,i-5,5)
        daily.append({
            "date":day.isoformat(),
            "breadth":q, "pressure":p, "velocity":v,
            "acceleration":v-pv if v is not None and pv is not None else None,
            "flow":q-qseries[i-1] if i and qseries[i-1] is not None else None,
            "persistence":mean(qseries[i-9:i+1]) if i>=9 and all(z is not None for z in qseries[i-9:i+1]) else None,
            "stageCounts":{str(j):state.count(j) for j in range(5)},
        })
    for i, rec in enumerate(daily):
        if rec is None:
            continue
        for field in FIELDS:
            x = rec[field]
            past = [p[field] for p in daily[max(0,i-252):i] if p is not None and p[field] is not None]
            rec[field+"Rank"] = percent_rank(x,past) if x is not None else 50.0
    return daily


def profile_score(point: dict, profile) -> float:
    _, weights, signs = profile
    total = sum(weights)
    return round(sum(w * (point[k+"Rank"] if sign > 0 else 100-point[k+"Rank"])
                     for k,w,sign in zip(FIELDS,weights,signs))/total, 4)


def forward_label(prices: list[float | None], index: int) -> float | None:
    # Signal after t close: earliest PRICE we can use is t+1 close.
    # Adjusted closes mean this is an illustrative total-return proxy, not a fillable open order.
    if index + HORIZON + 1 >= len(prices):
        return None
    entry, exit_ = prices[index+1], prices[index+HORIZON+1]
    return (exit_/entry-1)*100 if entry and exit_ else None


def correlation(values: list[tuple[float,float]]) -> float:
    if len(values) < 6:
        return 0.0
    x, y = zip(*values)
    mx,my = mean(x),mean(y)
    sx = math.sqrt(sum((a-mx)**2 for a in x))
    sy = math.sqrt(sum((b-my)**2 for b in y))
    return sum((a-mx)*(b-my) for a,b in values)/(sx*sy) if sx*sy else 0.


def summary(records: list[dict]) -> dict:
    if not records:
        return {"n":0}
    ranked = sorted(records, key=lambda r:r["score"])
    k = max(1,len(ranked)//4)
    low, high = ranked[:k], ranked[-k:]
    return {
        "n":len(records),
        "highScoreMean20dPct":round(mean(r["futureReturnPct"] for r in high),3),
        "lowScoreMean20dPct":round(mean(r["futureReturnPct"] for r in low),3),
        "topMinusBottomPp":round(mean(r["futureReturnPct"] for r in high)-mean(r["futureReturnPct"] for r in low),3),
        "highScorePositiveRatePct":round(100*mean(r["futureReturnPct"]>0 for r in high),1),
        "allMean20dPct":round(mean(r["futureReturnPct"] for r in ranked),3),
        "scoreReturnPearson":round(correlation([(r["score"],r["futureReturnPct"]) for r in records]),3),
    }


def choose_profile(history: list[dict]):
    # Scores evaluated only against returns that ended BEFORE this year.
    # Stability reward: mean within-year correlations, penalize dispersion.
    years = sorted({r["year"] for r in history})
    if len(years) < 3 or len(history) < 60:
        return PROFILES[0]
    best = (-1e99, PROFILES[0])
    for profile in PROFILES:
        correlations = []
        for y in years:
            subset = [r for r in history if r["year"]==y]
            pairs = [(profile_score(r["features"],profile),r["futureReturnPct"]) for r in subset]
            if len(pairs) >= 9:
                correlations.append(correlation(pairs))
        if len(correlations) < 3:
            continue
        objective = mean(correlations) - .35*pstdev(correlations)
        if objective > best[0]+1e-12:
            best = (objective,profile)
    return best[1]


def actual_features(points: list[dict]) -> list[dict]:
    normalized = []
    for i,p in enumerate(points):
        q = p["qualityBreadthPct"]
        pv = linear_slope([x["qualityBreadthPct"] for x in points],i-5,5)
        v = linear_slope([x["qualityBreadthPct"] for x in points],i,5)
        normalized.append({
            "date":p["sessionDate"],
            "breadth":q, "pressure":p["pressurePct"], "velocity":v,
            "acceleration":v-pv if v is not None and pv is not None else None,
            "flow":p.get("matchedQualityDeltaPp"),
            "persistence":mean(x["qualityBreadthPct"] for x in points[i-9:i+1]) if i>=9 else None,
        })
    for i,p in enumerate(normalized):
        for field in FIELDS:
            past = [x[field] for x in normalized[max(0,i-252):i] if x[field] is not None]
            p[field+"Rank"] = percent_rank(p[field],past)
    return normalized


def run(prices_csv: str, actual_payload: dict) -> dict:
    days, prices = load_prices(prices_csv)
    features = feature_rows(days,prices)
    samples = []
    for i in range(260, len(days)-HORIZON-1, STEP):
        rec = features[i]
        target = forward_label(prices["SPY"],i)
        if rec is None or target is None or any(rec[k] is None for k in FIELDS):
            continue
        samples.append({
            "date":rec["date"],"year":days[i].year,
            "labelEnd":days[i+HORIZON+1].isoformat(),
            "futureReturnPct":target,"features":rec,
            "vix":prices["^VIX"][i],
        })
    if len(samples) < 350:
        raise ValueError("Not enough point-in-time proxy samples")
    out = []
    by_year = []
    profiles = {}
    for year in range(2008,days[-1].year+1):
        training = [r for r in samples if r["year"] < year and r["labelEnd"] < f"{year}-01-01"]
        selected = choose_profile(training)
        profiles[str(year)] = selected[0]
        year_oos = []
        for rec in samples:
            if rec["year"] == year:
                point = {"date":rec["date"],"year":year,"score":profile_score(rec["features"],selected),
                         "futureReturnPct":rec["futureReturnPct"],"vix":rec["vix"],"profile":selected[0]}
                out.append(point);year_oos.append(point)
        by_year.append({"year":year,"profile":selected[0],**summary(year_oos)})
    if len(out) < 180:
        raise ValueError("Not enough held-out samples")
    latest_profile = choose_profile(samples)
    actual = actual_features(actual_payload["points"])
    now = actual[-1]
    component = {k:round(now[k+"Rank"],1) for k in FIELDS}
    latest_score = profile_score(now,latest_profile)
    regime_summary = []
    for label,filter_fn in (
        ("2008 GFC",lambda r:r["year"]==2008),
        ("2011 sovereign debt",lambda r:r["year"]==2011),
        ("2015-16 industrial correction",lambda r:r["year"] in (2015,2016)),
        ("2018 tightening",lambda r:r["year"]==2018),
        ("2020 pandemic",lambda r:r["year"]==2020),
        ("2022 inflation bear",lambda r:r["year"]==2022),
        ("2023-24 rally",lambda r:r["year"] in (2023,2024)),
        ("High volatility (VIX >= 30)",lambda r:r["vix"] is not None and r["vix"]>=30),
        ("Lower volatility (VIX < 20)",lambda r:r["vix"] is not None and r["vix"]<20),
    ):
        group = [r for r in out if filter_fn(r)]
        regime_summary.append({"regime":label,**summary(group)})
    weights = {k:w for k,w in zip(FIELDS,latest_profile[1])}
    directions = {k:sign for k,sign in zip(FIELDS,latest_profile[2])}
    last_valid_proxy = next(p for p in reversed(features) if p is not None)
    good_years = sum(r.get("topMinusBottomPp",0)>0 for r in by_year if r["n"]>=8)
    return {
        "schemaVersion":SCHEMA,
        "scope":"equity-etf-proxy-not-historical-stockscout",
        "source":{"url":SOURCE_URL,"sha256":hashlib.sha256(prices_csv.encode()).hexdigest(),
                  "firstDate":days[0].isoformat(),"lastDate":days[-1].isoformat(),
                  "description":"Dividend-adjusted closes of 14 sector/region/size/REIT equity ETFs, not OHLC or delisted stocks", "droppedEmptyEquityRows":len(list(csv.DictReader(io.StringIO(prices_csv))))-len(days)},
        "method":{"horizonTradingDays":HORIZON,"entry":"next-session adjusted CLOSE","exit":"adjusted CLOSE 20 sessions after entry",
                  "samplingStrideSessions":STEP,"walkForward":"annual profile selection using only previously completed labeled calendar years",
                  "featureRankWindowSessions":252,"atrProxy":"1.8 x EMA14 absolute close move; no high/low",
                  "survivorship":"14 pre-specified long-lived equity ETFs (>=12 evaluated/session), not a delisting-complete stock universe",
                  "testedProfiles":len(PROFILES),"minHistoryYears":3,
                  "status":"EXPLORATORY ETF PROXY, NOT AN AUDITED STOCKSCOUT SIGNAL"},
        "oos":{"startYear":2008,"endYear":by_year[-1]["year"],**summary(out),
               "positiveSpreadYears":good_years,"testedYears":len([r for r in by_year if r["n"]>=8]),
               "yearly":by_year,"regimes":regime_summary},
        "calibration":{"selectedProfile":latest_profile[0],"weights":weights,"directions":directions,
                       "selection":"historical yearwise score/forward-return correlation minus across-year variability",
                       "trainingYears":sorted({r["year"] for r in samples}),"sampleCount":len(samples)},
        "latestActual":{"sessionDate":actual_payload["latestSessionDate"],"score":latest_score,
                        "components":component,"actualHistoryCount":len(actual),
                        "interpretation":"INDICATIVE transfer of ETF-proxy weights onto ranks of the short REAL StockScout EOD series; NOT out-of-sample validated"},
        "lastProxy":{"sessionDate":last_valid_proxy["date"],"score":profile_score(last_valid_proxy,latest_profile)},
    }


def refresh_actual(report: dict, actual_payload: dict) -> dict:
    if (report.get("schemaVersion") != SCHEMA or not isinstance(report.get("calibration"),dict)):
        raise ValueError("Backtest calibration missing or incompatible")
    selected_name = report["calibration"]["selectedProfile"]
    selected = next((p for p in PROFILES if p[0] == selected_name),None)
    if selected is None:
        raise ValueError("Unknown frozen calibration profile")
    points = actual_payload["points"]
    actual = actual_features(points)
    now = actual[-1]
    report["latestActual"] = {
        "sessionDate":actual_payload["latestSessionDate"],
        "score":profile_score(now,selected),
        "components":{field:round(now[field+"Rank"],1) for field in FIELDS},
        "actualHistoryCount":len(points),
        "interpretation":"INDICATIVE ETF-proxy transfer; short REAL stock EOD history, no validated stock-level returns",
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices-csv",type=Path,help="Optional previously obtained historical CSV")
    parser.add_argument("--refresh-actual-only",action="store_true",help="Daily local refresh with frozen calibration; zero network")
    parser.add_argument("--actual",type=Path,default=Path("lab/data/trend-birth-market-internals.json"))
    parser.add_argument("--output",type=Path,default=Path("lab/data/trend-birth-composite-backtest.json"))
    args = parser.parse_args()
    actual = json.loads(args.actual.read_text(encoding="utf-8"))
    if (actual.get("schemaVersion") != "trend-birth-market-internals-v1"
        or not actual.get("points") or actual.get("scope") != "unified-plus-tracked-watchlist"):
        raise ValueError("Incompatible actual EOD statistics archive")
    if args.refresh_actual_only:
        result = refresh_actual(json.loads(args.output.read_text(encoding="utf-8")), actual)
    else:
        csv_text = args.prices_csv.read_text(encoding="utf-8") if args.prices_csv else urlopen(SOURCE_URL, timeout=35).read().decode("utf-8")
        result = run(csv_text,actual)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print("Composite ETF proxy:",result["oos"]["n"],"held-out samples; selected",result["calibration"]["selectedProfile"],
          "; actual EOD",result["latestActual"]["actualHistoryCount"],"; mode",
          "local-refresh" if args.refresh_actual_only else "walk-forward")


if __name__ == "__main__":
    main()
