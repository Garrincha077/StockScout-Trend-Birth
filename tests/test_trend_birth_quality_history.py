import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "trend_birth_quality_history",
    Path(__file__).parents[1] / "scripts" / "trend_birth_quality_history.py",
)
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


def snapshot(day="2026-10-23", counts=None, unavailable=2):
    counts = counts or {"0": 10, "1": 8, "2": 6, "3": 3, "4": 1}
    return {"source": {"sessionDate": day, "runId": day + "-eod-42-1"},
            "trendBirthRadar": {"schemaVersion": "trend-birth-radar-v1",
                                "scope": "unified-plus-tracked-watchlist",
                                "stageCounts": counts,
                                "evaluatedCount": sum(counts.values()),
                                "unavailableCount": unavailable}}


class HistoryTests(unittest.TestCase):
    def test_all_stages_reconcile_and_na_is_separate(self):
        result = history.point_from_snapshot(snapshot())
        self.assertEqual([result["counts"][str(i)] for i in range(5)], [10, 8, 6, 3, 1])
        self.assertEqual((result["evaluatedCount"], result["universeCount"]), (28, 30))

    def test_legacy_dates_not_backfilled(self):
        self.assertIsNone(history.point_from_snapshot({"source": {"sessionDate": "2026-09-17"}}))

    def test_invalid_counts_fail(self):
        with self.assertRaises(ValueError):
            history.point_from_snapshot(snapshot(counts={"0": 9}))
        bad = snapshot()
        bad["trendBirthRadar"]["evaluatedCount"] = 999
        with self.assertRaises(ValueError):
            history.point_from_snapshot(bad)

    def test_immutable_daily_archives_are_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for day in ("2026-10-23", "2026-10-22"):
                (folder / (day + ".json")).write_text(json.dumps(snapshot(day)))
            (folder / "2026-09-17.json").write_text("{}")
            points = history.build_history(folder)["points"]
            self.assertEqual([p["sessionDate"] for p in points], ["2026-10-22", "2026-10-23"])


if __name__ == "__main__":
    unittest.main()
