#!/usr/bin/env python3
"""Evaluate human-reviewed Kell Gold Set labels against point-in-time model outputs.

The Gold Set is deliberately separate from scoring. Labels are human review artifacts,
not detector output. This script can compare the prediction that existed when a label
was reviewed (BEFORE) with the currently archived prediction for that same session
(AFTER), without changing the Unified universe, Kell screens, stages, setups, or scores.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

GOLD_SCHEMA_VERSION = "kell-gold-set-v2"
REPORT_SCHEMA_VERSION = "kell-gold-set-eval-v2"
VALID_LABELS = {"VALID", "BORDERLINE", "FALSE_POSITIVE", "FALSE_NEGATIVE"}
VALID_LAYERS = {"screen", "stage", "setup", "context"}


def _load_json(path: Path) -> dict:
    if path.name.endswith(".json.gz.b64"):
        raw = base64.b64decode(path.read_text(encoding="utf-8"))
        return json.loads(gzip.decompress(raw).decode("utf-8"))
    return json.loads(path.read_text(encoding="utf-8"))


def validate_gold_set(gold: dict) -> list[str]:
    errors: list[str] = []
    if gold.get("schemaVersion") != GOLD_SCHEMA_VERSION:
        errors.append(f"schemaVersion must be {GOLD_SCHEMA_VERSION}")
    seen: set[tuple[str, str, str, str]] = set()
    for index, row in enumerate(gold.get("labels") or []):
        prefix = f"labels[{index}]"
        session = str(row.get("sessionDate") or "")
        ticker = str(row.get("ticker") or "")
        layer = str(row.get("layer") or "")
        signal = str(row.get("signal") or "")
        label = str(row.get("label") or "")
        if not session:
            errors.append(f"{prefix}: sessionDate missing")
        if not ticker:
            errors.append(f"{prefix}: ticker missing")
        if layer not in VALID_LAYERS:
            errors.append(f"{prefix}: invalid layer {layer!r}")
        if not signal:
            errors.append(f"{prefix}: signal missing")
        if label not in VALID_LABELS:
            errors.append(f"{prefix}: invalid label {label!r}")
        if not isinstance(row.get("predictionAtReview"), bool):
            errors.append(f"{prefix}: predictionAtReview must be boolean")
        elif label == "FALSE_POSITIVE" and row.get("predictionAtReview") is not True:
            errors.append(f"{prefix}: FALSE_POSITIVE requires predictionAtReview=true")
        elif label == "FALSE_NEGATIVE" and row.get("predictionAtReview") is not False:
            errors.append(f"{prefix}: FALSE_NEGATIVE requires predictionAtReview=false")
        elif label in {"VALID", "BORDERLINE"} and row.get("predictionAtReview") is False:
            errors.append(
                f"{prefix}: reviewed positive missed by the model must use FALSE_NEGATIVE"
            )
        reasons = row.get("reasonCodes")
        if not isinstance(reasons, list) or not all(isinstance(x, str) and x for x in reasons):
            errors.append(f"{prefix}: reasonCodes must be a non-empty string list")
        key = (session, ticker, layer, signal)
        if key in seen:
            errors.append(f"{prefix}: duplicate label key {key}")
        seen.add(key)
    return errors


def _candidates(payload: dict) -> list[dict]:
    """Return candidate mappings from compact, v1, or columnar v2 archives."""
    rows = list(payload.get("kellCandidates") or payload.get("candidates") or [])
    if not rows:
        return []
    if all(isinstance(row, dict) for row in rows):
        return rows

    columns = payload.get("columns") or []
    if columns and all(isinstance(row, list) for row in rows):
        out: list[dict] = []
        for row in rows:
            item = {
                str(columns[index]): value
                for index, value in enumerate(row)
                if index < len(columns)
            }
            out.append(item)
        return out
    return []


def _session(payload: dict) -> str:
    return str((payload.get("source") or {}).get("sessionDate") or "")


def _model_version(payload: dict) -> str | None:
    return (payload.get("kellScoring") or {}).get("modelVersion")


def _prediction(item: dict | None, layer: str, signal: str) -> tuple[bool | None, str | None]:
    if item is None:
        return False, None

    if layer == "stage":
        stage = (
            (item.get("kell_stage") or {}).get("primary")
            or item.get("kell_cycle_stage")
            or item.get("stage")
        )
        if stage is None:
            return None, "stage_not_archived"
        return str(stage) == signal, None

    keys = {
        "screen": ("kellScreens", "kell_screens", "screens"),
        "setup": ("kellSetups", "kell_setups", "setups"),
        "context": ("kellContext", "kell_context", "context"),
    }[layer]
    values = None
    for key in keys:
        if key in item:
            values = item.get(key)
            break
    if values is None:
        return None, f"{layer}_not_archived"
    return signal in set(values or []), None


def _load_session_payloads(current: dict | None, scores_dir: Path | None) -> dict[str, dict]:
    payloads: dict[str, dict] = {}
    if scores_dir and scores_dir.exists():
        paths = sorted(scores_dir.glob("*.json")) + sorted(scores_dir.glob("*.json.gz.b64"))
        for path in paths:
            try:
                payload = _load_json(path)
            except Exception:
                continue
            session = _session(payload)
            if session:
                existing = payloads.get(session)
                # Prefer richer plain JSON archives over legacy encoded copies.
                if existing is None or path.suffix == ".json":
                    payloads[session] = payload
    if current:
        session = _session(current)
        if session:
            payloads[session] = current
    return payloads


def _bucket_metrics(rows: list[dict]) -> dict:
    evaluated = [row for row in rows if row["predictionNow"] is not None]
    current_predicted = [row for row in evaluated if row["predictionNow"] is True]
    baseline_predicted = [row for row in rows if row["predictionAtReview"] is True]
    expected_positive = [
        row for row in evaluated
        if row["label"] in {"VALID", "BORDERLINE", "FALSE_NEGATIVE"}
    ]
    valid_current = [
        row for row in current_predicted
        if row["label"] in {"VALID", "FALSE_NEGATIVE"}
    ]
    accepted_current = [
        row for row in current_predicted
        if row["label"] in {"VALID", "BORDERLINE", "FALSE_NEGATIVE"}
    ]

    def pct(num: int, den: int) -> float | None:
        return round(num / den * 100.0, 1) if den else None

    weighted = (
        sum(
            1.0 if row["label"] in {"VALID", "FALSE_NEGATIVE"}
            else 0.5 if row["label"] == "BORDERLINE"
            else 0.0
            for row in current_predicted
        )
        / len(current_predicted) * 100.0
        if current_predicted else None
    )
    return {
        "reviewed": len(rows),
        "evaluated": len(evaluated),
        "unavailable": len(rows) - len(evaluated),
        "labels": dict(Counter(row["label"] for row in rows)),
        "baselinePredicted": len(baseline_predicted),
        "currentPredicted": len(current_predicted),
        "lostFromBaseline": sum(
            row["predictionAtReview"] is True and row["predictionNow"] is False
            for row in evaluated
        ),
        "addedFromBaseline": sum(
            row["predictionAtReview"] is False and row["predictionNow"] is True
            for row in evaluated
        ),
        "acceptedPrecisionPct": pct(len(accepted_current), len(current_predicted)),
        "strictValidPrecisionPct": pct(len(valid_current), len(current_predicted)),
        "positiveRecallPct": pct(
            sum(row["predictionNow"] is True for row in expected_positive),
            len(expected_positive),
        ),
        "weightedQualityPct": round(weighted, 1) if weighted is not None else None,
        "observedFalsePositives": sum(
            row["label"] == "FALSE_POSITIVE" for row in rows
        ),
        "observedFalseNegatives": sum(
            row["label"] == "FALSE_NEGATIVE" for row in rows
        ),
        "fixedFalsePositives": sum(
            row["label"] == "FALSE_POSITIVE"
            and row["predictionAtReview"] is True
            and row["predictionNow"] is False
            for row in evaluated
        ),
        "unresolvedFalsePositives": sum(
            row["label"] == "FALSE_POSITIVE" and row["predictionNow"] is True
            for row in evaluated
        ),
        "fixedFalseNegatives": sum(
            row["label"] == "FALSE_NEGATIVE" and row["predictionNow"] is True
            for row in evaluated
        ),
        "unresolvedFalseNegatives": sum(
            row["label"] == "FALSE_NEGATIVE" and row["predictionNow"] is False
            for row in evaluated
        ),
        "hardRegressions": sum(
            row["label"] == "VALID"
            and row["predictionAtReview"] is True
            and row["predictionNow"] is False
            for row in evaluated
        ),
    }


def evaluate_gold_set(gold: dict, current: dict | None = None, scores_dir: Path | None = None) -> dict:
    errors = validate_gold_set(gold)
    payloads = _load_session_payloads(current, scores_dir)
    indexes = {
        session: {str(item.get("ticker") or ""): item for item in _candidates(payload)}
        for session, payload in payloads.items()
    }

    rows: list[dict] = []
    for label in gold.get("labels") or []:
        session = str(label["sessionDate"])
        ticker = str(label["ticker"])
        payload = payloads.get(session)
        item = indexes.get(session, {}).get(ticker) if payload else None
        if payload is None:
            prediction = None
            unavailable_reason = "session_snapshot_unavailable"
            model_version = None
        else:
            prediction, unavailable_reason = _prediction(
                item, str(label["layer"]), str(label["signal"])
            )
            model_version = _model_version(payload)

        baseline = bool(label["predictionAtReview"])
        if prediction is None:
            change = "unavailable"
        elif label["label"] == "FALSE_POSITIVE":
            change = "unresolved_false_positive" if prediction else "fixed_false_positive"
        elif label["label"] == "FALSE_NEGATIVE":
            change = "fixed_false_negative" if prediction else "unresolved_false_negative"
        elif baseline == prediction:
            change = "unchanged"
        elif baseline and not prediction:
            if label["label"] == "VALID":
                change = "regression_valid_lost"
            else:
                change = "borderline_removed"
        else:
            change = "recovered_positive"

        rows.append({
            "sessionDate": session,
            "ticker": ticker,
            "layer": label["layer"],
            "signal": label["signal"],
            "label": label["label"],
            "reasonCodes": list(label.get("reasonCodes") or []),
            "predictionAtReview": baseline,
            "predictionNow": prediction,
            "change": change,
            "unavailableReason": unavailable_reason,
            "modelVersionAtReview": label.get("modelVersionAtReview"),
            "modelVersionNow": model_version,
            "notes": label.get("notes"),
        })

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[f'{row["layer"]}:{row["signal"]}'].append(row)

    buckets = {
        key: _bucket_metrics(bucket_rows)
        for key, bucket_rows in sorted(grouped.items())
    }
    summary = _bucket_metrics(rows)
    fp_reasons = Counter(
        reason
        for row in rows
        if row["label"] == "FALSE_POSITIVE" and row["predictionNow"] is True
        for reason in row["reasonCodes"]
    )
    summary["topFalsePositiveReasons"] = [
        {"reason": reason, "count": count}
        for reason, count in fp_reasons.most_common(10)
    ]
    summary["availableSessionCount"] = len(payloads)
    summary["labeledSessionCount"] = len({row["sessionDate"] for row in rows})
    summary["sessionsWithFalsePositives"] = len({
        row["sessionDate"] for row in rows if row["label"] == "FALSE_POSITIVE"
    })
    summary["sessionsWithFalseNegatives"] = len({
        row["sessionDate"] for row in rows if row["label"] == "FALSE_NEGATIVE"
    })

    session_groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        session_groups[row["sessionDate"]].append(row)
    sessions = {
        session: _bucket_metrics(session_rows)
        for session, session_rows in sorted(session_groups.items())
    }

    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "goldSetSchemaVersion": gold.get("schemaVersion"),
        "validationErrors": errors,
        "summary": summary,
        "buckets": buckets,
        "sessions": sessions,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold-set", required=True)
    parser.add_argument("--current")
    parser.add_argument("--scores-dir")
    parser.add_argument("--output")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    gold = _load_json(Path(args.gold_set))
    current = _load_json(Path(args.current)) if args.current else None
    scores_dir = Path(args.scores_dir) if args.scores_dir else None
    report = evaluate_gold_set(gold, current=current, scores_dir=scores_dir)

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    print(json.dumps({
        "status": "ok" if not report["validationErrors"] else "invalid",
        "reviewed": report["summary"]["reviewed"],
        "evaluated": report["summary"]["evaluated"],
        "unavailable": report["summary"]["unavailable"],
        "lostFromBaseline": report["summary"]["lostFromBaseline"],
        "addedFromBaseline": report["summary"]["addedFromBaseline"],
        "hardRegressions": report["summary"]["hardRegressions"],
        "observedFalsePositives": report["summary"]["observedFalsePositives"],
        "observedFalseNegatives": report["summary"]["observedFalseNegatives"],
        "unresolvedFalsePositives": report["summary"]["unresolvedFalsePositives"],
        "unresolvedFalseNegatives": report["summary"]["unresolvedFalseNegatives"],
        "acceptedPrecisionPct": report["summary"]["acceptedPrecisionPct"],
        "weightedQualityPct": report["summary"]["weightedQualityPct"],
    }, sort_keys=True))

    if args.strict and (
        report["validationErrors"] or report["summary"]["hardRegressions"] > 0
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
