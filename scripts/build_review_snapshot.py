#!/usr/bin/env python3
"""Build a read-only Trend Birth review snapshot from StockScout Unified public assets."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import urllib.request
from pathlib import Path
from urllib.parse import urljoin
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kell_scoring import MODEL_VERSION as KELL_SCORE_MODEL_VERSION, score_candidate

DEFAULT_BASE = "https://garrincha077.github.io/StockScout-Unified/"
MODES = ("bottom-fishing", "next", "ryan-original")
KELL_SCREEN_FIELDS = (
    "kell_52w_high",
    "kell_unusual_volume",
    "kell_rvol_3x",
    "kell_bull_snort",
    "kell_momentum_3m_50",
    "kell_doubler_ytd",
    "kell_gapper",
    "kell_strength_on_down_day",
    "kell_rs_leader",
)
KELL_SETUP_FIELDS = (
    "kell_buyable_gap_proxy",
    "kell_wedge_pop",
    "kell_ema_crossback",
    "kell_base_n_break",
    "kell_tightening",
    "kell_breakout_proximity",
)
KELL_CONTEXT_FIELDS = (
    "kell_focus",
    "kell_name_selection_ok",
    "kell_growth_context",
    "kell_rs_divergence",
    "kell_weekly_trend_ok",
    "kell_ema_readiness",
)


def _get_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "StockScout-Trend-Birth-Lab/0.2"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def _get_json(url: str):
    return json.loads(_get_bytes(url).decode("utf-8"))


def verified_mode_manifest(base_url: str, unified: dict, mode: str) -> dict:
    entry = unified["modes"][mode]
    content = _get_bytes(urljoin(base_url, "data/" + entry["manifestPath"]))
    if hashlib.sha256(content).hexdigest() != entry["manifestSha256"]:
        raise ValueError(f"{mode}: manifest hash mismatch; activation may be changing")
    manifest = json.loads(content)
    for field in ("runId", "sessionDate"):
        if manifest.get(field) != unified.get(field):
            raise ValueError(f"{mode}: {field} differs from activated Unified scan")
    if manifest.get("status") != "healthy":
        raise ValueError(f"{mode}: unhealthy manifest")
    return manifest


def _number(row: dict, *names: str) -> float | None:
    for name in names:
        value = row.get(name)
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return number
    return None


def _ticker(row: dict) -> str:
    return str(row.get("ticker") or row.get("symbol") or "").strip().upper()


def relative_volume(row: dict) -> float | None:
    values = [
        _number(row, "currentThrustRelVolume", "current_thrust_rel_volume"),
        _number(row, "rwbThrustRelVolume", "rwb_thrust_rel_volume"),
        _number(row, "rvolToday", "rvol_today", "relativeVolume", "relative_volume"),
        _number(row, "weeklyBreakoutRvol", "weekly_breakout_rvol"),
    ]
    finite = [value for value in values if value is not None]
    return max(finite) if finite else None


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def kell_signals(row: dict, min_rvol: float = 3.0) -> list[str]:
    """Mirror the public Unified Oliver Kell saved screens plus a liquid daily RVOL event."""
    signals: list[str] = []
    rs = _number(row, "rs_rating", "rsRating") or 0.0
    primary = str(row.get("primary_setup") or row.get("primarySetup") or "")
    ema_phase = str(row.get("ema_stack_phase") or row.get("emaStackPhase") or "")
    long_base_phase = str(row.get("long_base_phase") or row.get("longBasePhase") or "")
    rwb_phase = str(row.get("rwb_squeeze_phase") or row.get("rwbSqueezePhase") or "")
    distance_high = _number(row, "distance_to_52w_high_pct", "distanceTo52wHighPct")
    weekly_rvol = _number(row, "weekly_breakout_rvol", "weeklyBreakoutRvol") or 0.0
    daily_rvol = _number(row, "rvol_today", "rvolToday") or 0.0
    adv50 = _number(row, "avg_dollar_volume_50d", "avgDollarVolume50d") or 0.0
    price = _number(row, "price", "close") or 0.0
    ret_1d = _number(row, "ret_1d_pct", "ret1dPct") or 0.0
    ret_6m = _number(row, "ret_6m_pct", "ret6mPct") or 0.0

    if rs >= 85 and (
        primary == "ema_cross"
        or ema_phase in {"early_ignition", "stack_thrust", "follow_through"}
        or long_base_phase == "launching"
        or rwb_phase in {"thrusting", "confirmed"}
    ):
        signals.append("Reclaim / Launch")

    if (
        rs >= 85
        and distance_high is not None
        and distance_high >= -5
        and _truthy(row.get("rs_line_at_52w_high") or row.get("rsLineAt52wHigh"))
    ):
        signals.append("52W Highs")

    if rs >= 80 and (
        weekly_rvol >= 2
        or _truthy(row.get("daily_rvol_headsup") or row.get("dailyRvolHeadsup"))
        or _truthy(row.get("pocket_pivot") or row.get("pocketPivot"))
    ):
        signals.append("Bull Snort")

    if ret_6m >= 100 and rs >= 90:
        signals.append("Doublers")

    # User-requested daily power-move overlay. Liquidity and price sanity prevent
    # extreme RVOL prints in tiny/illiquid names from dominating the daily board.
    if daily_rvol >= min_rvol and adv50 >= 20_000_000 and price >= 5 and ret_1d > 0:
        signals.append(f"Daily {min_rvol:g}x RVOL")

    return signals


def _kell_rank(row: dict, signals: list[str]) -> tuple[int, float, float, float]:
    """Rank only qualifying daily power moves; saved-screen confluence breaks ties."""
    daily_rvol = _number(row, "rvol_today", "rvolToday") or 0.0
    rs = _number(row, "rs_rating", "rsRating") or 0.0
    dollar_volume = _number(row, "avg_dollar_volume_50d", "avgDollarVolume50d") or 0.0
    return len(signals), daily_rvol, rs, dollar_volume


def kell_gap_metrics(row: dict) -> dict:
    """Derive Kell's canonical gap screen from latest enriched EOD row."""
    price = _number(row, "price", "close")
    open_price = _number(row, "open")
    ret_1d = _number(row, "ret_1d_pct", "ret1dPct")
    avg_volume_20d = _number(row, "avg_volume_20d", "avgVolume20d")
    if price is None or open_price is None or ret_1d is None or ret_1d <= -99.0:
        return {"gapPct": None, "prevClose": None, "gapHeldPct": None, "avgVolume20d": avg_volume_20d}
    prev_close = price / (1.0 + ret_1d / 100.0)
    if prev_close <= 0:
        return {"gapPct": None, "prevClose": None, "gapHeldPct": None, "avgVolume20d": avg_volume_20d}
    gap_pct = (open_price / prev_close - 1.0) * 100.0
    gap_size = open_price - prev_close
    gap_held = ((price - prev_close) / gap_size * 100.0) if gap_size > 0 else None
    return {
        "gapPct": gap_pct,
        "prevClose": prev_close,
        "gapHeldPct": gap_held,
        "avgVolume20d": avg_volume_20d,
        "open": open_price,
    }


