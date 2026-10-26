"""Development-only generator; production uses the committed XNYS session file."""
import json
from importlib.metadata import version
from pathlib import Path


def main():
    import exchange_calendars as xcals
    if version("exchange-calendars") != "4.11.3" or version("pandas") != "2.3.3":
        raise ValueError("Requires exchange-calendars==4.11.3 and pandas==2.3.3")
    cal = xcals.get_calendar("XNYS", start="2025-01-01", end="2030-12-31")
    payload = {
        "schemaVersion": "xnys-eod-sessions-v1",
        "source": "exchange-calendars==4.11.3:XNYS",
        "validFrom": "2025-01-01", "validThrough": "2030-12-31",
        "publicationGraceHours": 4,
        "sessions": [[stamp.date().isoformat(), cal.session_close(stamp).isoformat()]
                     for stamp in cal.sessions],
    }
    target = Path(__file__).resolve().parents[1] / "lab/data/exchange-sessions-v1.json"
    target.write_text(json.dumps(payload, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
