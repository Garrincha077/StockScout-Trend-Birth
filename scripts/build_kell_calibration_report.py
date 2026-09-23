#!/usr/bin/env python3
"""Build a self-contained visual calibration report for Kell setup audit candidates.

The report is read-only and consumes the point-in-time Unified/Kell snapshot plus the
signal-validation JSON. It exists to make proxy calibration inspectable; it does not
change scores, setup flags, rankings, or candidate membership.
"""
from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
from typing import Any


def _bars(rows: list | None) -> list[dict[str, float | str]]:
    out: list[dict[str, float | str]] = []
    for row in rows or []:
        if isinstance(row, list) and len(row) >= 6:
            source = {
                "time": row[0], "open": row[1], "high": row[2],
                "low": row[3], "close": row[4], "volume": row[5],
            }
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
        if all(math.isfinite(float(bar[key])) for key in ("open", "high", "low", "close", "volume")):
            out.append(bar)
    return out


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


def _svg_chart(rows: list | None, width: int = 760, height: int = 240, lookback: int = 80) -> str:
    bars = _bars(rows)[-lookback:]
    if len(bars) < 3:
        return '<div class="missing">Chart history unavailable</div>'

    closes = [float(row["close"]) for row in bars]
    ema10 = _ema(closes, 10)
    ema20 = _ema(closes, 20)
    lows = [float(row["low"]) for row in bars]
    highs = [float(row["high"]) for row in bars]
    valid_emas = [float(v) for v in ema10 + ema20 if v is not None]
    low_value = min(lows + valid_emas)
    high_value = max(highs + valid_emas)
    if high_value <= low_value:
        high_value = low_value + 1.0

    pad_x = 18.0
    pad_y = 14.0
    chart_w = width - 2 * pad_x
    chart_h = height - 2 * pad_y

    def x(index: int) -> float:
        return pad_x + chart_w * index / max(1, len(bars) - 1)

    def y(value: float) -> float:
        return pad_y + chart_h * (high_value - value) / (high_value - low_value)

    wicks = []
    for index, bar in enumerate(bars):
        wicks.append(
            f'<line class="wick" x1="{x(index):.1f}" y1="{y(float(bar["high"])):.1f}" '
            f'x2="{x(index):.1f}" y2="{y(float(bar["low"])):.1f}" />'
        )

    close_points = " ".join(f"{x(i):.1f},{y(value):.1f}" for i, value in enumerate(closes))
    ema10_points = " ".join(
        f"{x(i):.1f},{y(float(value)):.1f}" for i, value in enumerate(ema10) if value is not None
    )
    ema20_points = " ".join(
        f"{x(i):.1f},{y(float(value)):.1f}" for i, value in enumerate(ema20) if value is not None
    )
    latest = bars[-1]
    latest_x = x(len(bars) - 1)
    label = html.escape(str(latest["time"])[:10])

    return (
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Daily price with EMA10 and EMA20">'
        + "".join(wicks)
        + f'<polyline class="close-line" points="{close_points}" />'
        + f'<polyline class="ema10-line" points="{ema10_points}" />'
        + f'<polyline class="ema20-line" points="{ema20_points}" />'
        + f'<line class="latest-line" x1="{latest_x:.1f}" y1="{pad_y:.1f}" '
          f'x2="{latest_x:.1f}" y2="{height-pad_y:.1f}" />'
        + f'<text class="date-label" x="{max(4.0, latest_x-72):.1f}" y="{height-4}">{label}</text>'
        + '</svg>'
    )


