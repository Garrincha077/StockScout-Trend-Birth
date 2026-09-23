#!/usr/bin/env python3
"""Point-in-time validation/audit for the Kell overlay on existing StockScout candidates.

This validator is intentionally separate from scoring. It does not discover symbols, does
not change candidate membership, and does not create a second ranking model. It checks:

1. SCREEN contract consistency against already-published metrics.
2. STAGE/event consistency.
3. SETUP quality with stricter book-grounded evidence checks, reported as strong,
   borderline, or contradiction.

Borderline setup evidence is diagnostic only. CI fails only on hard contract/event
contradictions so calibration can improve without silently changing the live universe.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "kell-signal-validation-v1"
CORE_SETUP_FIELDS = (
    "kell_buyable_gap_proxy",
    "kell_wedge_pop",
    "kell_ema_crossback",
    "kell_base_n_break",
)
SCREEN_FIELDS = (
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
    for i, value in enumerate(values):
        current = value if i == 0 else value * alpha + current * (1.0 - alpha)
        out.append(current if i + 1 >= window else None)
    return out


def _range_pct(sample: list[dict[str, Any]]) -> float | None:
    if not sample:
        return None
    low = min(float(row["low"]) for row in sample)
    high = max(float(row["high"]) for row in sample)
    return (high / low - 1.0) * 100.0 if low > 0 else None


def _truth(item: dict, field: str) -> bool | None:
    value = item.get(field)
    return value if isinstance(value, bool) else None


def _metric(item: dict, name: str) -> float | None:
    metrics = item.get("kell_metrics") or {}
    try:
        value = float(metrics.get(name))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _expected_screen_contract(item: dict) -> dict[str, bool | None]:
    bars = _bars(item.get("chartBars") or [])
    close = float(bars[-1]["close"]) if bars else None
    avg_volume20 = _metric(item, "avg_volume20")
    rvol = _metric(item, "rvol20")
    ret1 = _metric(item, "ret_1d_pct")
    ret3 = _metric(item, "ret_3m_pct")
    ytd = _metric(item, "ret_ytd_pct")
    gap = _metric(item, "gap_pct")
    beta = _metric(item, "beta")
    rs_rank = _metric(item, "rs_rank")
    metrics = item.get("kell_metrics") or {}
    new_high = metrics.get("new_52w_high")
    if not isinstance(new_high, bool):
        new_high = None

    liquid = (
        close is not None and avg_volume20 is not None
        and close > 20.0 and avg_volume20 > 500_000.0
    )

    def known(value: float | None, result: bool) -> bool | None:
        return result if value is not None else None

    return {
        "kell_unusual_volume": known(rvol, bool(rvol is not None and rvol >= 2.0)),
        "kell_rvol_3x": known(rvol, bool(rvol is not None and rvol >= 3.0)),
        "kell_bull_snort": (
            None if rvol is None or ret1 is None or close is None or avg_volume20 is None
            else bool(liquid and rvol >= 2.0 and ret1 > 0.0)
        ),
        "kell_momentum_3m_50": known(ret3, bool(ret3 is not None and ret3 >= 50.0)),
        "kell_doubler_ytd": (
            None if ytd is None or close is None or avg_volume20 is None
            else bool(liquid and ytd > 100.0)
        ),
        "kell_gapper": (
            None if gap is None or close is None or avg_volume20 is None
            else bool(liquid and gap > 3.0)
        ),
        "kell_strength_on_down_day": (
            None if beta is None or ret1 is None or close is None or avg_volume20 is None
            else bool(liquid and beta > 1.0 and ret1 > 0.0)
        ),
        "kell_rs_leader": known(rs_rank, bool(rs_rank is not None and rs_rank >= 90.0)),
        "kell_52w_high": (
            None if new_high is None or beta is None or close is None or avg_volume20 is None
            else bool(liquid and new_high and beta > 1.0)
        ),
    }


def _audit_wedge_pop(item: dict, bars: list[dict[str, Any]]) -> tuple[str, list[str]]:
    if len(bars) < 30:
        return "contradiction", ["insufficient_history"]
    closes = [float(row["close"]) for row in bars]
    e10 = _ema(closes, 10)
    e20 = _ema(closes, 20)
    if None in (e10[-1], e20[-1], e10[-2], e20[-2]):
        return "contradiction", ["ema_unavailable"]

    upper = max(float(e10[-1]), float(e20[-1]))
    prior_upper = max(float(e10[-2]), float(e20[-2]))
    crossed = closes[-1] > upper and closes[-2] <= prior_upper
    ema_gap = abs(float(e10[-1]) / float(e20[-1]) - 1.0) * 100.0
    pretrend = (closes[-2] / closes[-11] - 1.0) * 100.0 if closes[-11] > 0 else None
    row = bars[-1]
    span = float(row["high"]) - float(row["low"])
    close_location = (
        (float(row["close"]) - float(row["low"])) / span * 100.0 if span > 0 else 50.0
    )

    reasons: list[str] = []
    if not crossed:
        reasons.append("not_current_10_20_ema_recapture")
    if ema_gap > 1.5:
        reasons.append("ema_cluster_not_tight")
    if pretrend is not None and pretrend > 3.0:
        reasons.append("pre_pop_price_not_working_lower_or_sideways")
    if close_location < 55.0:
        reasons.append("weak_pop_close_location")

    if not crossed or ema_gap > 2.0:
        return "contradiction", reasons
    if reasons:
        return "borderline", reasons
    return "strong", []


def _audit_ema_crossback(item: dict, bars: list[dict[str, Any]]) -> tuple[str, list[str]]:
    if len(bars) < 30:
        return "contradiction", ["insufficient_history"]
    closes = [float(row["close"]) for row in bars]
    e10 = _ema(closes, 10)
    e20 = _ema(closes, 20)
    if e10[-1] is None or e20[-1] is None:
        return "contradiction", ["ema_unavailable"]

    lower = min(float(e10[-1]), float(e20[-1]))
    upper = max(float(e10[-1]), float(e20[-1]))
    midpoint = (lower + upper) / 2.0
    low = float(bars[-1]["low"])
    close = closes[-1]
    pop_age = _metric(item, "recent_wedge_pop_sessions_ago")
    if pop_age is None:
        raw_age = (item.get("kell_metrics") or {}).get("recent_wedge_pop_sessions_ago")
        try:
            pop_age = float(raw_age)
        except (TypeError, ValueError):
            pop_age = None

    penetration_pct = (low / lower - 1.0) * 100.0 if lower > 0 else -999.0
    touches = low <= upper * 1.01
    holds = close >= lower * 0.995
    reasons: list[str] = []
    if pop_age is None or pop_age > 15:
        reasons.append("no_recent_wedge_pop")
    if not touches:
        reasons.append("did_not_retest_ema_cluster")
    if not holds:
        reasons.append("failed_to_hold_ema_cluster")
    if penetration_pct < -2.0:
        reasons.append("deep_ema_undercut")
    if close < midpoint * 0.995:
        reasons.append("weak_crossback_close")

    if (pop_age is None or pop_age > 15) or not touches or not holds:
        return "contradiction", reasons
    if reasons:
        return "borderline", reasons
    return "strong", []


def _audit_base_n_break(item: dict, bars: list[dict[str, Any]]) -> tuple[str, list[str]]:
    if len(bars) < 31:
        return "contradiction", ["insufficient_history"]
    closes = [float(row["close"]) for row in bars]
    e10 = _ema(closes, 10)
    e20 = _ema(closes, 20)
    if None in (e10[-1], e20[-1], e20[-6]):
        return "contradiction", ["ema_unavailable"]

    prior10 = bars[-11:-1]
    prior20 = bars[-21:-1]
    prior10_high = max(float(row["high"]) for row in prior10)
    range10 = _range_pct(prior10)
    range20 = _range_pct(prior20)
    contraction = (
        range10 is not None and range20 is not None and range20 > 0
        and range10 <= range20 * 0.80
    )
    breakout = closes[-1] > prior10_high
    ema_structure_ok = float(e10[-1]) >= float(e20[-1]) * 0.995
    ema20_not_falling_hard = float(e20[-1]) >= float(e20[-6]) * 0.995

    reasons: list[str] = []
    if not breakout:
        reasons.append("no_current_10d_breakout")
    if not contraction:
        reasons.append("base_not_contracted")
    if not ema_structure_ok:
        reasons.append("bearish_10_20_ema_structure")
    if not ema20_not_falling_hard:
        reasons.append("20ema_still_falling")

    if not breakout or not contraction:
        return "contradiction", reasons
    if reasons:
        return "borderline", reasons
    return "strong", []


def _audit_buyable_gap(item: dict, bars: list[dict[str, Any]]) -> tuple[str, list[str]]:
    if len(bars) < 22:
        return "contradiction", ["insufficient_history"]
    prev_close = float(bars[-2]["close"])
    row = bars[-1]
    gap = (float(row["open"]) / prev_close - 1.0) * 100.0 if prev_close > 0 else None
    prior20_high = max(float(x["high"]) for x in bars[-21:-1])
    rvol = _metric(item, "rvol20")
    unfilled = float(row["low"]) > prev_close
    breakout = float(row["open"]) > prior20_high
    span = float(row["high"]) - float(row["low"])
    close_location = (
        (float(row["close"]) - float(row["low"])) / span * 100.0 if span > 0 else 50.0
    )
    gap_size = float(row["open"]) - prev_close
    gap_held = (
        (float(row["close"]) - prev_close) / gap_size * 100.0
        if gap_size > 0 else None
    )

    reasons: list[str] = []
    if gap is None or gap <= 3.0:
        reasons.append("gap_not_above_3pct")
    if not unfilled:
        reasons.append("gap_filled")
    if not breakout:
        reasons.append("open_not_above_prior20d_high")
    if rvol is None or rvol < 1.5:
        reasons.append("rvol_below_1_5x")
    if gap_held is not None and gap_held < 50.0:
        reasons.append("weak_gap_hold")
    if close_location < 50.0:
        reasons.append("weak_gap_close")

    hard = (
        gap is None or gap <= 3.0 or not unfilled or not breakout
        or rvol is None or rvol < 1.5
    )
    if hard:
        return "contradiction", reasons
    if reasons:
        return "borderline", reasons
    return "strong", []


SETUP_AUDITORS = {
    "kell_buyable_gap_proxy": _audit_buyable_gap,
    "kell_wedge_pop": _audit_wedge_pop,
    "kell_ema_crossback": _audit_ema_crossback,
    "kell_base_n_break": _audit_base_n_break,
}

STAGE_EVENT_FIELD = {
    "reversal_extension": "kell_reversal_extension",
    "wedge_pop": "kell_wedge_pop",
    "ema_crossback": "kell_ema_crossback",
    "base_n_break": "kell_base_n_break",
    "exhaustion_extension": "kell_exhaustion_extension",
    "wedge_drop": "kell_wedge_drop",
}


def validate_snapshot(snapshot: dict, sample_limit: int = 15) -> dict:
    candidates = list(snapshot.get("kellCandidates") or snapshot.get("candidates") or [])
    source = snapshot.get("source") or {}
    scoring = snapshot.get("kellScoring") or {}

    screen_stats = {
        field: {"checked": 0, "matched": 0, "mismatched": 0}
        for field in SCREEN_FIELDS
    }
    screen_examples: list[dict] = []
    stage_mismatches: list[dict] = []
    setup_stats = {
        field: {"total": 0, "strong": 0, "borderline": 0, "contradiction": 0}
        for field in CORE_SETUP_FIELDS
    }
    setup_examples: dict[str, list[dict]] = {field: [] for field in CORE_SETUP_FIELDS}
    overlap_errors: list[dict] = []

    for item in candidates:
        ticker = str(item.get("ticker") or "")
        expected = _expected_screen_contract(item)
        for field, exp in expected.items():
            actual = _truth(item, field)
            if exp is None or actual is None:
                continue
            stat = screen_stats[field]
            stat["checked"] += 1
            if actual == exp:
                stat["matched"] += 1
            else:
                stat["mismatched"] += 1
                if len(screen_examples) < sample_limit:
                    screen_examples.append({
                        "ticker": ticker,
                        "field": field,
                        "expected": exp,
                        "actual": actual,
                    })

        stage = item.get("kell_stage") or {}
        primary = stage.get("primary") or item.get("kell_cycle_stage")
        event_field = STAGE_EVENT_FIELD.get(str(primary))
        if event_field and _truth(item, event_field) is not True:
            if len(stage_mismatches) < sample_limit:
                stage_mismatches.append({
                    "ticker": ticker,
                    "stage": primary,
                    "expectedEventField": event_field,
                    "actual": item.get(event_field),
                })

        screens = set(item.get("kellScreens") or item.get("kell_screens") or [])
        setups = set(item.get("kellSetups") or item.get("kell_setups") or [])
        context = set(item.get("kellContext") or item.get("kell_context") or [])
        if screens & setups or screens & context or setups & context:
            if len(overlap_errors) < sample_limit:
                overlap_errors.append({
                    "ticker": ticker,
                    "screenSetup": sorted(screens & setups),
                    "screenContext": sorted(screens & context),
                    "setupContext": sorted(setups & context),
                })

        bars = _bars(item.get("chartBars") or [])
        for field, auditor in SETUP_AUDITORS.items():
            if _truth(item, field) is not True:
                continue
            grade, reasons = auditor(item, bars)
            stat = setup_stats[field]
            stat["total"] += 1
            stat[grade] += 1
            if grade != "strong" and len(setup_examples[field]) < sample_limit:
                setup_examples[field].append({
                    "ticker": ticker,
                    "grade": grade,
                    "reasons": reasons,
                    "stage": primary,
                })

    screen_mismatch_count = sum(stat["mismatched"] for stat in screen_stats.values())
    setup_contradictions = sum(stat["contradiction"] for stat in setup_stats.values())
    hard_error_count = (
        screen_mismatch_count
        + len(stage_mismatches)
        + len(overlap_errors)
        + setup_contradictions
    )

    unified_count = scoring.get("unifiedCandidateCount")
    candidate_generation_changed = scoring.get("candidateGenerationChanged")
    universe_ok = (
        candidate_generation_changed is not True
        and (unified_count is None or int(unified_count) >= len(candidates))
    )
    if not universe_ok:
        hard_error_count += 1

    return {
        "schemaVersion": SCHEMA_VERSION,
        "source": {
            "runId": source.get("runId"),
            "sessionDate": source.get("sessionDate"),
        },
        "modelVersion": scoring.get("modelVersion"),
        "candidateCount": len(candidates),
        "universePreserved": universe_ok,
        "hardErrorCount": hard_error_count,
        "checks": {
            "screenContract": {
                "mismatchCount": screen_mismatch_count,
                "signals": screen_stats,
                "examples": screen_examples,
            },
            "stageEventConsistency": {
                "mismatchCount": len(stage_mismatches),
                "examples": stage_mismatches,
            },
            "layerSeparation": {
                "overlapCount": len(overlap_errors),
                "examples": overlap_errors,
            },
            "setupQuality": {
                "signals": setup_stats,
                "examples": setup_examples,
                "note": (
                    "Borderline is diagnostic, not a hard failure. Strong checks are deliberately "
                    "stricter than the production v5 detector and are intended for calibration."
                ),
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--sample-limit", type=int, default=15)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    snapshot = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = validate_snapshot(snapshot, sample_limit=max(1, args.sample_limit))

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    compact = {
        "schemaVersion": report["schemaVersion"],
        "sessionDate": report["source"]["sessionDate"],
        "candidateCount": report["candidateCount"],
        "universePreserved": report["universePreserved"],
        "hardErrorCount": report["hardErrorCount"],
        "screenMismatches": report["checks"]["screenContract"]["mismatchCount"],
        "stageMismatches": report["checks"]["stageEventConsistency"]["mismatchCount"],
        "layerOverlaps": report["checks"]["layerSeparation"]["overlapCount"],
        "setupQuality": report["checks"]["setupQuality"]["signals"],
    }
    print(json.dumps(compact, ensure_ascii=False, sort_keys=True))

    if args.strict and report["hardErrorCount"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
