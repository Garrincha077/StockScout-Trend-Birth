#!/usr/bin/env python3
"""Sync the private owner watchlist into the Trend Birth tracked input.

This runs only inside the allowlisted GitHub Actions workflow. No Supabase
service-role secret is stored in this repository; the Edge Function verifies
GitHub OIDC and returns only deduplicated ticker symbols.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

DEFAULT_ENDPOINT = "https://whmjhpaxpcepmpdykrdt.supabase.co/functions/v1/unified-operations"
DEFAULT_OUTPUT = "lab/data/tracked-watchlist.json"
AUDIENCE = "stockscout-unified-operations"


def normalize_tickers(values) -> list[str]:
    out: set[str] = set()
    for value in values or []:
        ticker = str(value or "").strip().upper()
        if ticker and len(ticker) <= 20 and all(ch.isalnum() or ch in "._-" for ch in ticker):
            out.add(ticker)
    return sorted(out)


def github_oidc_token(
    request_url: str | None = None,
    request_token: str | None = None,
    opener: Callable = urlopen,
) -> str:
    base_url = request_url or os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL")
    bearer = request_token or os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    if not base_url or not bearer:
        raise RuntimeError("GitHub Actions OIDC environment is unavailable")
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["audience"] = AUDIENCE
    url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    request = Request(url, headers={"Authorization": f"Bearer {bearer}"})
    with opener(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = payload.get("value") if isinstance(payload, dict) else None
    if not token:
        raise RuntimeError("GitHub OIDC response did not contain a token")
    return str(token)


def fetch_watchlist(endpoint: str, token: str, opener: Callable = urlopen) -> list[str]:
    request = Request(
        endpoint,
        data=json.dumps({"action": "watchlist_tickers"}, separators=(",", ":")).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "StockScout-Trend-Birth/owner-watchlist-sync",
        },
        method="POST",
    )
    with opener(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError(f"Owner watchlist endpoint rejected request: {payload}")
    data = payload.get("data") or {}
    return normalize_tickers(data.get("tickers") if isinstance(data, dict) else [])


def write_watchlist(path: Path, tickers: list[str]) -> dict:
    payload = {
        "schemaVersion": "trend-birth-tracked-watchlist-v2",
        "source": "stockscout-unified-owner-state",
        "syncedAt": datetime.now(timezone.utc).isoformat(),
        "tickers": normalize_tickers(tickers),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    token = github_oidc_token()
    tickers = fetch_watchlist(args.endpoint, token)
    payload = write_watchlist(Path(args.output), tickers)
    print(json.dumps({
        "status": "ok",
        "tickers": len(payload["tickers"]),
        "output": args.output,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
