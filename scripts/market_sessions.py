"""Shared normalization for daily bars and the versioned XNYS calendar."""

from datetime import date, datetime, timezone
import json
from pathlib import Path

CALENDAR_PATH = Path(__file__).resolve().parents[1] / "lab" / "data" / "exchange-sessions-v1.json"


def session_date(value: object) -> str | None:
    """Convert ISO or Unix seconds/milliseconds to the source's daily session label."""
    text = str(value).strip() if value is not None else ""
    if not text:
        return None
    try:
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            return date.fromisoformat(text).isoformat()
        if len(text) > 10 and text[10] in ("T", " "):
            return datetime.fromisoformat(text).date().isoformat()
        stamp = float(text)
        if stamp <= 0:
            return None
        if stamp >= 1_000_000_000_000:
            stamp /= 1000
        return datetime.fromtimestamp(stamp, timezone.utc).date().isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def bar_session_date(row: object) -> str | None:
    if isinstance(row, dict):
        return session_date(row.get("time") or row.get("date"))
    if isinstance(row, (list, tuple)) and row:
        return session_date(row[0])
    return None


def exchange_sessions(as_of: str, path: Path = CALENDAR_PATH) -> tuple[str, ...]:
    """Read authoritative session labels through a completed trading date."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != "xnys-eod-sessions-v1":
        raise ValueError("Unsupported exchange calendar: " + str(path))
    if not payload["validFrom"] <= as_of <= payload["validThrough"]:
        raise ValueError("Requested date outside exchange calendar: " + as_of)
    days = tuple(row[0] for row in payload["sessions"])
    if any(session_date(day) != day for day in days) or tuple(sorted(set(days))) != days:
        raise ValueError("Exchange calendar session labels must be unique and sorted")
    if as_of not in days:
        raise ValueError("Requested date is not an XNYS session: " + as_of)
    return tuple(day for day in days if day <= as_of)