def is_kell_gap_up(row: dict, min_gap_pct: float = 3.0) -> bool:
    """Oliver Kell Gappers screen: price > $20, Avg Vol 20d > 500k, gap > 3%."""
    metrics = kell_gap_metrics(row)
    price = _number(row, "price", "close") or 0.0
    avg_volume_20d = metrics.get("avgVolume20d") or 0.0
    gap_pct = metrics.get("gapPct")
    return bool(price > 20.0 and avg_volume_20d > 500_000 and gap_pct is not None and gap_pct > min_gap_pct)


def kell_gap_from_bars(rows: list) -> dict:
    bars = _normalized_bars(rows)
    if len(bars) < 21:
        return {"gapPct": None, "prevClose": None, "gapHeldPct": None, "avgVolume20d": None}
    last = bars[-1]
    prev = bars[-2]
    prev_close = prev["close"]
    if prev_close <= 0:
        return {"gapPct": None, "prevClose": None, "gapHeldPct": None, "avgVolume20d": None}
    gap_pct = (last["open"] / prev_close - 1.0) * 100.0
    avg_volume_20d = sum(bar["volume"] for bar in bars[-20:]) / 20.0
    gap_size = last["open"] - prev_close
    gap_held = ((last["close"] - prev_close) / gap_size * 100.0) if gap_size > 0 else None
    return {
        "gapPct": gap_pct,
        "prevClose": prev_close,
        "gapHeldPct": gap_held,
        "avgVolume20d": avg_volume_20d,
        "open": last["open"],
        "close": last["close"],
    }


def is_kell_gap_from_bars(rows: list, min_gap_pct: float = 3.0) -> bool:
    metrics = kell_gap_from_bars(rows)
    price = metrics.get("close") or 0.0
    avg_volume_20d = metrics.get("avgVolume20d") or 0.0
    gap_pct = metrics.get("gapPct")
    return bool(price > 20.0 and avg_volume_20d > 500_000 and gap_pct is not None and gap_pct > min_gap_pct)


def _kell_gap_probe_rank(row: dict) -> tuple[float, float, float]:
    """Cheap public-summary prefilter before exact OHLCV gap verification."""
    ret_1d = _number(row, "ret_1d_pct", "ret1dPct") or -999.0
    rvol = _number(row, "rvol_today", "rvolToday") or 0.0
    rs = _number(row, "rs_rating", "rsRating") or 0.0
    return ret_1d, rvol, rs


def is_kell_gap_probe(row: dict) -> bool:
    price = _number(row, "price", "close") or 0.0
    adv50 = _number(row, "avg_dollar_volume_50d", "avgDollarVolume50d") or 0.0
    ret_1d = _number(row, "ret_1d_pct", "ret1dPct")
    est_avg_volume_50d = adv50 / price if price > 0 else 0.0
    return bool(price > 20.0 and est_avg_volume_50d > 300_000 and ret_1d is not None and ret_1d > -1.0)


def _kell_gap_rank(row: dict) -> tuple[float, float, float, float]:
    metrics = kell_gap_metrics(row)
    gap_pct = float(metrics.get("gapPct") or 0.0)
    gap_held = float(metrics.get("gapHeldPct") or 0.0)
    rvol = _number(row, "rvol_today", "rvolToday") or 0.0
    rs = _number(row, "rs_rating", "rsRating") or 0.0
    return gap_held, rvol, gap_pct, rs


def _bottom_priority(row: dict) -> tuple[float, float, float]:
    score = max(
        value or 0.0
        for value in (
            _number(row, "focusScore", "focus_score"),
            _number(row, "emaStackLaunchScore", "ema_stack_launch_score"),
            _number(row, "rwbSqueezeScore", "rwb_squeeze_score"),
            _number(row, "longBaseScore", "long_base_score"),
            _number(row, "accumulationScore", "accumulation_score"),
            _number(row, "crashBaseScore", "crash_base_score"),
            _number(row, "score"),
        )
    )
    rs = _number(row, "rsRating", "rs_rating") or 0.0
    rvol = relative_volume(row) or 0.0
    return score, rs, rvol


