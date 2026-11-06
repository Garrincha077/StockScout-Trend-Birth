#!/usr/bin/env python3
"""Idempotent infrastructure-only reconciliation of the production Trend Birth branch.

Reads the active, fully verified Unified Pages publication. Only updates the existing
lab/refresh-trigger.txt; Review/Kell builds, Vercel, and Telegram retain their own gates.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request

UPSTREAM = "Garrincha077/StockScout-Unified"
REPO = "Garrincha077/StockScout-Trend-Birth"
BRANCH = "feature/unified-review-grid-lab"
TRIGGER_PATH = "lab/refresh-trigger.txt"
PUB_PATH = "lab/data/publication.json"
API = "https://api.github.com"
PUBLIC = "https://garrincha077.github.io/StockScout-Unified/data/manifest.json"
RUN_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})-eod-(\d+)-(\d+)$")
TOKEN = os.environ.get("GH_TOKEN", "")


def json_request(url: str, *, authenticated: bool = False,
                 method: str = "GET", data: dict | None = None) -> dict:
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "TrendBirth-Daily-Reconciler",
               "Cache-Control": "no-cache"}
    if authenticated:
        if not TOKEN:
            raise RuntimeError("GH_TOKEN is required for same-repo operations")
        headers["Authorization"] = "Bearer " + TOKEN
    payload = json.dumps(data).encode() if data is not None else None
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=payload, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=35) as response:
        return json.load(response)


def github(path: str, *, method: str = "GET", data: dict | None = None) -> dict:
    return json_request(API + path, authenticated=True, method=method, data=data)


def contents(path: str) -> tuple[str, str]:
    endpoint = f"/repos/{REPO}/contents/{path}?ref={urllib.parse.quote(BRANCH, safe='')}"
    data = github(endpoint)
    if data.get("encoding") != "base64" or not data.get("sha"):
        raise RuntimeError("Unexpected GitHub contents response: " + path)
    return base64.b64decode(data["content"]).decode("utf-8"), data["sha"]


def verify_unified() -> tuple[str, str, int]:
    active = json_request(PUBLIC + "?check=" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M"))
    session, run_id = active.get("sessionDate"), active.get("runId")
    match = RUN_PATTERN.fullmatch(str(run_id))
    if active.get("status") != "healthy" or not match or match.group(1) != session:
        raise RuntimeError(f"Upstream public manifest not an exact healthy EOD publication: {session} {run_id}")
    run_number = int(match.group(2))
    run = json_request(f"{API}/repos/{UPSTREAM}/actions/runs/{run_number}")
    if (run.get("status"), run.get("conclusion"), run.get("head_branch")) != ("completed", "success", "main"):
        raise RuntimeError(f"Upstream EOD run is not complete and successful: {run.get('html_url')}")
    jobs_data = json_request(f"{API}/repos/{UPSTREAM}/actions/runs/{run_number}/jobs?per_page=100")
    jobs = {job["name"]: job for job in jobs_data.get("jobs", [])}
    for name, step in (
        ("deploy-pages / smoke", "Verify exact remote run and every mode hash"),
        ("verify-notify", "Deliver five resumable Telegram series"),
    ):
        job = jobs.get(name)
        if not job or job.get("conclusion") != "success":
            raise RuntimeError(f"Upstream {name} not SUCCESS in EOD {run_number}")
        if not any(s.get("name") == step and s.get("conclusion") == "success"
                   for s in job.get("steps", [])):
            raise RuntimeError(f"Upstream {name}/{step} not SUCCESS in EOD {run_number}")
    return str(session), str(run_id), run_number


def reconcile() -> None:
    session, run_id, upstream_id = verify_unified()
    pub_text, _ = contents(PUB_PATH)
    pub = json.loads(pub_text)
    if pub.get("sessionDate") == session and pub.get("runId") == run_id:
        print(f"CURRENT: Review production publication already matches Unified {session} / {run_id}")
        return
    if str(pub.get("sessionDate", "")) > session:
        raise RuntimeError("Refusing to roll back a newer Trend Birth publication")

    runs = github(
        f"/repos/{REPO}/actions/runs"
        f"?branch={urllib.parse.quote(BRANCH, safe='')}&per_page=50"
    ).get("workflow_runs", [])
    active_runs = [r for r in runs if r.get("status") != "completed"
                   and r.get("head_branch") == BRANCH]
    if active_runs:
        print("IN_PROGRESS: existing Review build; no duplicate trigger: " +
              ", ".join(str(r.get("html_url")) for r in active_runs))
        return

    existing, sha = contents(TRIGGER_PATH)
    marker = re.compile(r"^unified-recovery\s+\S+\s+session=" + re.escape(session) + r"(?:\s|$)", re.M)
    if marker.search(existing):
        recent = next((r for r in runs if r.get("name") == "Unified Review Grid Lab"), None)
        raise RuntimeError(
            f"Unresolved Review for {session}: previous trigger exists but publication still differs. "
            f"Investigate {recent.get('html_url') if recent else 'Review Lab runs'}; will not blindly replay."
        )
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    new_line = f"unified-recovery {now} session={session} source-run={upstream_id}"
    new_content = existing.rstrip("\n") + "\n" + new_line + "\n"
    result = github(f"/repos/{REPO}/contents/{TRIGGER_PATH}", method="PUT", data={
        "message": f"ops: reconcile verified Unified session {session} into Trend Birth",
        "content": base64.b64encode(new_content.encode("utf-8")).decode("ascii"),
        "sha": sha,
        "branch": BRANCH,
    })
    print(f"TRIGGERED: {session} / {run_id}; commit {result['commit']['sha']}")
    print("Follow the Unified Review Grid Lab workflow to terminal state. This check sends no alerts.")


if __name__ == "__main__":
    try:
        reconcile()
    except Exception as exc:
        print(f"ATTENTION: {exc}", file=sys.stderr)
        raise
