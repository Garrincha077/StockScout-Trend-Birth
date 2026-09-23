#!/usr/bin/env python3
"""Recover point-in-time Kell v5 score history from an archived Unified Pages artifact.

This is a lab-only recovery tool. It consumes the exact historical GitHub Pages artifact
for one Unified EOD session, reconstructs the deduplicated Bottom/Next/Ryan candidate
union, reuses the historical public chart shards and scalar candidate context, and scores
that historical state with the current Kell overlay.

It never reconstructs historical membership from today's universe.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kell_scoring import MODEL_VERSION, score_candidate

MODES = ("bottom-fishing", "next", "ryan-original")
SCREEN_FIELDS = (
    "kell_52w_high", "kell_unusual_volume", "kell_rvol_3x", "kell_bull_snort",
    "kell_momentum_3m_50", "kell_doubler_ytd", "kell_gapper",
    "kell_strength_on_down_day", "kell_rs_leader",
)
SETUP_FIELDS = (
    "kell_buyable_gap_proxy", "kell_wedge_pop", "kell_ema_crossback",
    "kell_base_n_break", "kell_tightening", "kell_breakout_proximity",
)
CONTEXT_FIELDS = (
    "kell_focus", "kell_name_selection_ok", "kell_growth_context",
    "kell_rs_divergence", "kell_weekly_trend_ok", "kell_ema_readiness",
)

HISTORY_COLUMNS = (
    "ticker", "kell_score", "legacy_v4_score", "kell_quality_score",
    "kell_readiness_score", "kell_context_score", "kell_evidence_coverage",
    "kell_stage_cap", "stage", "source_mask",
)


def _source_mask(sources: list[str]) -> int:
    bits = {"bottom-fishing": 1, "next": 2, "ryan-original": 4}
    return sum(bits.get(source, 0) for source in sources)


def _name(value: str) -> str:
    return value[2:] if value.startswith("./") else value


def _download(url: str, path: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "StockScout-Trend-Birth-History/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as target:
        shutil.copyfileobj(response, target, length=1024 * 1024)


def _materialize_tar(artifact_zip: Path, target: Path) -> None:
    with zipfile.ZipFile(artifact_zip) as archive:
        names = archive.namelist()
        if "artifact.tar" not in names:
            raise ValueError("Pages artifact ZIP has no artifact.tar")
        with archive.open("artifact.tar") as source, target.open("wb") as out:
            shutil.copyfileobj(source, out, length=4 * 1024 * 1024)


class PagesArtifact:
    def __init__(self, tar_path: Path):
        self.tar = tarfile.open(tar_path, "r")
        self.members = {_name(member.name): member for member in self.tar.getmembers() if member.isfile()}

    def close(self) -> None:
        self.tar.close()

    def bytes(self, path: str) -> bytes:
        member = self.members.get(_name(path))
        if member is None:
            raise KeyError(path)
        source = self.tar.extractfile(member)
        if source is None:
            raise KeyError(path)
        return source.read()

    def json(self, path: str) -> Any:
        return json.loads(self.bytes(path).decode("utf-8"))

    def has(self, path: str) -> bool:
        return _name(path) in self.members


def _mode_path(mode: str, relative: str) -> str:
    return f"data/modes/{mode}/{relative.lstrip('/')}"


def _chart_rows(payload: Any, ticker: str) -> list:
    candidate = payload.get(ticker) if isinstance(payload, dict) else None
    if candidate is None and isinstance(payload, dict) and isinstance(payload.get("byTicker"), dict):
        candidate = payload["byTicker"].get(ticker)
    if isinstance(candidate, list):
        return candidate
    if isinstance(candidate, dict):
        for key in ("daily", "rows"):
            if isinstance(candidate.get(key), list):
                return candidate[key]
    return []


def _load_mode(artifact: PagesArtifact, mode: str) -> tuple[dict, dict]:
    manifest = artifact.json(_mode_path(mode, "manifest.json"))
    core_rel = str((manifest.get("assets") or {}).get("core", {}).get("path") or "")
    if not core_rel:
        raise ValueError(f"{mode}: missing core asset")
    core = artifact.json(_mode_path(mode, core_rel))
    return manifest, core


def _load_json_chart_shards(
    artifact: PagesArtifact,
    mode: str,
    manifest: dict,
    core: dict,
    tickers: set[str],
) -> dict[str, list]:
    charts = (manifest.get("assets") or {}).get("charts") or {}
    base = str(charts.get("path") or "").rstrip("/")
    by_ticker = core.get("chartShards") or {}
    needed: dict[str, list[str]] = {}
    for ticker in tickers:
        shard = by_ticker.get(ticker)
        if shard:
            needed.setdefault(str(shard), []).append(ticker)
    out: dict[str, list] = {}
    for shard, names in needed.items():
        rel = f"{base}/{shard}"
        if not artifact.has(_mode_path(mode, rel)):
            continue
        payload = artifact.json(_mode_path(mode, rel))
        for ticker in names:
            rows = _chart_rows(payload, ticker)
            if rows:
                out[ticker] = rows[-1265:]
    return out


def _load_bottom_charts(
    artifact: PagesArtifact,
    manifest: dict,
    tickers: set[str],
) -> dict[str, list]:
    mode = "bottom-fishing"
    charts = (manifest.get("assets") or {}).get("charts") or {}
    manifest_rel = str(charts.get("path") or "")
    if not manifest_rel:
        return {}
    chart_manifest = artifact.json(_mode_path(mode, manifest_rel))
    by_ticker = chart_manifest.get("shardsByTicker") or {}
    needed: dict[str, list[str]] = {}
    for ticker in tickers:
        shard = by_ticker.get(ticker)
        if shard:
            needed.setdefault(str(shard), []).append(ticker)
    shard_root = str(Path(manifest_rel).parent / "shards").replace("\\", "/")
    out: dict[str, list] = {}
    for shard, names in needed.items():
        filename = shard if str(shard).endswith(".json.gz") else f"{shard}.json.gz"
        rel = f"{shard_root}/{filename}"
        path = _mode_path(mode, rel)
        if not artifact.has(path):
            continue
        try:
            payload = json.loads(gzip.decompress(artifact.bytes(path)).decode("utf-8"))
        except (OSError, ValueError):
            continue
        for ticker in names:
            rows = _chart_rows(payload, ticker)
            if rows:
                out[ticker] = rows[-1265:]
    return out


def _embedded_spy_benchmark(charts: dict[str, list]) -> list[dict]:
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
                    "time": str(stamp), "open": spy_close, "high": spy_close,
                    "low": spy_close, "close": spy_close, "volume": 0.0,
                })
            except (TypeError, ValueError):
                continue
        if len(derived) >= 2:
            return derived
    return []


def _is_match(scored: dict) -> bool:
    return any(scored.get(field) is True for field in (*SCREEN_FIELDS, *SETUP_FIELDS, *CONTEXT_FIELDS))


def _archive_row(ticker: str, sources: list[str], scored: dict) -> list:
    breakdown = scored.get("score_breakdown") or {}
    return [
        ticker,
        scored.get("kell_score"),
        breakdown.get("legacy_v4_score"),
        scored.get("kell_quality_score"),
        scored.get("kell_readiness_score"),
        scored.get("kell_context_score"),
        scored.get("kell_evidence_coverage"),
        scored.get("kell_stage_cap"),
        (scored.get("kell_stage") or {}).get("primary") or scored.get("kell_cycle_stage"),
        _source_mask(sources),
    ]


def _run_identity(run_id: str) -> tuple[int | None, int | None]:
    match = re.search(r"-eod-(\d+)-(\d+)$", run_id)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def recover(artifact_zip: Path, provenance: dict | None = None) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        tar_path = Path(tmp) / "artifact.tar"
        _materialize_tar(artifact_zip, tar_path)
        artifact = PagesArtifact(tar_path)
        try:
            unified = artifact.json("data/manifest.json")
            session_date = str(unified.get("sessionDate") or "")
            run_id = str(unified.get("runId") or "")
            if not session_date or not run_id:
                raise ValueError("Unified artifact missing sessionDate/runId")

            mode_data: dict[str, tuple[dict, dict]] = {}
            membership: dict[str, list[str]] = {}
            contexts: dict[str, dict] = {}
            # Match build_review_snapshot.py merge semantics exactly: Next scalars
            # override Bottom, while existing Bottom/Next scalars override Ryan.
            priority = {"ryan-original": 1, "bottom-fishing": 2, "next": 3}
            context_priority: dict[str, int] = {}
            for mode in MODES:
                manifest, core = _load_mode(artifact, mode)
                if manifest.get("sessionDate") != session_date or manifest.get("runId") != run_id:
                    raise ValueError(f"{mode}: artifact identity mismatch")
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
            next_tickers = {str(row.get("ticker") or "").strip().upper() for row in next_core.get("universe") or []}
            next_tickers.discard("")
            charts = _load_json_chart_shards(artifact, "next", next_manifest, next_core, next_tickers)
            benchmark = _embedded_spy_benchmark(charts)

            ryan_manifest, ryan_core = mode_data["ryan-original"]
            missing_after_next = union.difference(charts)
            if missing_after_next:
                charts.update(_load_json_chart_shards(
                    artifact, "ryan-original", ryan_manifest, ryan_core, missing_after_next
                ))

            bottom_manifest, _ = mode_data["bottom-fishing"]
            missing_after_adjusted = union.difference(charts)
            if missing_after_adjusted:
                charts.update(_load_bottom_charts(artifact, bottom_manifest, missing_after_adjusted))

            candidates = []
            scored_count = 0
            for ticker in sorted(union):
                rows = charts.get(ticker) or []
                scored = score_candidate(rows, benchmark, contexts.get(ticker) or {})
                if float(scored.get("kell_evidence_coverage") or 0) > 0:
                    scored_count += 1
                if _is_match(scored):
                    candidates.append(_archive_row(ticker, membership[ticker], scored))

            candidates.sort(key=lambda item: (-float(item[1] or 0), str(item[0])))
            inferred_run, inferred_attempt = _run_identity(run_id)
            provenance = dict(provenance or {})
            provided_run = provenance.get("workflowRunId")
            if provided_run is not None and inferred_run is not None and int(provided_run) != inferred_run:
                raise ValueError("provenance workflowRunId does not match Unified runId")
            provided_attempt = provenance.get("runAttempt")
            if provided_attempt is not None and inferred_attempt is not None and int(provided_attempt) != inferred_attempt:
                raise ValueError("provenance runAttempt does not match Unified runId")
            source = {
                "sessionDate": session_date,
                "runId": run_id,
                "recovered": True,
                "recoveredFrom": "historical-unified-pages-artifact",
                "recoveryMethod": "exact-github-pages-artifact",
                "recoveryReliability": "exact-pages-artifact",
                "artifactIdentityVerified": True,
                "pointInTimeCandidateMembership": True,
                "scoreSemantics": "current-model-recomputed-on-point-in-time-inputs",
                "scoreObservedAtSession": False,
                "unifiedCandidateCount": len(union),
                "chartCoverageCount": len(charts),
                "scoreCoverageCount": scored_count,
            }
            if inferred_run is not None:
                source["workflowRunId"] = inferred_run
            if inferred_attempt is not None:
                source["runAttempt"] = inferred_attempt
            for key in (
                "sourceRepository", "workflowRunId", "workflowRunNumber", "runAttempt",
                "headSha", "artifactId", "artifactName", "artifactDigest",
                "artifactCreatedAt", "artifactExpiresAt", "sourcePath",
            ):
                value = provenance.get(key)
                if value not in (None, ""):
                    source[key] = value
            return {
                "schemaVersion": "kell-score-history-v2",
                "columns": list(HISTORY_COLUMNS),
                "source": source,
                "kellScoring": {"modelVersion": MODEL_VERSION},
                "candidateCount": len(candidates),
                "candidates": candidates,
            }
        finally:
            artifact.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--artifact")
    source.add_argument("--artifact-url")
    parser.add_argument("--output-dir", default="lab/data/kell-score-history")
    parser.add_argument("--source-repository", default="Garrincha077/StockScout-Unified")
    parser.add_argument("--workflow-run-id", type=int)
    parser.add_argument("--workflow-run-number", type=int)
    parser.add_argument("--run-attempt", type=int)
    parser.add_argument("--head-sha")
    parser.add_argument("--artifact-id", type=int)
    parser.add_argument("--artifact-name", default="github-pages")
    parser.add_argument("--artifact-digest")
    parser.add_argument("--artifact-created-at")
    parser.add_argument("--artifact-expires-at")
    parser.add_argument("--source-path")
    args = parser.parse_args()
    provenance = {
        "sourceRepository": args.source_repository,
        "workflowRunId": args.workflow_run_id,
        "workflowRunNumber": args.workflow_run_number,
        "runAttempt": args.run_attempt,
        "headSha": args.head_sha,
        "artifactId": args.artifact_id,
        "artifactName": args.artifact_name,
        "artifactDigest": args.artifact_digest,
        "artifactCreatedAt": args.artifact_created_at,
        "artifactExpiresAt": args.artifact_expires_at,
        "sourcePath": args.source_path or args.artifact or args.artifact_url,
    }

    with tempfile.TemporaryDirectory() as tmp:
        if args.artifact_url:
            artifact_zip = Path(tmp) / "pages.zip"
            _download(args.artifact_url, artifact_zip)
        else:
            artifact_zip = Path(args.artifact)
        recovered = recover(artifact_zip, provenance=provenance)

    session_date = recovered["source"]["sessionDate"]
    output = Path(args.output_dir) / f"{session_date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(recovered, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({
        "status": "ok",
        "sessionDate": session_date,
        "unifiedCandidates": recovered["source"]["unifiedCandidateCount"],
        "chartCoverage": recovered["source"]["chartCoverageCount"],
        "matchedCandidates": recovered["candidateCount"],
        "output": str(output),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