def select_mode_rows(mode: str, rows: list[dict], limit: int = 25) -> list[dict]:
    clean = [row for row in rows if _ticker(row)]
    if mode == "ryan-original":
        signals = [row for row in clean if row.get("originalRunBuySignal") is True]
        clean = signals or clean[:20]
        return clean[:limit]
    if mode == "bottom-fishing":
        return sorted(clean, key=_bottom_priority, reverse=True)[:limit]
    return clean[:limit]


def _asset_json(mode_root: str, manifest: dict, name: str):
    asset = (manifest.get("assets") or {}).get(name)
    if not isinstance(asset, dict) or not asset.get("path"):
        return None
    content = _get_bytes(urljoin(mode_root, str(asset["path"])))
    if not asset.get("sha256") or hashlib.sha256(content).hexdigest() != asset["sha256"]:
        raise ValueError(f"{name}: asset hash mismatch")
    return json.loads(content)


def _rows_for_mode(mode_root: str, mode: str, manifest: dict, core: dict) -> list[dict]:
    core_rows = [row for row in core.get("universe") or [] if isinstance(row, dict)]
    if mode != "bottom-fishing":
        return core_rows
    richer = _asset_json(mode_root, manifest, "bottomScreener") or {}
    screen_rows = [row for row in richer.get("rows") or [] if isinstance(row, dict)]
    if not screen_rows:
        return core_rows
    by_ticker = {_ticker(row): row for row in screen_rows if _ticker(row)}
    merged = []
    for row in core_rows:
        ticker = _ticker(row)
        merged.append({**row, **by_ticker.get(ticker, {})})
    known = {_ticker(row) for row in merged}
    merged.extend(row for row in screen_rows if _ticker(row) not in known)
    return merged


def _chart_rows(payload, ticker: str):
    candidate = None
    if isinstance(payload, dict):
        candidate = payload.get(ticker)
        if candidate is None and isinstance(payload.get("byTicker"), dict):
            candidate = payload["byTicker"].get(ticker)
        if candidate is None and isinstance(payload.get("candidates"), dict):
            candidate = payload["candidates"].get(ticker)
    if isinstance(candidate, list):
        return candidate
    if isinstance(candidate, dict):
        for key in ("daily", "rows"):
            if isinstance(candidate.get(key), list):
                return candidate[key]
    return []


def load_charts(mode_root: str, manifest: dict, core: dict, tickers: set[str]) -> dict[str, list]:
    """Load either Bottom's gzip chart-manifest contract or Next/Ryan legacy chart directories."""
    asset = (manifest.get("assets") or {}).get("charts")
    if not isinstance(asset, dict) or not asset.get("path") or not tickers:
        return {}
    asset_path = str(asset["path"])
    out: dict[str, list] = {}

    # Bottom Fishing publishes a chart manifest which points to gzip shards.
    if asset_path.endswith(".json"):
        try:
            chart_manifest = _get_json(urljoin(mode_root, asset_path))
        except Exception:
            return {}
        storage = str(chart_manifest.get("storageBaseUrl") or "").rstrip("/") + "/shards/"
        by_ticker = chart_manifest.get("shardsByTicker") or {}
        needed: dict[str, list[str]] = {}
        for ticker in tickers:
            shard = by_ticker.get(ticker)
            if shard:
                needed.setdefault(str(shard), []).append(ticker)
        for shard, shard_tickers in needed.items():
            filename = shard if shard.endswith(".json.gz") else f"{shard}.json.gz"
            try:
                payload = json.loads(gzip.decompress(_get_bytes(urljoin(storage, filename))).decode("utf-8"))
            except Exception:
                continue
            for ticker in shard_tickers:
                rows = _chart_rows(payload, ticker)
                if rows:
                    out[ticker] = rows[-1265:]
        return out

    # Next and Ryan publish immutable JSON chart shards inside the active run.
    by_ticker = core.get("chartShards") or {}
    needed: dict[str, list[str]] = {}
    for ticker in tickers:
        shard = by_ticker.get(ticker)
        if shard:
            needed.setdefault(str(shard), []).append(ticker)
    for shard, shard_tickers in needed.items():
        shard_path = f"{asset_path.rstrip('/')}/{shard}"
        try:
            payload = _get_json(urljoin(mode_root, shard_path))
        except Exception:
            continue
        for ticker in shard_tickers:
            rows = _chart_rows(payload, ticker)
            if rows:
                out[ticker] = rows[-1265:]
    return out


def _embedded_spy_benchmark(charts: dict[str, list]) -> list[dict]:
    """Reconstruct point-in-time SPY history from Unified's RS=stock/SPY*100 field.

    Next/Ryan public chart rows already embed daily relative strength against SPY.
    Recovering the benchmark this way keeps Kell relative-strength tests aligned to
    the exact Unified session without adding SPY to the candidate universe.
    """
    for rows in charts.values():
        if not isinstance(rows, list) or len(rows) < 2:
            continue
        derived = []
        for row in rows[-260:]:
            try:
                if isinstance(row, list) and len(row) >= 7:
                    stamp, close, rs = row[0], float(row[4]), float(row[6])
                elif isinstance(row, dict):
                    stamp = row.get("time") or row.get("date") or ""
                    close = float(row.get("close"))
                    rs = float(row.get("rs") or row.get("relativeStrength") or row.get("relative_strength"))
                else:
                    continue
                if not math.isfinite(close) or not math.isfinite(rs) or close <= 0 or rs <= 0:
                    continue
                spy_close = close * 100.0 / rs
                derived.append({
                    "time": str(stamp),
                    "open": spy_close,
                    "high": spy_close,
                    "low": spy_close,
                    "close": spy_close,
                    "volume": 0.0,
                })
            except (TypeError, ValueError):
                continue
        if len(derived) >= 2:
            return derived
    return []


