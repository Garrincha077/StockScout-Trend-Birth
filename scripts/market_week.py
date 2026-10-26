"""Offline exchange-session week completion, with a conservative legacy fallback."""
from datetime import timedelta
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def _week_ends():
    doc = json.loads((Path(__file__).with_name("data") / "xnys-week-ends-v1.json").read_text())
    if doc["schemaVersion"] != "xnys-week-ends-v1":
        raise ValueError("Unsupported exchange week calendar")
    from datetime import date
    result = {}
    for value in doc["lastSessions"]:
        day = date.fromisoformat(value)
        monday = (day - timedelta(days=day.weekday())).isoformat()
        if monday in result:
            raise ValueError("Duplicate exchange week")
        result[monday] = day
    return result


def week_is_complete(last_day):
    monday = (last_day - timedelta(days=last_day.weekday())).isoformat()
    expected = _week_ends().get(monday)
    # Beyond the versioned calendar, preserve the former conservative Friday
    # behavior. Never invent an earlier final session for an unknown week.
    return last_day == expected if expected is not None else last_day.weekday() == 4
