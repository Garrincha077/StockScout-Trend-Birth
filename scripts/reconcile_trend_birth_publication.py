#!/usr/bin/env python3
"""Idempotent infrastructure-only reconciliation of the production Trend Birth branch.

Reads the active, fully verified Unified Pages publication. Dispatches the existing
Review publisher once per exact activation and records the attempt.
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

from refresh_review_publication import read_target, publisher_runs, start_publisher

UPSTREAM = "Garrincha077/StockScout-Unified"
REPO = "Garrincha077/StockScout-Trend-Birth"
BRANCH = "feature/unified-review-grid-lab"
TRIGGER_PATH = "lab/refresh-trigger.txt"
PUB_PATH = "lab/data/publication.json"
API = "https://api.github.com"
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


def verify_unified() -> dict:
    target = read_target()
    run_id = target["runId"]
    match = RUN_PATTERN.fullmatch(run_id)
    if not match:
        raise RuntimeError("Invalid active Unified run")
    run_number = int(match.group(2))
    attempt = int(match.group(3))
    run = json_request(f"{API}/repos/{UPSTREAM}/actions/runs/{run_number}")
    if (run.get("status"), run.get("conclusion"), run.get("head_branch"), run.get("run_attempt")) != (
            "completed", "success", "main", attempt):
        raise RuntimeError(f"Upstream EOD run is not complete and successful: {run.get('html_url')}")
    jobs_data = json_request(f"{API}/repos/{UPSTREAM}/actions/runs/{run_number}/attempts/{attempt}/jobs?per_page=100")
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
    return target


def has_marker(existing: str, run_id: str, manifest: str) -> bool:
    marker = re.compile(r"^unified-recovery\s+\S+\s+session=\S+\s+activation=" +
                        re.escape(run_id) + r"\s+manifest=" + re.escape(manifest) + r"(?:\s|$)", re.M)
    return marker.search(existing) is not None


def reconcile() -> None:
    target = verify_unified()
    session, run_id = target["sessionDate"], target["runId"]
    manifest = target["unifiedManifestSha256"]
    pub_text, _ = contents(PUB_PATH)
    pub = json.loads(pub_text)
    if all(pub.get(key) == value for key, value in target.items()):
        print(f"CURRENT: Review production publication already matches Unified {session} / {run_id}")
        return
    if str(pub.get("sessionDate", "")) > session:
        raise RuntimeError("Refusing to roll back a newer Trend Birth publication")
    before = RUN_PATTERN.fullmatch(str(pub.get("runId") or ""))
    after = RUN_PATTERN.fullmatch(run_id)
    if (pub.get("sessionDate") == session and before and after and
            tuple(map(int, before.groups()[1:])) > tuple(map(int, after.groups()[1:]))):
        raise RuntimeError("Refusing to roll back a newer Unified attempt")

    runs = publisher_runs(REPO)
    active_runs = [r for r in runs if r.get("status") != "completed"
                   and r.get("head_branch") == BRANCH]
    if active_runs:
        print("IN_PROGRESS: existing Review build; no duplicate trigger: " +
              ", ".join(str(r.get("html_url")) for r in active_runs))
        return

    existing, sha = contents(TRIGGER_PATH)
    if has_marker(existing, run_id, manifest):
        recent = next((r for r in runs if r.get("name") == "Unified Review Grid Lab"), None)
        raise RuntimeError(
            f"Unresolved Review for {run_id}: exact activation already dispatched. "
            f"Investigate {recent.get('html_url') if recent else 'Review Lab runs'}."
        )
    if read_target(session, run_id) != target:
        raise RuntimeError("Unified activation changed before Review dispatch")
    publisher_id = start_publisher(REPO, runs)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    new_line = f"unified-recovery {now} session={session} activation={run_id} manifest={manifest} publisher={publisher_id}"
    new_content = existing.rstrip("\n") + "\n" + new_line + "\n"
    result = github(f"/repos/{REPO}/contents/{TRIGGER_PATH}", method="PUT", data={
        "message": f"ops: reconcile verified Unified session {session} into Trend Birth",
        "content": base64.b64encode(new_content.encode("utf-8")).decode("ascii"),
        "sha": sha,
        "branch": BRANCH,
    })
    print(f"TRIGGERED: {session} / {run_id}; publisher {publisher_id}; commit {result['commit']['sha']}")
    print("Follow the Unified Review Grid Lab workflow to terminal state. This check sends no alerts.")


if __name__ == "__main__":
    try:
        reconcile()
    except Exception as exc:
        print(f"ATTENTION: {exc}", file=sys.stderr)
        raise
