#!/usr/bin/env python3
"""Compare Kell v5/v6 on exact historical StockScout Unified Pages artifacts.

Each artifact supplies its own candidate membership, scalar context and chart
shards. Both models receive identical inputs truncated to that session. This
audits classification drift, not future returns or discretionary chart truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import types
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import kell_scoring as v6  # noqa: E402
import recover_kell_history_artifact as recovery  # noqa: E402

V5_COMMIT = "37f29accc09d5159e436fd840c69f3eedb6f40e8"
MODES = recovery.MODES


def load_v5():
    source = subprocess.run(
        ["git", "show", f"{V5_COMMIT}:scripts/kell_scoring.py"],
        cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    module = types.ModuleType("kell_scoring_v5_baseline")
    exec(compile(source, f"{V5_COMMIT}:scripts/kell_scoring.py", "exec"), module.__dict__)
    return module


def load_inputs(tar_path: Path, expected_date: str) -> tuple[dict, dict, dict, dict, list]:
    artifact = recovery.PagesArtifact(tar_path)
    try:
        raw_manifest = artifact.bytes("data/manifest.json")
        unified = json.loads(raw_manifest)
        date = str(unified.get("sessionDate") or "")
        run_id = str(unified.get("runId") or "")
        if date != expected_date or not run_id:
            raise ValueError(f"{tar_path}: expected {expected_date}, found {date}/{run_id}")

        membership: dict[str, list[str]] = {}
        contexts: dict[str, dict] = {}
        context_priority: dict[str, int] = {}
        mode_data = {}
        priority = {"ryan-original": 1, "bottom-fishing": 2, "next": 3}
        for mode in MODES:
            manifest, core = recovery._load_mode(artifact, mode)
            if manifest.get("sessionDate") != date or manifest.get("runId") != run_id:
                raise ValueError(f"{mode}: manifest identity differs from Unified {run_id}")
            mode_data[mode] = (manifest, core)
            for row in core.get("universe") or []:
                ticker = str(row.get("ticker") or "").strip().upper()
                if not ticker:
                    continue
                membership.setdefault(ticker, []).append(mode)
                if priority[mode] >= context_priority.get(ticker, 0):
                    contexts[ticker] = row
                    context_priority[ticker] = priority[mode]

        union = set(membership)
        next_manifest, next_core = mode_data["next"]
        next_names = {str(row.get("ticker") or "").strip().upper() for row in next_core.get("universe") or []}
        next_names.discard("")
        charts = recovery._load_json_chart_shards(artifact, "next", next_manifest, next_core, next_names)
        benchmark = recovery._embedded_spy_benchmark(charts)
        ryan_manifest, ryan_core = mode_data["ryan-original"]
        missing = union.difference(charts)
        if missing:
            charts.update(recovery._load_json_chart_shards(
                artifact, "ryan-original", ryan_manifest, ryan_core, missing,
            ))
        bottom_manifest, _ = mode_data["bottom-fishing"]
        missing = union.difference(charts)
        if missing:
            charts.update(recovery._load_bottom_charts(artifact, bottom_manifest, missing))

        future_bars = [
            ticker for ticker, bars in charts.items()
            if bars and str((bars[-1].get("time") or bars[-1].get("date")) if isinstance(bars[-1], dict) else bars[-1][0])[:10] > date
        ]
        if future_bars:
            raise ValueError(f"future chart bars in {date}: {future_bars[:5]}")
        source = {
            "sessionDate": date,
            "runId": run_id,
            "manifestSha256": hashlib.sha256(raw_manifest).hexdigest(),
            "artifactPath": str(tar_path.resolve()),
            "candidateCount": len(union),
            "chartCoverageCount": len(charts),
            "benchmarkBars": len(benchmark),
        }
        return source, membership, contexts, charts, benchmark
    finally:
        artifact.close()


def audit_session(tar_path: Path, expected_date: str, v5) -> dict:
    source, membership, contexts, charts, benchmark = load_inputs(tar_path, expected_date)
    counts = {"v5": Counter(), "v6": Counter()}
    setups = {"v5": Counter(), "v6": Counter()}
    focus = {"v5": 0, "v6": 0}
    matched = {"v5": 0, "v6": 0}
    changed = []
    crossback_ages = Counter()
    for ticker in sorted(membership):
        bars = charts.get(ticker) or []
        context = contexts.get(ticker) or {}
        old = v5.score_candidate(bars, benchmark, context)
        new = v6.score_candidate(bars, benchmark, context)
        old_stage, new_stage = old["kell_cycle_stage"], new["kell_cycle_stage"]
        counts["v5"][old_stage] += 1
        counts["v6"][new_stage] += 1
        for key, result in (("v5", old), ("v6", new)):
            if recovery._is_match(result):
                matched[key] += 1
            if result.get("kell_focus") is True:
                focus[key] += 1
            for field in ("kell_wedge_pop", "kell_ema_crossback", "kell_base_n_break", "kell_wedge_drop", "kell_exhaustion_extension"):
                if result.get(field) is True:
                    setups[key][field] += 1
        if old.get("kell_ema_crossback") is True:
            crossback_ages[str((old.get("kell_metrics") or {}).get("recent_wedge_pop_sessions_ago"))] += 1
        if old_stage != new_stage or bool(old.get("kell_focus")) != bool(new.get("kell_focus")):
            changed.append({
                "ticker": ticker,
                "sources": membership[ticker],
                "v5Stage": old_stage,
                "v6Stage": new_stage,
                "v5Score": old.get("kell_score"),
                "v6Score": new.get("kell_score"),
                "v5Focus": old.get("kell_focus"),
                "v6Focus": new.get("kell_focus"),
                "v5PopAge": (old.get("kell_metrics") or {}).get("recent_wedge_pop_sessions_ago"),
                "v6Basis": (new.get("kell_stage") or {}).get("basis"),
            })
    source.update({
        "matched": matched,
        "focus": focus,
        "stageCounts": {key: dict(value) for key, value in counts.items()},
        "eventCounts": {key: dict(value) for key, value in setups.items()},
        "v5CrossbackPopAges": dict(crossback_ages),
        "stageOrFocusChanged": len(changed),
        "changes": changed,
    })
    return source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", action="append", required=True, metavar="YYYY-MM-DD=ARTIFACT_TAR")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    v5 = load_v5()
    sessions = []
    for item in args.artifact:
        date, sep, path = item.partition("=")
        if not sep or not date or not path:
            parser.error(f"Invalid --artifact {item!r}")
        session = audit_session(Path(path), date, v5)
        sessions.append(session)
        print(f"{date}: {session['candidateCount']} Unified names, {session['chartCoverageCount']} charts, "
              f"{session['stageOrFocusChanged']} changed; "
              f"Crossback {session['eventCounts']['v5'].get('kell_ema_crossback', 0)}->"
              f"{session['eventCounts']['v6'].get('kell_ema_crossback', 0)}, "
              f"Wedge Drop {session['eventCounts']['v5'].get('kell_wedge_drop', 0)}->"
              f"{session['eventCounts']['v6'].get('kell_wedge_drop', 0)}", flush=True)
    sessions.sort(key=lambda row: row["sessionDate"])
    report = {
        "schemaVersion": "kell-unified-history-audit-v1",
        "v5Commit": V5_COMMIT,
        "candidateSourceSha256": hashlib.sha256(
            (ROOT / "scripts/kell_scoring.py").read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
        ).hexdigest(),
        "comparison": "same exact-session Unified membership, scalar context, bars and embedded benchmark for both models",
        "limitations": "This measures classification drift, not chart-label precision or forward trade results.",
        "sessions": sessions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
