import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))

MODULE = Path(__file__).parents[1] / "scripts" / "archive_trend_birth_closes.py"
spec = importlib.util.spec_from_file_location("archive_trend_birth_closes", MODULE)
close = importlib.util.module_from_spec(spec)
spec.loader.exec_module(close)


def point(day, run="r"):
    return {
        "sessionDate": day, "runId": run,
        "stages": {"AAA": [4, 0], "BBB": [0, 0]},
        "unavailable": ["CCC"],
        "counts": {"0": 1, "1": 0, "2": 0, "3": 0, "4": 1},
        "evaluatedCount": 2, "unavailableCount": 1,
    }


def snapshot(day, run="r"):
    return {"source": {"sessionDate": day, "runId": run},
            "trendBirthCandidateIndex": [
                {"ticker": "AAA", "metrics": {"price": 10.5}},
                {"ticker": "BBB", "metrics": {"price": 25.2}},
                {"ticker": "CCC", "metrics": {"price": 0}},
            ]}


class ArchiveClosesTests(unittest.TestCase):
    def test_extract_full_point_in_time_prices_and_exclude_unavailable(self):
        result = close.extract(snapshot("2026-10-23"), point("2026-10-23"))
        self.assertEqual(result["priceCount"], 2)
        self.assertEqual(result["prices"], {"AAA": 10.5, "BBB": 25.2})
        self.assertNotIn("CCC", result["prices"])

    def test_provenance_and_universe_conflict_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "provenance"):
            close.extract(snapshot("2026-10-23", "wrong"), point("2026-10-23"))
        altered = snapshot("2026-10-23")
        altered["trendBirthCandidateIndex"].pop()
        with self.assertRaisesRegex(ValueError, "universe"):
            close.extract(altered, point("2026-10-23"))

    def test_incremental_archive_is_idempotent_and_conflicts_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stages, history, prices = root / "stages", root / "history", root / "prices"
            stages.mkdir()
            history.mkdir()
            days = ["2026-10-22", "2026-10-23"]
            pts = [point(day) for day in days]
            (stages / "2026-10.json").write_text(json.dumps({
                "schemaVersion": "trend-birth-ticker-month-v1",
                "scope": close.SCOPE, "month": "2026-10", "sessions": pts,
            }))
            (history / "2026-10-22.json").write_text(json.dumps(snapshot(days[0])))
            last = root / "latest.json"
            last.write_text(json.dumps(snapshot(days[-1])))
            first = close.build(last, history, stages, prices)
            self.assertEqual(first["sessions"], 2)
            self.assertEqual(first["latestPriceCoveragePct"], 100)
            saved = (prices / "2026-10.json").read_bytes()
            close.build(last, history, stages, prices)
            self.assertEqual(saved, (prices / "2026-10.json").read_bytes())
            payload = json.loads((stages / "2026-10.json").read_text())
            payload["sessions"][0]["runId"] = "modified"
            (stages / "2026-10.json").write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "Conflicting immutable"):
                close.build(last, history, stages, prices)


if __name__ == "__main__":
    unittest.main()
