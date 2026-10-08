#!/usr/bin/env python3
"""Point-in-time replay of user-annotated 2023 Kell cycle examples.

Optional research dependency: yfinance. Historical adjusted prices may be
restated by the vendor; this is a visual calibration check, not a backtest of
historical Unified candidate membership or trading performance.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from kell_scoring import MODEL_VERSION, score_candidate  # noqa: E402


# Windows are intentionally broad: labels on the supplied charts mark a phase,
# not an exact fill price or machine-readable daily event date.
CASES = (
    ("ELF", "reversal_extension", "2023-10-30", "2023-11-03", True),
    ("NVDA", "wedge_pop", "2023-01-06", "2023-01-11", True),
    ("TOL", "wedge_pop", "2023-10-31", "2023-11-03", True),
    ("TOL", "ema_crossback", "2023-11-08", "2023-11-13", True),
    ("TOL", "exhaustion_extension", "2023-11-01", "2023-11-03", False),
    ("WING", "reversal_extension", "2023-09-05", "2023-09-07", True),
    ("WING", "wedge_pop", "2023-09-08", "2023-09-14", True),
    ("WING", "base_n_break", "2023-10-30", "2023-11-03", True),
    ("AFRM", "wedge_pop", "2023-11-01", "2023-11-03", True),
    ("AFRM", "ema_crossback", "2023-11-07", "2023-11-10", True),
    ("AFRM", "base_n_break", "2023-11-24", "2023-11-28", True),
    ("AFRM", "exhaustion_extension", "2023-11-01", "2023-11-10", False),
    ("AFRM", "exhaustion_extension", "2023-12-18", "2023-12-21", True),
    ("KBH", "wedge_drop", "2023-08-15", "2023-08-18", True),
    ("PHM", "wedge_drop", "2023-08-16", "2023-08-18", True),
)


def download_bars(ticker: str) -> list[dict]:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise SystemExit("Install yfinance for this optional research replay") from exc
    frame = yf.download(
        ticker, start="2022-01-01", end="2024-02-01",
        auto_adjust=True, progress=False, threads=False,
    )
    if frame.empty:
        raise RuntimeError(f"No historical bars for {ticker}")
    rows = []
    for day, values in frame.iterrows():
        def number(field: str) -> float:
            key = (field, ticker) if (field, ticker) in frame.columns else field
            return float(values[key])
        rows.append({
            "time": day.date().isoformat(),
            "open": number("Open"),
            "high": number("High"),
            "low": number("Low"),
            "close": number("Close"),
            "volume": number("Volume"),
        })
    return rows


def replay(bars_by_ticker: dict[str, list[dict]]) -> dict:
    stages: dict[str, dict[str, str]] = {}
    for ticker, bars in bars_by_ticker.items():
        stage_by_day = {}
        for index, bar in enumerate(bars):
            # Every decision sees only history available through that session.
            stage_by_day[bar["time"]] = score_candidate(bars[:index + 1])["kell_cycle_stage"]
        stages[ticker] = stage_by_day
    results = []
    for ticker, stage, start, end, expected in CASES:
        hits = [
            day for day, actual in stages[ticker].items()
            if start <= day <= end and actual == stage
        ]
        results.append({
            "ticker": ticker, "stage": stage, "window": [start, end],
            "expectedPresent": expected, "hitDates": hits,
            "matchesAnnotation": bool(hits) == expected,
        })
    return {
        "modelVersion": MODEL_VERSION,
        "source": "Yahoo Finance adjusted daily OHLCV via yfinance; retrieved at replay time",
        "scope": "seven user-annotated charts; selected positive and negative windows",
        "cases": results,
        "matched": sum(row["matchesAnnotation"] for row in results),
        "total": len(results),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="write a machine-readable research report")
    args = parser.parse_args()
    tickers = sorted({row[0] for row in CASES})
    report = replay({ticker: download_bars(ticker) for ticker in tickers})
    for row in report["cases"]:
        status = "PASS" if row["matchesAnnotation"] else "MISS"
        print(f"{status:4} {row['ticker']:4} {row['stage']:22} {row['window'][0]}..{row['window'][1]}  {','.join(row['hitDates']) or '-'}")
    print(f"{report['matched']}/{report['total']} windows match")
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["matched"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
