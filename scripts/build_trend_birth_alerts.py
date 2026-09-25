#!/usr/bin/env python3
"""Build a no-send Telegram-ready Trend Birth alert payload.

Trend Birth stays credential-free.  This script only compares today's compact
dataset with the latest prior archived dataset and writes grouped text that an
external/Unified sender can deliver later.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_DASHBOARD = "https://stockscout-trend-birth-review-lab.vercel.app/"


def _stage(item: dict) -> int:
    try:
        return int((item.get("trendBirth") or {}).get("stage") or 0)
    except (TypeError, ValueError):
        return 0


def _candidate_map(data: dict) -> dict[str, dict]:
    # Keep Telegram sparse: normal names still require the quality-screened
    # Kell set, while persistent tracked names are always eligible for Trend
    # Birth stage-change alerts even if today's Unified screener missed them.
    quality_rows = data.get("kellCandidates") or data.get("unifiedCandidateIndex") or []
    selected = {
        str(item.get("ticker") or "").upper(): item
        for item in quality_rows
        if isinstance(item, dict) and item.get("ticker")
    }
    for item in data.get("trendBirthCandidateIndex") or []:
        if not isinstance(item, dict) or not item.get("ticker") or not item.get("trackedWatchlist"):
            continue
        selected[str(item["ticker"]).upper()] = item
    return selected


def _rank(item: dict) -> tuple:
    return (
        _stage(item),
        float(item.get("kell_score") or 0.0),
        float(item.get("kell_readiness_score") or 0.0),
        float(item.get("kell_quality_score") or 0.0),
        str(item.get("ticker") or ""),
    )


def _checks(item: dict) -> list[str]:
    checks = (item.get("trendBirth") or {}).get("checks") or {}
    labels = (
        ("sma50Rising", "SMA50 rising"),
        ("sma30wRising", "SMA30W rising"),
        ("structureValid", "Structure valid"),
        ("notExtended", "Not extended"),
        ("recentPullbackCompression", "Pullback + EMA compression"),
        ("ema10Rising", "EMA10 rising"),
        ("ema20NonFalling", "EMA20 non-falling"),
        ("ema10AboveEma20", "EMA10 > EMA20"),
        ("closeAboveShortEmas", "Close > EMA10 & EMA20"),
        ("bullishReexpansion", "Bullish EMA re-expansion"),
    )
    return [f"{'✅' if checks.get(key) else '❌'} {label}" for key, label in labels]


def _latest_prior(history_dir: Path, session_date: str) -> tuple[Path | None, dict | None]:
    candidates = sorted(
        (path for path in history_dir.glob("*.json") if path.stem < session_date),
        key=lambda path: path.stem,
        reverse=True,
    )
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        return path, data
    return None, None


def _dashboard_url(base: str, publication: dict) -> str:
    base = base.rstrip("/") + "/"
    snapshot = str(publication.get("snapshotId") or "").strip()
    return f"{base}?snapshot={snapshot}" if snapshot else base


def build_alerts(
    current: dict,
    previous: dict | None,
    dashboard_url: str,
    max_ready: int = 5,
) -> dict:
    current_map = _candidate_map(current)
    previous_map = _candidate_map(previous or {})
    prior_has_radar = any("trendBirth" in item for item in previous_map.values())

    ready: list[dict] = []
    triggers: list[dict] = []
    invalidated: list[dict] = []

    if prior_has_radar:
        for ticker, item in current_map.items():
            now = _stage(item)
            before = _stage(previous_map.get(ticker, {}))
            if now == 4 and before < 4:
                triggers.append(item)
            elif now == 3 and before < 3:
                ready.append(item)
            elif now == 0 and before >= 3:
                invalidated.append({**item, "_previousStage": before})

    ready.sort(key=_rank, reverse=True)
    triggers.sort(key=_rank, reverse=True)
    invalidated.sort(key=lambda item: (int(item.get("_previousStage") or 0), _rank(item)), reverse=True)

    messages: list[dict] = []
    if ready:
        shown = ready[:max_ready]
        lines = [
            "🟠 KELL TREND BIRTH — 3/4 READY",
            f"{len(ready)} new candidate{'s' if len(ready) != 1 else ''}",
            "",
        ]
        for item in shown:
            lines.append(f"{item['ticker']} — 3/4")
            missing = (item.get("trendBirth") or {}).get("missingFor4") or []
            if missing:
                lines.append("❌ Still needed: " + "; ".join(missing))
            lines.append("")
        extra = len(ready) - len(shown)
        if extra:
            lines.append(f"+{extra} additional candidates — View dashboard: {dashboard_url}")
        else:
            lines.append(f"View dashboard: {dashboard_url}")
        messages.append({"kind": "ready", "text": "\n".join(lines).strip()})

    for item in triggers:
        lines = [
            "🚀 KELL TREND BIRTH — 4/4 TRIGGER",
            f"{item['ticker']} — 4/4",
            *_checks(item),
            "",
            f"View dashboard: {dashboard_url}",
        ]
        messages.append({"kind": "trigger", "ticker": item["ticker"], "text": "\n".join(lines)})

    if invalidated:
        shown = invalidated[:max_ready]
        lines = [
            "⚪ KELL TREND BIRTH — INVALIDATED",
            f"{len(invalidated)} former READY/TRIGGER candidate{'s' if len(invalidated) != 1 else ''}",
            "",
        ]
        lines.extend(
            f"{item['ticker']} — {int(item.get('_previousStage') or 0)}/4 → 0/4"
            for item in shown
        )
        extra = len(invalidated) - len(shown)
        lines.append("")
        if extra:
            lines.append(f"+{extra} additional candidates — View dashboard: {dashboard_url}")
        else:
            lines.append(f"View dashboard: {dashboard_url}")
        messages.append({"kind": "invalidated", "text": "\n".join(lines)})

    return {
        "schemaVersion": "trend-birth-alerts-v1",
        "sessionDate": (current.get("source") or {}).get("sessionDate"),
        "baselineOnly": not prior_has_radar,
        "readyCount": len(ready),
        "triggerCount": len(triggers),
        "invalidatedCount": len(invalidated),
        "dashboardUrl": dashboard_url,
        "messages": messages,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", required=True)
    parser.add_argument("--history-dir", required=True)
    parser.add_argument("--publication", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD)
    parser.add_argument("--max-ready", type=int, default=5)
    args = parser.parse_args()

    current = json.loads(Path(args.current).read_text(encoding="utf-8"))
    publication = json.loads(Path(args.publication).read_text(encoding="utf-8"))
    session_date = str((current.get("source") or {}).get("sessionDate") or "")
    prior_path, previous = _latest_prior(Path(args.history_dir), session_date)
    payload = build_alerts(
        current,
        previous,
        _dashboard_url(args.dashboard_url, publication),
        max_ready=max(1, args.max_ready),
    )
    payload["previousSessionDate"] = (
        (previous.get("source") or {}).get("sessionDate") if previous else None
    )
    payload["previousPath"] = str(prior_path) if prior_path else None

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "ok",
        "baselineOnly": payload["baselineOnly"],
        "ready": payload["readyCount"],
        "triggers": payload["triggerCount"],
        "invalidated": payload["invalidatedCount"],
        "messages": len(payload["messages"]),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