def _collect_review_items(snapshot: dict, report: dict) -> list[dict]:
    candidates = list(snapshot.get("kellCandidates") or snapshot.get("candidates") or [])
    by_ticker = {str(item.get("ticker") or ""): item for item in candidates}
    setup_quality = ((report.get("checks") or {}).get("setupQuality") or {})

    reasons_by_ticker: dict[str, list[str]] = {}
    kinds_by_ticker: dict[str, set[str]] = {}

    for setup, examples in (setup_quality.get("examples") or {}).items():
        for example in examples or []:
            ticker = str(example.get("ticker") or "")
            if not ticker:
                continue
            kinds_by_ticker.setdefault(ticker, set()).add(setup)
            reasons_by_ticker.setdefault(ticker, []).extend(example.get("reasons") or [])

    soft = setup_quality.get("softQualityFlags") or {}
    for example in soft.get("examples") or []:
        ticker = str(example.get("ticker") or "")
        if not ticker:
            continue
        kinds_by_ticker.setdefault(ticker, set()).add(str(example.get("setup") or "soft_quality"))
        reasons_by_ticker.setdefault(ticker, []).extend(example.get("flags") or [])

    crossback = setup_quality.get("emaCrossbackSupport") or {}
    for row in crossback.get("largestUndercuts") or []:
        undercut = row.get("undercutAtr")
        if not isinstance(undercut, (int, float)) or undercut <= 0.5:
            continue
        ticker = str(row.get("ticker") or "")
        if not ticker:
            continue
        kinds_by_ticker.setdefault(ticker, set()).add("kell_ema_crossback")
        reasons_by_ticker.setdefault(ticker, []).append(
            f"crossback_undercut_{float(undercut):.2f}atr"
        )

    out: list[dict] = []
    for ticker in sorted(kinds_by_ticker):
        item = by_ticker.get(ticker)
        if item is None:
            continue
        out.append({
            "ticker": ticker,
            "setups": sorted(kinds_by_ticker[ticker]),
            "reasons": sorted(set(reasons_by_ticker.get(ticker) or [])),
            "candidate": item,
        })
    return out


