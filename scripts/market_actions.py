"""Return valuation for as-published, unadjusted EOD close archives."""

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

try:
    from .market_sessions import session_date
except ImportError:
    from market_sessions import session_date

SCHEMA = "review-market-actions-v1"


@dataclass(frozen=True)
class MarketAction:
    ticker: str
    day: str
    kind: str
    value: float
    distribution_ticker: str | None


def read_actions(path: Path) -> tuple[list[MarketAction], str]:
    raw = path.read_bytes()
    payload = json.loads(raw)
    if payload.get("schemaVersion") != SCHEMA or payload.get("currency") != "USD":
        raise ValueError("Unsupported corporate-action ledger")
    actions = []
    seen = set()
    for row in payload["actions"]:
        ticker = row["ticker"]
        day = row["effectiveSession"]
        kind = row["kind"]
        target = row.get("distributionTicker")
        value = float(row["value"])
        key = (ticker, day, kind, target)
        if (not isinstance(ticker, str) or not ticker or not isinstance(day, str) or
                session_date(day) != day or kind not in {"split", "spin_off", "cash"} or
                not math.isfinite(value) or value <= 0 or key in seen or
                (kind == "spin_off" and (not isinstance(target, str) or not target or target == ticker)) or
                (kind != "spin_off" and target is not None) or
                not str(row.get("sourceUrl", "")).startswith("https://")):
            raise ValueError(f"Invalid or duplicate corporate action: {key}")
        seen.add(key)
        actions.append(MarketAction(ticker, day, kind, value, target))
    # The ledger defines same-day ordering. Sort dates stably, preserving it.
    return sorted(actions, key=lambda action: action.day), hashlib.sha256(raw).hexdigest()


def holding_return_pct(ticker: str, entry_day: str, exit_day: str,
                       prices: dict[str, dict[str, float]], actions: list[MarketAction]) -> float | None:
    """Value all resulting holdings at the exit close, with no reinvestment."""
    entry = prices.get(ticker, {}).get(entry_day)
    if entry is None:
        return None
    cash = 0.0
    shares = defaultdict(float, {ticker: 1.0})
    for action in actions:
        if action.day <= entry_day or action.day > exit_day or action.ticker not in shares:
            continue
        if action.kind == "split":
            shares[action.ticker] *= action.value
        elif action.kind == "spin_off":
            shares[action.distribution_ticker] += shares[action.ticker] * action.value
        else:
            cash += shares[action.ticker] * action.value
    value = cash
    for symbol, quantity in shares.items():
        close = prices.get(symbol, {}).get(exit_day)
        if close is None:
            return None
        value += quantity * close
    return (value / entry - 1) * 100
