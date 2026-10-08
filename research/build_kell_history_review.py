#!/usr/bin/env python3
"""Build a small, point-in-time visual review sample from Unified artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import kell_unified_history_audit as audit


def _sample(names: set[str], date: str, group: str, limit: int) -> list[str]:
    return sorted(names, key=lambda ticker: hashlib.sha256(f"{date}:{ticker}:{group}".encode()).hexdigest())[:limit]


def _bars_for_display(rows: list) -> list[list]:
    bars = audit.v6._bars(rows)
    closes = [float(row["close"]) for row in bars]
    e10 = audit.v6._ema(closes, 10)
    e20 = audit.v6._ema(closes, 20)
    packed = []
    for index in range(max(0, len(bars) - 160), len(bars)):
        bar = bars[index]
        packed.append([
            str(bar["time"])[:10],
            *[round(float(bar[key]), 4) for key in ("open", "high", "low", "close")],
            round(float(bar["volume"])),
            round(float(e10[index]), 4) if e10[index] is not None else None,
            round(float(e20[index]), 4) if e20[index] is not None else None,
        ])
    return packed


def build(artifacts: list[tuple[str, Path]], initial_reports: dict[str, dict], tuned_reports: dict[str, dict]) -> dict:
    if {date for date, _ in artifacts} != set(initial_reports) or set(initial_reports) != set(tuned_reports):
        raise ValueError("Artifact and audit date sets differ")
    records = []
    for date, artifact in sorted(artifacts):
        source, membership, contexts, charts, benchmark = audit.load_inputs(artifact, date)
        prior, tuned = initial_reports[date], tuned_reports[date]
        for key in ("runId", "manifestSha256", "candidateCount", "chartCoverageCount"):
            if source[key] != prior[key] or source[key] != tuned[key]:
                raise ValueError(f"{date}: source differs from audit on {key}")
        prior_changes = {row["ticker"]: row for row in prior["changes"]}
        tuned_changes = {row["ticker"]: row for row in tuned["changes"]}
        groups: dict[str, set[str]] = {
            "tuned_drop": set(),
            "removed_drop": set(),
            "v5_drop": set(),
            "tuned_crossback": set(),
            "removed_crossback": set(),
        }
        scores = {}
        for ticker in sorted(membership):
            score = audit.v6.score_candidate(charts.get(ticker) or [], benchmark, contexts.get(ticker) or {})
            scores[ticker] = score
            old_stage = (tuned_changes.get(ticker) or {}).get("v5Stage", score["kell_cycle_stage"])
            initial_stage = (prior_changes.get(ticker) or {}).get("v6Stage", old_stage)
            if score.get("kell_wedge_drop"):
                groups["tuned_drop"].add(ticker)
            elif initial_stage == "wedge_drop":
                groups["removed_drop"].add(ticker)
            elif old_stage == "wedge_drop":
                groups["v5_drop"].add(ticker)
            if score.get("kell_ema_crossback"):
                groups["tuned_crossback"].add(ticker)
            elif old_stage == "ema_crossback":
                groups["removed_crossback"].add(ticker)
        limits = {"tuned_drop": 3, "removed_drop": 3, "v5_drop": 2,
                  "tuned_crossback": 2, "removed_crossback": 3}
        selected = {}
        for group, names in groups.items():
            for ticker in _sample(names, date, group, limits[group]):
                question = "wedge_drop" if "drop" in group else "ema_crossback"
                selected.setdefault((ticker, question), group)
        for (ticker, question), group in selected.items():
            score = scores[ticker]
            old_stage = (tuned_changes.get(ticker) or {}).get("v5Stage", score["kell_cycle_stage"])
            initial_stage = (prior_changes.get(ticker) or {}).get("v6Stage", old_stage)
            bars = _bars_for_display(charts[ticker])
            if not bars or bars[-1][0] > date:
                raise ValueError(f"{date}/{ticker}: missing or future bar")
            metrics = score.get("kell_metrics") or {}
            records.append({
                "id": f"{date}:{ticker}:{question}",
                "date": date, "ticker": ticker, "question": question,
                "group": group,
                "sources": membership[ticker],
                "v5Stage": old_stage,
                "initialV6Stage": initial_stage,
                "tunedV6Stage": score["kell_cycle_stage"],
                "tunedBasis": (score.get("kell_stage") or {}).get("basis") or [],
                "metrics": {key: metrics.get(key) for key in (
                    "rvol20", "close_location_pct", "wedge_drop_loss_depth_pct",
                    "recent_wedge_pop_sessions_ago")},
                "bars": bars,
            })
        print(date, "sample", len(selected), "groups", {key: len(value) for key, value in groups.items()}, flush=True)
    records.sort(key=lambda row: hashlib.sha256(row["id"].encode()).hexdigest())
    return {
        "schemaVersion": "kell-history-review-v1",
        "scope": "Blinded visual sample of v5, initial v6 and tuned v6 differences on exact historical Unified inputs; bars end at the listed signal date",
        "sessions": [date for date, _ in sorted(artifacts)],
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", action="append", required=True, metavar="YYYY-MM-DD=ARTIFACT_TAR")
    parser.add_argument("--initial", action="append", required=True, type=Path)
    parser.add_argument("--tuned", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    artifacts = []
    for item in args.artifact:
        date, sep, path = item.partition("=")
        if not sep:
            parser.error(f"Invalid artifact: {item}")
        artifacts.append((date, Path(path)))
    def reports(paths: list[Path]) -> dict[str, dict]:
        result = {}
        for path in paths:
            for row in json.loads(path.read_text(encoding="utf-8"))["sessions"]:
                if row["sessionDate"] in result:
                    raise ValueError(f"Duplicate audit date {row['sessionDate']}")
                result[row["sessionDate"]] = row
        return result
    output = build(artifacts, reports(args.initial), reports(args.tuned))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, separators=(",", ":")) + "\n", encoding="utf-8")
    print("records", len(output["records"]), "bytes", args.output.stat().st_size)


if __name__ == "__main__":
    main()
