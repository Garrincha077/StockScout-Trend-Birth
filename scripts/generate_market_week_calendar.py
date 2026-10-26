"""Rebuild the small offline XNYS week-end calendar.

One-time development dependency: exchange-calendars==4.11.3.
Production reads the committed JSON using only the Python standard library.
"""
import json
from pathlib import Path
from datetime import timedelta


def main():
    import exchange_calendars as xcals
    from importlib.metadata import version
    if version("exchange-calendars") != "4.11.3":
        raise ValueError("Calendar generator requires exchange-calendars==4.11.3")
    calendar = xcals.get_calendar("XNYS", start="1999-12-20", end="2031-01-10")
    ends = {}
    for stamp in calendar.sessions:
        day = stamp.date()
        monday = day - timedelta(days=day.weekday())
        if "2000-01-03" <= monday.isoformat() <= "2030-12-30":
            ends[monday.isoformat()] = day.isoformat()
    doc = {
        "schemaVersion": "xnys-week-ends-v1",
        "source": "exchange-calendars==4.11.3:XNYS",
        "reference": "https://github.com/gerrymanoim/exchange_calendars/tree/v4.11.3",
        "firstMonday": min(ends), "lastMonday": max(ends),
        "lastSessions": list(ends.values()),
    }
    path = Path(__file__).with_name("data") / "xnys-week-ends-v1.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(doc, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