def build_html(snapshot: dict, report: dict) -> str:
    review_items = _collect_review_items(snapshot, report)
    session = ((report.get("source") or {}).get("sessionDate")
               or (snapshot.get("source") or {}).get("sessionDate")
               or "unknown")
    setup_quality = ((report.get("checks") or {}).get("setupQuality") or {})
    signals = setup_quality.get("signals") or {}
    soft_counts = (setup_quality.get("softQualityFlags") or {}).get("counts") or {}

    summary_rows = []
    for setup, stats in sorted(signals.items()):
        summary_rows.append(
            "<tr>"
            f"<td>{html.escape(setup)}</td>"
            f"<td>{int(stats.get('total') or 0)}</td>"
            f"<td>{int(stats.get('strong') or 0)}</td>"
            f"<td>{int(stats.get('borderline') or 0)}</td>"
            f"<td>{int(stats.get('contradiction') or 0)}</td>"
            "</tr>"
        )

    soft_rows = "".join(
        f"<li><code>{html.escape(name)}</code>: {int(count)}</li>"
        for name, count in sorted(soft_counts.items())
    ) or "<li>None</li>"

    cards = []
    for row in review_items:
        item = row["candidate"]
        ticker = row["ticker"]
        stage = (item.get("kell_stage") or {}).get("primary") or item.get("kell_cycle_stage") or "n/a"
        score = item.get("kell_score")
        readiness = item.get("kell_readiness_score")
        metrics = item.get("kell_metrics") or {}
        tags = " ".join(f"<span class='tag'>{html.escape(x)}</span>" for x in row["setups"])
        reasons = " ".join(f"<span class='flag'>{html.escape(x)}</span>" for x in row["reasons"])
        cards.append(
            "<article class='card'>"
            "<div class='card-head'>"
            f"<div><h2>{html.escape(ticker)}</h2><div>{tags}</div></div>"
            f"<div class='numbers'>Focus <b>{html.escape(str(score))}</b> · "
            f"Readiness <b>{html.escape(str(readiness))}</b> · "
            f"Stage <b>{html.escape(str(stage))}</b></div>"
            "</div>"
            f"<div class='flags'>{reasons or '<span class=muted>No flags</span>'}</div>"
            f"{_svg_chart(item.get('chartBars') or [])}"
            "<div class='metrics'>"
            f"RVOL20 {html.escape(str(metrics.get('rvol20')))} · "
            f"3M {html.escape(str(metrics.get('ret_3m_pct')))}% · "
            f"RS {html.escape(str(metrics.get('rs_rank')))} · "
            f"Breakout proximity {html.escape(str(metrics.get('breakout_proximity_pct')))}%"
            "</div>"
            "</article>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kell Signal Calibration — {html.escape(str(session))}</title>
<style>
:root {{ color-scheme: light dark; font-family: Inter, system-ui, sans-serif; }}
body {{ margin: 0; padding: 24px; background: Canvas; color: CanvasText; }}
main {{ max-width: 1180px; margin: 0 auto; }}
h1 {{ margin-bottom: 4px; }}
.lead {{ opacity: .75; margin-top: 0; }}
.summary {{ display: grid; grid-template-columns: minmax(360px,1fr) minmax(280px,.7fr); gap: 18px; }}
.panel,.card {{ border: 1px solid color-mix(in srgb, CanvasText 18%, transparent); border-radius: 14px; padding: 16px; margin-bottom: 18px; }}
table {{ border-collapse: collapse; width: 100%; }}
th,td {{ text-align: left; padding: 7px 9px; border-bottom: 1px solid color-mix(in srgb, CanvasText 12%, transparent); }}
.card-head {{ display: flex; gap: 12px; align-items: flex-start; justify-content: space-between; }}
.card h2 {{ margin: 0 0 8px; }}
.numbers {{ text-align: right; font-size: .92rem; opacity: .8; }}
.tag,.flag {{ display: inline-block; border: 1px solid color-mix(in srgb, CanvasText 24%, transparent); border-radius: 999px; padding: 3px 8px; margin: 2px 4px 2px 0; font-size: .8rem; }}
.flag {{ font-family: ui-monospace, monospace; }}
.flags {{ margin: 12px 0 4px; }}
.chart {{ display: block; width: 100%; height: auto; margin-top: 8px; }}
.wick {{ stroke: currentColor; stroke-opacity: .22; stroke-width: 1; }}
.close-line,.ema10-line,.ema20-line {{ fill: none; stroke-width: 2.2; }}
.close-line {{ stroke: #2f80ed; }}
.ema10-line {{ stroke: #e67e22; }}
.ema20-line {{ stroke: #8e44ad; }}
.latest-line {{ stroke: currentColor; stroke-opacity: .16; stroke-dasharray: 4 4; }}
.date-label {{ fill: currentColor; font-size: 11px; opacity: .65; }}
.metrics {{ font-size: .86rem; opacity: .75; margin-top: 4px; }}
.muted {{ opacity: .6; }}
@media (max-width: 780px) {{ .summary {{ grid-template-columns: 1fr; }} .card-head {{ display:block; }} .numbers {{ text-align:left; margin-top:8px; }} }}
</style>
</head>
<body>
<main>
<h1>Kell Signal Calibration</h1>
<p class="lead">Point-in-time session {html.escape(str(session))}. Visual review only — no universe, score, stage, or setup mutation.</p>
<section class="summary">
<div class="panel">
<h2>Structural audit</h2>
<table><thead><tr><th>Setup</th><th>Total</th><th>Strong</th><th>Borderline</th><th>Contradiction</th></tr></thead>
<tbody>{''.join(summary_rows)}</tbody></table>
</div>
<div class="panel">
<h2>Soft quality flags</h2>
<ul>{soft_rows}</ul>
<p class="muted">Soft flags are calibration observations, not Kell rules and not setup invalidators.</p>
</div>
</section>
<p><b>Charts queued for review:</b> {len(review_items)}</p>
{''.join(cards) if cards else '<div class="panel">No calibration candidates for this session.</div>'}
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    report = json.loads(Path(args.validation).read_text(encoding="utf-8"))
    rendered = build_html(snapshot, report)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "status": "ok",
        "sessionDate": (report.get("source") or {}).get("sessionDate"),
        "reviewCandidates": len(_collect_review_items(snapshot, report)),
        "bytes": output.stat().st_size,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