def _normalized_bars(rows: list) -> list[dict]:
    bars: list[dict] = []
    for row in rows or []:
        if isinstance(row, list) and len(row) >= 6:
            source = {"time": row[0], "open": row[1], "high": row[2], "low": row[3], "close": row[4], "volume": row[5]}
        elif isinstance(row, dict):
            source = row
        else:
            continue
        try:
            bar = {
                "time": str(source.get("time") or source.get("date") or ""),
                "open": float(source["open"]),
                "high": float(source["high"]),
                "low": float(source["low"]),
                "close": float(source["close"]),
                "volume": float(source.get("volume") or 0.0),
            }
        except (KeyError, TypeError, ValueError):
            continue
        if all(math.isfinite(bar[key]) for key in ("open", "high", "low", "close", "volume")):
            bars.append(bar)
    return bars


def _date_from_stamp(value):
    """Return a UTC date for ISO strings or Unix seconds/milliseconds."""
    import datetime as _dt
    text = str(value or "").strip()
    if not text:
        return None
    try:
        numeric = float(text)
        if math.isfinite(numeric) and numeric > 0:
            seconds = numeric / 1000.0 if numeric >= 1e12 else numeric
            return _dt.datetime.fromtimestamp(seconds, tz=_dt.timezone.utc).date()
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    try:
        return _dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _weekly_bars(rows: list, max_weeks: int = 260) -> list[list]:
    """Aggregate daily OHLCV into weekly candles for the long-horizon chart."""
    import datetime as _dt
    bars = _normalized_bars(rows)
    weeks: list[dict] = []
    for bar in bars:
        date = _date_from_stamp(bar["time"])
        if date is None:
            continue
        monday = date - _dt.timedelta(days=date.weekday())
        key = monday.isoformat()
        if not weeks or weeks[-1]["key"] != key:
            weeks.append({
                "key": key,
                "time": date.isoformat(),
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar["volume"],
            })
        else:
            current = weeks[-1]
            current["time"] = date.isoformat()
            current["high"] = max(current["high"], bar["high"])
            current["low"] = min(current["low"], bar["low"])
            current["close"] = bar["close"]
            current["volume"] += bar["volume"]
    if max_weeks > 0:
        weeks = weeks[-max_weeks:]
    return [
        [week["time"], week["open"], week["high"], week["low"], week["close"], week["volume"]]
        for week in weeks
    ]


