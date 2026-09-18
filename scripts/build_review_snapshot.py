#!/usr/bin/env python3
"""Build a read-only Trend Birth review snapshot from StockScout Unified public assets."""
from __future__ import annotations

import argparse
import gzip
import json
import math
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

DEFAULT_BASE = "https://garrincha077.github.io/StockScout-Unified/"
MODES = ("bottom-fishing", "next", "ryan-original")


def _get_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "StockScout-Trend-Birth-Lab/0.2"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def _get_json(url: str):
    return json.loads(_get_bytes(url).decode("utf-8"))


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
    return _get_json(urljoin(mode_root, str(asset["path"])))


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
    weeks: list[tuple[str, float]] = []
    for bar in bars:
        stamp = str(bar["time"])[:10]
        try:
            year, month, day = (int(part) for part in stamp.split("-"))
            import datetime as _dt
            date = _dt.date(year, month, day)
        except Exception:
            continue
        monday = (date - _dt.timedelta(days=date.weekday())).isoformat()
        if weeks and weeks[-1][0] == monday:
            weeks[-1] = (monday, bar["close"])
        else:
            weeks.append((monday, bar["close"]))
    return [close for _, close in weeks]


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
    return {
        "price": closes[-1],
        "rvol": rvol,
        "rsi14": _rsi14(closes),
        "slope50": _slope_state(_sma(closes, 50), 20),
        "slope30w": _slope_state(_sma(weekly, 30), 8),
    }


def _summary(row: dict, chart_rows: list | None = None) -> dict:
    chart = _chart_metrics(chart_rows or [])
    return {
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


def build_snapshot(base_url: str, analysis: dict | None, kell_min_rvol: float, kell_limit: int) -> dict:
    base_url = base_url.rstrip("/") + "/"
    unified = _get_json(urljoin(base_url, "data/manifest.json"))
    session_date = str(unified.get("sessionDate") or "")
    run_id = str(unified.get("runId") or "")
    merged: dict[str, dict] = {}
    mode_payloads: dict[str, tuple[str, dict, dict]] = {}
    kell_raw: dict[str, tuple[float, str, dict]] = {}
    mode_universe_counts: dict[str, int] = {}

    for mode in MODES:
        mode_root = urljoin(base_url, f"data/modes/{mode}/")
        manifest = _get_json(urljoin(mode_root, "manifest.json"))
        core = _asset_json(mode_root, manifest, "core") or {}
        full_rows = _rows_for_mode(mode_root, mode, manifest, core)
        mode_payloads[mode] = (mode_root, manifest, core)
        mode_universe_counts[mode] = len(full_rows)

        # Kell overlay scans the full public mode pool, not only the 25 names already
        # selected for the daily review. It remains a transparent RVOL hypothesis.
        for row in full_rows:
            ticker = _ticker(row)
            rv = relative_volume(row)
            if ticker and rv is not None and rv >= kell_min_rvol:
                previous = kell_raw.get(ticker)
                if previous is None or rv > previous[0]:
                    kell_raw[ticker] = (rv, mode, row)

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

    for rank, (ticker, (rv, origin_mode, row)) in enumerate(
        sorted(kell_raw.items(), key=lambda pair: pair[1][0], reverse=True)[:kell_limit],
        1,
    ):
        item = merged.setdefault(
            ticker,
            {"ticker": ticker, "sources": [], "sourceRanks": {}, "chartModes": [], "raw": {}},
        )
        if "kell-3x-rvol" not in item["sources"]:
            item["sources"].append("kell-3x-rvol")
        if origin_mode not in item["chartModes"]:
            item["chartModes"].append(origin_mode)
        item["sourceRanks"]["kell-3x-rvol"] = rank
        item["raw"] = {**item["raw"], **row}
        item["kell"] = {
            "rvol": rv,
            "rule": f"RVOL >= {kell_min_rvol:.1f}x",
            "rank": rank,
            "originMode": origin_mode,
        }

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

    analysis_by_ticker = analysis if isinstance(analysis, dict) else {}
    candidates = []
    for ticker, item in merged.items():
        raw = item.pop("raw")
        item.pop("chartModes", None)
        rows = charts.get(ticker, [])
        item["metrics"] = _summary(raw, rows)
        item["chartBars"] = rows
        item["analysis"] = analysis_by_ticker.get(ticker, {})
        candidates.append(item)
    candidates.sort(key=lambda item: (
        0 if str(item.get("analysis", {}).get("status") or "").upper() == "ACTION" else 1,
        min(item["sourceRanks"].values()),
        item["ticker"],
    ))

    return {
        "schemaVersion": "trend-birth-review-v1",
        "source": {
            "repo": "Garrincha077/StockScout-Unified",
            "runId": run_id,
            "sessionDate": session_date,
            "readOnly": True,
            "modeUniverseCounts": mode_universe_counts,
        },
        "kell": {
            "minRelativeVolume": kell_min_rvol,
            "limit": kell_limit,
            "eligiblePublicPool": len(kell_raw),
            "method": "strongest published scalar RVOL evidence across full public mode pools",
        },
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
    args = parser.parse_args()
    analysis = {}
    if args.analysis and Path(args.analysis).exists():
        analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))
    snapshot = build_snapshot(args.base_url, analysis, args.kell_min_rvol, args.kell_limit)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({
        "status": "ok",
        "candidates": snapshot["candidateCount"],
        "charts": snapshot["chartCount"],
        "sessionDate": snapshot["source"]["sessionDate"],
        "kellEligible": snapshot["kell"]["eligiblePublicPool"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
