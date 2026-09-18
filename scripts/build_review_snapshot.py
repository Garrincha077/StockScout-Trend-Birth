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
    request = urllib.request.Request(url, headers={"User-Agent": "StockScout-Trend-Birth-Lab/0.1"})
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


def _rows_for_mode(mode_root: str, mode: str, manifest: dict) -> list[dict]:
    core = _asset_json(mode_root, manifest, "core") or {}
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


def load_charts(mode_root: str, manifest: dict, tickers: set[str]) -> dict[str, list]:
    asset = (manifest.get("assets") or {}).get("charts")
    if not isinstance(asset, dict) or not asset.get("path"):
        return {}
    try:
        chart_manifest = _get_json(urljoin(mode_root, str(asset["path"])))
    except Exception:
        return {}
    storage = str(chart_manifest.get("storageBaseUrl") or "").rstrip("/") + "/shards/"
    by_ticker = chart_manifest.get("shardsByTicker") or {}
    needed: dict[str, list[str]] = {}
    for ticker in tickers:
        shard = by_ticker.get(ticker)
        if shard:
            needed.setdefault(str(shard), []).append(ticker)
    out: dict[str, list] = {}
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


def _summary(row: dict) -> dict:
    return {
        "price": _number(row, "price", "close"),
        "score": _number(row, "score", "focusScore", "focus_score", "opportunityScore", "originalBuyScore"),
        "rs": _number(row, "rsRating", "rs_rating", "rs"),
        "rvol": relative_volume(row),
        "rsi14": _number(row, "rsi14", "rsi_14", "dailyRsi14"),
        "slope50": row.get("sma50SlopeState") or row.get("launch50dSlopeState") or row.get("launch_50d_slope_state"),
        "slope30w": row.get("launch30wSlopeState") or row.get("launch_30w_slope_state"),
        "setup": row.get("primarySetup") or row.get("primary_setup") or row.get("setup") or row.get("stageName"),
        "actionability": row.get("actionability") or row.get("tradeStatus") or row.get("trade_status"),
    }


def build_snapshot(base_url: str, analysis: dict | None, kell_min_rvol: float, kell_limit: int) -> dict:
    base_url = base_url.rstrip("/") + "/"
    unified = _get_json(urljoin(base_url, "data/manifest.json"))
    session_date = str(unified.get("sessionDate") or "")
    run_id = str(unified.get("runId") or "")
    merged: dict[str, dict] = {}
    mode_manifests: dict[str, tuple[str, dict]] = {}

    for mode in MODES:
        mode_root = urljoin(base_url, f"data/modes/{mode}/")
        manifest = _get_json(urljoin(mode_root, "manifest.json"))
        mode_manifests[mode] = (mode_root, manifest)
        rows = select_mode_rows(mode, _rows_for_mode(mode_root, mode, manifest))
        for rank, row in enumerate(rows, 1):
            ticker = _ticker(row)
            item = merged.setdefault(ticker, {"ticker": ticker, "sources": [], "sourceRanks": {}, "raw": {}})
            if mode not in item["sources"]:
                item["sources"].append(mode)
            item["sourceRanks"][mode] = rank
            item["raw"] = {**item["raw"], **row}

    kell_pool = []
    for ticker, item in merged.items():
        rv = relative_volume(item["raw"])
        if rv is not None and rv >= kell_min_rvol:
            kell_pool.append((rv, ticker))
    for rank, (rv, ticker) in enumerate(sorted(kell_pool, reverse=True)[:kell_limit], 1):
        item = merged[ticker]
        if "kell-3x-rvol" not in item["sources"]:
            item["sources"].append("kell-3x-rvol")
        item["sourceRanks"]["kell-3x-rvol"] = rank
        item["kell"] = {"rvol": rv, "rule": f"RVOL >= {kell_min_rvol:.1f}x", "rank": rank}

    pending = set(merged)
    charts: dict[str, list] = {}
    for mode in MODES:
        mode_root, manifest = mode_manifests[mode]
        mode_tickers = {ticker for ticker in pending if mode in merged[ticker]["sources"]}
        loaded = load_charts(mode_root, manifest, mode_tickers)
        charts.update(loaded)
        pending -= set(loaded)

    analysis_by_ticker = analysis if isinstance(analysis, dict) else {}
    candidates = []
    for ticker, item in merged.items():
        raw = item.pop("raw")
        item["metrics"] = _summary(raw)
        item["chartBars"] = charts.get(ticker, [])
        item["analysis"] = analysis_by_ticker.get(ticker, {})
        candidates.append(item)
    candidates.sort(key=lambda item: (
        0 if item.get("analysis", {}).get("status") == "ACTION" else 1,
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
        },
        "kell": {"minRelativeVolume": kell_min_rvol, "limit": kell_limit},
        "candidateCount": len(candidates),
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
        "sessionDate": snapshot["source"]["sessionDate"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