def _rsi14(closes: list[float]) -> float | None:
    period = 14
    if len(closes) < period + 1:
        return None
    gains = []
    losses = []
    for index in range(1, period + 1):
        change = closes[index] - closes[index - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for index in range(period + 1, len(closes)):
        change = closes[index] - closes[index - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _ema(values: list[float], window: int) -> list[float | None]:
    if not values:
        return []
    alpha = 2.0 / (window + 1.0)
    current = values[0]
    out: list[float | None] = []
    for index, value in enumerate(values):
        current = value if index == 0 else value * alpha + current * (1.0 - alpha)
        out.append(current if index + 1 >= window else None)
    return out


def _pivot_structure(bars: list[dict], side: int = 2) -> dict:
    if len(bars) < side * 2 + 3:
        return {"higherHigh": None, "higherLow": None, "swingState": "insufficient"}
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    for index in range(side, len(bars) - side):
        high = bars[index]["high"]
        low = bars[index]["low"]
        if all(high > bars[j]["high"] for j in range(index - side, index + side + 1) if j != index):
            highs.append((index, high))
        if all(low < bars[j]["low"] for j in range(index - side, index + side + 1) if j != index):
            lows.append((index, low))
    higher_high = len(highs) >= 2 and highs[-1][1] > highs[-2][1]
    higher_low = len(lows) >= 2 and lows[-1][1] > lows[-2][1]
    if higher_high and higher_low:
        swing = "HH+HL"
    elif higher_high:
        swing = "HH / no HL"
    elif higher_low:
        swing = "HL / no HH"
    else:
        swing = "no HH/HL"
    return {
        "higherHigh": higher_high if len(highs) >= 2 else None,
        "higherLow": higher_low if len(lows) >= 2 else None,
        "swingState": swing,
        "lastSwingHigh": highs[-1][1] if highs else None,
        "lastSwingLow": lows[-1][1] if lows else None,
    }


def _sma(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    total = 0.0
    for index, value in enumerate(values):
        total += value
        if index >= window:
            total -= values[index - window]
        out.append(total / window if index + 1 >= window else None)
    return out


def _weekly_closes(bars: list[dict]) -> list[float]:
    return [float(row[4]) for row in _weekly_bars(bars, max_weeks=0)]


def _slope_state(series: list[float | None], lookback: int) -> str | None:
    values = [value for value in series if value is not None]
    if len(values) <= lookback or values[-lookback - 1] == 0:
        return None
    change = values[-1] / values[-lookback - 1] - 1.0
    if change > 0.002:
        return "upward"
    if change < -0.002:
        return "downward"
    return "flat"


def _chart_metrics(rows: list) -> dict:
    bars = _normalized_bars(rows)
    if not bars:
        return {}
    closes = [bar["close"] for bar in bars]
    volumes = [bar["volume"] for bar in bars]
    rvol = None
    if len(volumes) >= 21:
        baseline = sum(volumes[-21:-1]) / 20.0
        if baseline > 0:
            rvol = volumes[-1] / baseline
    weekly = _weekly_closes(bars)
    ema10 = _ema(closes, 10)
    ema20 = _ema(closes, 20)
    last_ema10 = next((value for value in reversed(ema10) if value is not None), None)
    last_ema20 = next((value for value in reversed(ema20) if value is not None), None)
    ema_gap = None
    if last_ema10 is not None and last_ema20 not in (None, 0):
        ema_gap = (last_ema10 / last_ema20 - 1.0) * 100.0

    def range_pct(window: int) -> float | None:
        sample = bars[-window:]
        if len(sample) < window:
            return None
        low = min(bar["low"] for bar in sample)
        high = max(bar["high"] for bar in sample)
        return (high / low - 1.0) * 100.0 if low > 0 else None

    range20 = range_pct(20)
    range40 = range_pct(40)
    base_like = (
        range20 is not None and range40 is not None
        and range20 <= 18.0 and range40 <= 30.0
    )
    last = bars[-1]
    close_location = (
        (last["close"] - last["low"]) / (last["high"] - last["low"])
        if last["high"] > last["low"] else 0.5
    )
    swing = _pivot_structure(bars)
    return {
        "price": closes[-1],
        "rvol": rvol,
        "rsi14": _rsi14(closes),
        "ema10": last_ema10,
        "ema20": last_ema20,
        "emaGapPct": ema_gap,
        "slope50": _slope_state(_sma(closes, 50), 20),
        "slope30w": _slope_state(_sma(weekly, 30), 8),
        "range20Pct": range20,
        "range40Pct": range40,
        "baseLike": base_like,
        "closeLocationPct": close_location * 100.0,
        **swing,
    }


def _summary(row: dict, chart_rows: list | None = None) -> dict:
    chart = _chart_metrics(chart_rows or [])
    metrics = {
        "price": _number(row, "price", "close") or chart.get("price"),
        "score": _number(row, "score", "focusScore", "focus_score", "opportunityScore", "originalBuyScore"),
        "rs": _number(row, "rsRating", "rs_rating", "rs"),
        "rvol": relative_volume(row) or chart.get("rvol"),
        "rsi14": _number(row, "rsi14", "rsi_14", "dailyRsi14") or chart.get("rsi14"),
        "slope50": row.get("sma50SlopeState") or row.get("launch50dSlopeState") or row.get("launch_50d_slope_state") or chart.get("slope50"),
        "slope30w": row.get("launch30wSlopeState") or row.get("launch_30w_slope_state") or chart.get("slope30w"),
        "setup": row.get("primarySetup") or row.get("primary_setup") or row.get("setup") or row.get("stageName"),
        "actionability": row.get("actionability") or row.get("tradeStatus") or row.get("trade_status"),
    }
    for name in (
        "ema10", "ema20", "emaGapPct", "range20Pct", "range40Pct", "baseLike",
        "closeLocationPct", "higherHigh", "higherLow", "swingState",
        "lastSwingHigh", "lastSwingLow",
    ):
        metrics[name] = chart.get(name)
    return metrics


def build_snapshot(base_url: str, analysis: dict | None, kell_min_rvol: float, kell_limit: int, kell_gap_limit: int = 5) -> dict:
    base_url = base_url.rstrip("/") + "/"
    unified = _get_json(urljoin(base_url, "data/manifest.json"))
    if unified.get("status") != "healthy":
        raise ValueError("Unified scan is not healthy")
    session_date = str(unified.get("sessionDate") or "")
    run_id = str(unified.get("runId") or "")
    merged: dict[str, dict] = {}
    mode_payloads: dict[str, tuple[str, dict, dict]] = {}
    kell_pool: dict[str, tuple[list[str], dict]] = {}
    kell_gap_probe_pool: dict[str, dict] = {}
    unified_kell_pool: dict[str, dict] = {}
    mode_universe_counts: dict[str, int] = {}

    for mode in MODES:
        mode_root = urljoin(base_url, f"data/modes/{mode}/")
        manifest = verified_mode_manifest(base_url, unified, mode)
        core = _asset_json(mode_root, manifest, "core") or {}
        full_rows = _rows_for_mode(mode_root, mode, manifest, core)
        mode_payloads[mode] = (mode_root, manifest, core)
        mode_universe_counts[mode] = len(full_rows)

        # Full Unified candidate union for Kell screens. In Unified's published
        # contract, core.universe is the mode candidate set (counts.universe ==
        # counts.candidates), so this is not a new market-wide universe.
        for row in full_rows:
            ticker = _ticker(row)
            if not ticker:
                continue
            pool_item = unified_kell_pool.setdefault(
                ticker,
                {"ticker": ticker, "unifiedSources": [], "chartModes": [], "raw": {}},
            )
            if mode not in pool_item["unifiedSources"]:
                pool_item["unifiedSources"].append(mode)
            if mode not in pool_item["chartModes"]:
                pool_item["chartModes"].append(mode)
            if mode == "next":
                pool_item["raw"] = {**pool_item["raw"], **row}
            elif mode == "bottom-fishing":
                pool_item["raw"] = {**row, **pool_item["raw"]}
            else:
                pool_item["raw"] = {**row, **pool_item["raw"]}

        # The Bottom public screener carries the full transparent evidence fields
        # used by Unified's existing Kell saved screens. Scan that broad pool once.
        if mode == "bottom-fishing":
            for row in full_rows:
                ticker = _ticker(row)
                signals = kell_signals(row, kell_min_rvol)
                daily_power = any(label.startswith("Daily ") and label.endswith("x RVOL") for label in signals)
                # Kell Daily Leaders is intentionally strict: do not back-fill the board
                # with ordinary saved-screen names when fewer than N true 3x+ RVOL moves exist.
                if ticker and daily_power:
                    previous = kell_pool.get(ticker)
                    if previous is None or _kell_rank(row, signals) > _kell_rank(previous[1], previous[0]):
                        kell_pool[ticker] = (signals, row)
                if ticker and is_kell_gap_probe(row):
                    previous_gap = kell_gap_probe_pool.get(ticker)
                    if previous_gap is None or _kell_gap_probe_rank(row) > _kell_gap_probe_rank(previous_gap):
                        kell_gap_probe_pool[ticker] = row

        rows = select_mode_rows(mode, full_rows)
        for rank, row in enumerate(rows, 1):
            ticker = _ticker(row)
            item = merged.setdefault(
                ticker,
                {"ticker": ticker, "sources": [], "sourceRanks": {}, "chartModes": [], "raw": {}},
            )
            if mode not in item["sources"]:
                item["sources"].append(mode)
            if mode not in item["chartModes"]:
                item["chartModes"].append(mode)
            item["sourceRanks"][mode] = rank
            item["raw"] = {**item["raw"], **row}

    # Keep all strict 3x+ RVOL names temporarily so chart-derived quality can be
    # evaluated before the final "best of day" Kell board is cut to kell_limit.
    kell_sorted = sorted(
        kell_pool.items(),
        key=lambda pair: _kell_rank(pair[1][1], pair[1][0]),
        reverse=True,
    )
    for rank, (ticker, (signals, row)) in enumerate(kell_sorted, 1):
        item = merged.setdefault(
            ticker,
            {"ticker": ticker, "sources": [], "sourceRanks": {}, "chartModes": [], "raw": {}},
        )
        if "kell-daily" not in item["sources"]:
            item["sources"].append("kell-daily")
        if "bottom-fishing" not in item["chartModes"]:
            item["chartModes"].append("bottom-fishing")
        item["sourceRanks"]["kell-daily"] = rank
        item["raw"] = {**item["raw"], **row}
        item["kell"] = {
            "rank": rank,
            "signals": signals,
            "rvolToday": _number(row, "rvol_today", "rvolToday"),
            "avgDollarVolume50d": _number(row, "avg_dollar_volume_50d", "avgDollarVolume50d"),
            "rsRating": _number(row, "rs_rating", "rsRating"),
        }

    # Cheap prefilter from the full public Bottom pool, followed by exact
    # OHLCV gap verification after chart loading. Probe names are hidden unless
    # they pass Kell's canonical gap screen.
    gap_probe = sorted(
        kell_gap_probe_pool.items(),
        key=lambda pair: _kell_gap_probe_rank(pair[1]),
        reverse=True,
    )[:max(kell_gap_limit * 12, 60)]
    gap_probe_tickers = {ticker for ticker, _ in gap_probe}
    for ticker, row in gap_probe:
        item = merged.setdefault(
            ticker,
            {"ticker": ticker, "sources": [], "sourceRanks": {}, "chartModes": [], "raw": {}},
        )
        if "bottom-fishing" not in item["chartModes"]:
            item["chartModes"].append("bottom-fishing")
        item["raw"] = {**item["raw"], **row}

    pending = set(merged)
    charts: dict[str, list] = {}
    for mode in MODES:
        mode_root, manifest, core = mode_payloads[mode]
        mode_tickers = {ticker for ticker in pending if mode in merged[ticker]["chartModes"]}
        loaded = load_charts(mode_root, manifest, core, mode_tickers)
        charts.update(loaded)
        pending -= set(loaded)

    # Ryan and Next intentionally share adjusted OHLCV. If one mode did not carry
    # a shard for a selected name, try Next's chart map before declaring it absent.
    if pending and "next" in mode_payloads:
        mode_root, manifest, core = mode_payloads["next"]
        adjusted_pending = {
            ticker for ticker in pending
            if any(mode in merged[ticker]["chartModes"] for mode in ("next", "ryan-original"))
        }
        loaded = load_charts(mode_root, manifest, core, adjusted_pending)
        charts.update(loaded)
        pending -= set(loaded)

    # Unified Next/Ryan chart rows carry RS = stock / SPY * 100 as a seventh
    # field. Reconstruct the session SPY return from that embedded reference so
    # Strength on Down Day works across the entire candidate union without any
    # new market-wide or Yahoo/MCP scan.
    benchmark_rows: list = _embedded_spy_benchmark(charts)
    benchmark_method = "embedded-SPY-relative-strength" if benchmark_rows else "unavailable"

    # Score the complete Unified candidate union. Build this chart map from
    # scratch in explicit Next -> Ryan -> Bottom priority. Do not seed it from
    # the ordinary Review Grid chart cache: that cache is loaded Bottom-first
    # and would make Kell scores depend on whether a ticker happened to be on
    # the smaller review board.
    kell_unified_charts: dict[str, list] = {}
    kell_pending = set(unified_kell_pool)
    for mode in ("next", "ryan-original", "bottom-fishing"):
        if not kell_pending:
            break
        mode_root, manifest, core = mode_payloads[mode]
        mode_tickers = {
            ticker for ticker in kell_pending
            if mode in unified_kell_pool[ticker]["chartModes"]
        }
        if not mode_tickers:
            continue
        loaded = load_charts(mode_root, manifest, core, mode_tickers)
        kell_unified_charts.update(loaded)
        kell_pending -= set(loaded)

    def kell_chart_quality(item: dict) -> bool:
        metrics = _summary(item.get("raw") or {}, charts.get(item["ticker"], []))
        slope50 = metrics.get("slope50")
        slope30w = metrics.get("slope30w")
        close_location = metrics.get("closeLocationPct")
        ema_gap = metrics.get("emaGapPct")
        rsi = metrics.get("rsi14")
        return (
            slope50 == "upward"
            and slope30w in {"upward", "flat"}
            and close_location is not None and close_location >= 55.0
            and ema_gap is not None and abs(ema_gap) <= 10.0
            and (rsi is None or rsi <= 85.0)
        )

    qualified_kell = [
        item for item in merged.values()
        if "kell-daily" in item["sources"] and kell_chart_quality(item)
    ]
    qualified_kell.sort(
        key=lambda item: (
            len((item.get("kell") or {}).get("signals") or []),
            float((item.get("kell") or {}).get("rvolToday") or 0.0),
            float((item.get("kell") or {}).get("rsRating") or 0.0),
        ),
        reverse=True,
    )
    selected_kell = {item["ticker"] for item in qualified_kell[:kell_limit]}
    kell_rank_map = {
        item["ticker"]: rank for rank, item in enumerate(qualified_kell[:kell_limit], 1)
    }
    for ticker in list(merged):
        item = merged[ticker]
        if "kell-daily" not in item["sources"]:
            continue
        if ticker in selected_kell:
            item["sourceRanks"]["kell-daily"] = kell_rank_map[ticker]
            item["kell"]["rank"] = kell_rank_map[ticker]
            continue
        item["sources"] = [source for source in item["sources"] if source != "kell-daily"]
        item["sourceRanks"].pop("kell-daily", None)
        item.pop("kell", None)
        if not item["sources"] and ticker not in gap_probe_tickers:
            merged.pop(ticker)

    exact_gap_items = []
    for ticker in gap_probe_tickers:
        rows = charts.get(ticker, [])
        if not is_kell_gap_from_bars(rows):
            continue
        item = merged[ticker]
        gap = kell_gap_from_bars(rows)
        if "kell-gap" not in item["sources"]:
            item["sources"].append("kell-gap")
        item["kellGap"] = {
            "rank": None,
            "gapPct": gap.get("gapPct"),
            "gapHeldPct": gap.get("gapHeldPct"),
            "open": gap.get("open"),
            "prevClose": gap.get("prevClose"),
            "avgVolume20d": gap.get("avgVolume20d"),
            "rvolToday": _number(item.get("raw") or {}, "rvol_today", "rvolToday"),
            "rsRating": _number(item.get("raw") or {}, "rs_rating", "rsRating"),
        }
        exact_gap_items.append(item)

    def gap_quality_rank(item: dict):
        metrics = _summary(item.get("raw") or {}, charts.get(item["ticker"], []))
        gap = item.get("kellGap") or {}
        slope50 = 1 if metrics.get("slope50") == "upward" else 0
        slope30 = 1 if metrics.get("slope30w") in {"upward", "flat"} else 0
        close_location = float(metrics.get("closeLocationPct") or 0.0)
        held = float(gap.get("gapHeldPct") or 0.0)
        rvol = float(gap.get("rvolToday") or 0.0)
        gap_pct = float(gap.get("gapPct") or 0.0)
        return slope50 + slope30, min(held, 200.0), close_location, rvol, gap_pct

    exact_gap_items.sort(key=gap_quality_rank, reverse=True)
    selected_gap = {item["ticker"] for item in exact_gap_items[:kell_gap_limit]}
    gap_rank_map = {item["ticker"]: rank for rank, item in enumerate(exact_gap_items[:kell_gap_limit], 1)}
    for ticker in list(merged):
        item = merged[ticker]
        if ticker in selected_gap:
            if "kell-gap" not in item["sources"]:
                item["sources"].append("kell-gap")
            item["sourceRanks"]["kell-gap"] = gap_rank_map[ticker]
            item["kellGap"]["rank"] = gap_rank_map[ticker]
        elif "kell-gap" in item["sources"]:
            item["sources"] = [source for source in item["sources"] if source != "kell-gap"]
            item["sourceRanks"].pop("kell-gap", None)
            item.pop("kellGap", None)
        if not item["sources"]:
            merged.pop(ticker)

    analysis_by_ticker = analysis if isinstance(analysis, dict) else {}

    kell_screen_counts = {field: 0 for field in KELL_SCREEN_FIELDS}
    kell_setup_counts = {field: 0 for field in KELL_SETUP_FIELDS}
    kell_context_counts = {field: 0 for field in KELL_CONTEXT_FIELDS}
    kell_stage_counts: dict[str, int] = {}
    kell_candidates = []
    for ticker, pool_item in unified_kell_pool.items():
        rows = kell_unified_charts.get(ticker, [])
        raw = pool_item.get("raw") or {}
        scored = score_candidate(rows, benchmark_rows, raw)
        hit_screens = [field for field in KELL_SCREEN_FIELDS if scored.get(field) is True]
        hit_setups = [field for field in KELL_SETUP_FIELDS if scored.get(field) is True]
        hit_context = [field for field in KELL_CONTEXT_FIELDS if scored.get(field) is True]
        for field in hit_screens:
            kell_screen_counts[field] += 1
        for field in hit_setups:
            kell_setup_counts[field] += 1
        for field in hit_context:
            kell_context_counts[field] += 1
        if not (hit_screens or hit_setups or hit_context):
            continue
        stage = str((scored.get("kell_stage") or {}).get("primary") or scored.get("kell_cycle_stage") or "unavailable")
        kell_stage_counts[stage] = kell_stage_counts.get(stage, 0) + 1
        kell_candidates.append({
            "ticker": ticker,
            "sources": list(pool_item.get("unifiedSources") or []),
            "unifiedSources": list(pool_item.get("unifiedSources") or []),
            "metrics": _summary(raw, rows),
            "chartBars": rows[-260:],
            "weeklyChartBars": _weekly_bars(rows, 260),
            "analysis": analysis_by_ticker.get(ticker, {}),
            "kellScreens": hit_screens,
            "kellSetups": hit_setups,
            "kellContext": hit_context,
            **scored,
        })
    kell_candidates.sort(key=lambda item: (
        -float(item.get("kell_score") or 0.0),
        item["ticker"],
    ))

    candidates = []
    for ticker, item in merged.items():
        raw = item.pop("raw")
        item.pop("chartModes", None)
        rows = charts.get(ticker, [])
        item["metrics"] = _summary(raw, rows)
        item["chartBars"] = rows
        item["analysis"] = analysis_by_ticker.get(ticker, {})
        # Additive Oliver Kell overlay only. Candidate membership, source ranks,
        # and the existing default ordering are intentionally unchanged.
        item.update(score_candidate(rows, benchmark_rows, raw))
        candidates.append(item)
    candidates.sort(key=lambda item: (
        0 if str(item.get("analysis", {}).get("status") or "").upper() == "ACTION" else 1,
        min(item["sourceRanks"].values()),
        item["ticker"],
    ))

    # Avoid publishing a scan assembled across two activations.
    if _get_json(urljoin(base_url, "data/manifest.json")) != unified:
        raise ValueError("Unified activation changed during build; retry later")

    return {
        "schemaVersion": "trend-birth-review-v1",
        "source": {
            "repo": "Garrincha077/StockScout-Unified",
            "runId": run_id,
            "sessionDate": session_date,
            "readOnly": True,
            "modeUniverseCounts": mode_universe_counts,
            "modeManifests": unified["modes"],
        },
        "kell": {
            "minRelativeVolume": kell_min_rvol,
            "limit": kell_limit,
            "qualifiedCount": len(selected_kell),
            "eligiblePublicPool": len(kell_pool),
            "method": "Strict liquid positive-day 3x+ RVOL leaders, ranked with Unified Kell saved-screen confluence",
        },
        "kellGap": {
            "minGapPct": 3.0,
            "minPrice": 20.0,
            "minAvgVolume20d": 500000,
            "limit": kell_gap_limit,
            "qualifiedCount": len(selected_gap),
            "eligiblePublicPool": len(exact_gap_items),
            "probeCount": len(gap_probe_tickers),
            "method": "Full public pool -> liquid positive-close probe -> exact chart verification of Kell Gappers -> quality-ranked daily best",
        },
        "kellScoring": {
            "modelVersion": KELL_SCORE_MODEL_VERSION,
            "scope": "all-unified-candidates",
            "candidateGenerationChanged": False,
            "benchmark": benchmark_method,
            "unifiedCandidateCount": len(unified_kell_pool),
            "chartCoverageCount": len(kell_unified_charts),
            "matchedCandidateCount": len(kell_candidates),
            "screenCounts": kell_screen_counts,
            "setupCounts": kell_setup_counts,
            "contextCounts": kell_context_counts,
            "stageCounts": kell_stage_counts,
            "method": "Kell v5 overlay over the deduplicated Unified candidate union. Discovery screens remain separate from stage/setup; ranking uses Quality + Readiness + Context with evidence coverage, structural-risk proxy and late-cycle stage caps. No new market-wide universe.",
        },
        "kellCandidateCount": len(kell_candidates),
        "kellCandidates": kell_candidates,
        "candidateCount": len(candidates),
        "chartCount": sum(bool(item["chartBars"]) for item in candidates),
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--analysis")
    parser.add_argument("--output", default="lab/data/latest.json")
    parser.add_argument("--kell-min-rvol", type=float, default=3.0)
    parser.add_argument("--kell-limit", type=int, default=5)
    parser.add_argument("--kell-gap-limit", type=int, default=5)
    args = parser.parse_args()
    analysis = {}
    if args.analysis and Path(args.analysis).exists():
        analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))
    snapshot = build_snapshot(args.base_url, analysis, args.kell_min_rvol, args.kell_limit, args.kell_gap_limit)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({
        "status": "ok",
        "candidates": snapshot["candidateCount"],
        "charts": snapshot["chartCount"],
        "sessionDate": snapshot["source"]["sessionDate"],
        "kellEligible": snapshot["kell"]["eligiblePublicPool"],
        "kellUnifiedCandidates": snapshot["kellScoring"]["unifiedCandidateCount"],
        "kellMatchedCandidates": snapshot["kellScoring"]["matchedCandidateCount"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
