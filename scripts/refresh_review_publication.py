"""Refresh the sole LAB publisher only when needed, then verify public identity.

This controller has no Telegram access. Public pointer checks are small; chart
archives are validated by the publisher and Unified's notification verifier.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal

BRANCH = "feature/unified-review-grid-lab"
WORKFLOW = "unified-review-grid-lab.yml"
UNIFIED = "https://garrincha077.github.io/StockScout-Unified/data/"
DEPLOYED = "https://stockscout-trend-birth-review-lab.vercel.app/data/publication.json"


def latest_completed_session(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    now = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
    today = now.astimezone(ZoneInfo("America/New_York")).date()
    schedule = mcal.get_calendar("NYSE").schedule(today - timedelta(days=14), today)
    closed = schedule.loc[schedule["market_close"] <= now]
    if closed.empty:
        raise ValueError("No completed NYSE session in the calendar")
    return closed.index[-1].date().isoformat()


def fetch_bytes(url: str) -> bytes:
    separator = "&" if "?" in url else "?"
    request = Request(url + separator + urlencode({"refresh": time.time_ns()}),
                      headers={"Cache-Control": "no-cache", "User-Agent": "StockScout-Refresh/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError("GitHub Actions API request failed")
    return result.stdout


def api(repo: str, path: str) -> dict:
    return json.loads(gh("api", f"repos/{repo}/{path}"))


def read_target(expected_session: str | None = None, expected_run: str | None = None) -> dict:
    raw = fetch_bytes(UNIFIED + "manifest.json")
    active = json.loads(raw)
    session = expected_session or latest_completed_session()
    if expected_session:
        schedule = mcal.get_calendar("NYSE").schedule(session, session)
        if schedule.empty or schedule.iloc[0]["market_close"].to_pydatetime() > datetime.now(UTC):
            raise ValueError("Requested NYSE session is not completed")
    if active.get("status") != "healthy" or active.get("sessionDate") != session:
        raise ValueError(f"STALE_UPSTREAM expected={session} actual={active.get('sessionDate')} status={active.get('status')}")
    run = active.get("runId", "")
    if not re.fullmatch(re.escape(session) + r"-eod-\d+-\d+", run):
        raise ValueError("Invalid Unified run identity")
    if expected_run and run != expected_run:
        raise ValueError(f"Unified activation changed: expected {expected_run}, got {run}")
    for mode in ("bottom-fishing", "next", "ryan-original"):
        pointer = active["modes"][mode]
        path = pointer["manifestPath"]
        if path != f"modes/{mode}/manifest.json":
            raise ValueError(f"Invalid Unified mode path: {mode}")
        content = fetch_bytes(urljoin(UNIFIED, path))
        manifest = json.loads(content)
        if hashlib.sha256(content).hexdigest() != pointer["manifestSha256"]:
            raise ValueError(f"Unified mode hash mismatch: {mode}")
        if manifest.get("runId") != run or manifest.get("mode") != mode or manifest.get("sessionDate") != session:
            raise ValueError(f"Unified mode identity mismatch: {mode}")
    return {"runId": run, "sessionDate": session, "unifiedManifestSha256": hashlib.sha256(raw).hexdigest()}


def committed_pointer(repo: str) -> dict:
    payload = api(repo, "contents/lab/data/publication.json?" + urlencode({"ref": BRANCH}))
    return json.loads(base64.b64decode(payload["content"]))


def pointer_matches(pointer: dict, target: dict) -> bool:
    if pointer.get("schemaVersion") != "trend-birth-publication-v1":
        return False
    if any(pointer.get(key) != value for key, value in target.items()):
        return False
    digest = pointer.get("sha256", "")
    identity = f"{target['runId']}--{digest}"
    count = pointer.get("candidateCount")
    return (bool(re.fullmatch(r"[a-f0-9]{64}", digest))
            and pointer.get("snapshotId") == identity
            and pointer.get("snapshotPath") == f"data/snapshots/{identity}.json"
            and type(count) is int and count >= 0 and pointer.get("chartCount") == count)


def publisher_runs(repo: str) -> list[dict]:
    query = urlencode({"branch": BRANCH, "per_page": 30})
    return api(repo, f"actions/workflows/{WORKFLOW}/runs?{query}")["workflow_runs"]


def start_publisher(repo: str, existing: list[dict]) -> int:
    before = {run["id"] for run in existing}
    gh("workflow", "run", WORKFLOW, "--repo", repo, "--ref", BRANCH)
    for _ in range(30):
        new = [run for run in publisher_runs(repo) if run["id"] not in before and run["event"] == "workflow_dispatch"]
        if len(new) == 1:
            return new[0]["id"]
        if len(new) > 1:
            raise ValueError("Ambiguous publisher dispatch; no second dispatch will be attempted")
        time.sleep(4)
    raise TimeoutError("Publisher dispatch did not appear; no second dispatch will be attempted")


def refresh(repo: str, *, dry_run: bool = False, force: bool = False,
            expected_session: str | None = None, expected_run: str | None = None,
            timeout: int = 1800) -> dict:
    target = read_target(expected_session, expected_run)
    committed = committed_pointer(repo)
    deployed = json.loads(fetch_bytes(DEPLOYED))
    aligned = pointer_matches(committed, target) and deployed == committed
    report = {**target, "status": "fresh" if aligned else "refresh_needed", "dispatched": False}
    if aligned and not force:
        if read_target(expected_session, expected_run) != target:
            raise ValueError("Unified activation changed during verification")
        return report
    runs = publisher_runs(repo)
    running = [run for run in runs if run["status"] != "completed"]
    needs_publish = force or not pointer_matches(committed, target)
    if dry_run:
        report["status"] = "publisher_running" if running else "refresh_needed" if needs_publish else "deployment_pending"
        return report
    run_id = running[0]["id"] if running else None
    if needs_publish and run_id is None:
        run_id = start_publisher(repo, runs)
        report["dispatched"] = True
    report["publisherRunId"] = run_id
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = api(repo, f"actions/runs/{run_id}") if run_id else None
        if run and run["status"] == "completed" and run["conclusion"] != "success":
            raise ValueError(f"Publisher failed: run {run_id} ({run['conclusion']})")
        committed = committed_pointer(repo)
        deployed = json.loads(fetch_bytes(DEPLOYED))
        if pointer_matches(committed, target) and deployed == committed and (not run or run["status"] == "completed"):
            if read_target(expected_session, expected_run) != target:
                raise ValueError("Unified activation changed while refreshing")
            report["status"] = "fresh"
            return report
        time.sleep(15)
    raise TimeoutError(f"PUBLICATION_TIMEOUT expected={target['sessionDate']} run={target['runId']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY", "Garrincha077/StockScout-Trend-Birth"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--session-date", default=None)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    try:
        report = refresh(args.repo, dry_run=args.dry_run, force=args.force,
                         expected_session=args.session_date, expected_run=args.run_id)
    except (ValueError, KeyError, OSError, RuntimeError, TimeoutError) as error:
        report = {"status": "failed", "reason": str(error)}
    print(json.dumps(report))
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as output:
            output.write("## Trend Birth publication readiness\n\n```json\n" + json.dumps(report, indent=2) + "\n```\n")
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
