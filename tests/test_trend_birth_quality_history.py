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

    def test_compact_history_survives_pruning_of_large_raw_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            old = history.point_from_snapshot(snapshot("2026-10-21"))
            retained = {"schemaVersion": history.SCHEMA, "scope": old["scope"], "points": [old]}
            # No old raw archive remains; the next EOD snapshot must append without losing 21 October.
            (folder / "2026-10-23.json").write_text(json.dumps(snapshot("2026-10-23")))
            merged = history.merge_history(retained, history.build_history(folder))
            self.assertEqual([p["sessionDate"] for p in merged["points"]],
                             ["2026-10-21", "2026-10-23"])
            empty = history.build_history(folder / "nonexistent")
            self.assertEqual(history.merge_history(merged, empty), merged)

    def test_existing_daily_point_cannot_be_silently_rewritten(self):
        old = history.point_from_snapshot(snapshot("2026-10-23"))
        changed = history.point_from_snapshot(snapshot("2026-10-23",
                            counts={"0": 5, "1": 8, "2": 6, "3": 3, "4": 1}))
        retained = {"schemaVersion": history.SCHEMA, "scope": old["scope"], "points": [old]}
        observed = {"schemaVersion": history.SCHEMA, "scope": old["scope"], "points": [changed]}
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            history.merge_history(retained, observed)

    def test_latest_eod_matches_last_retained_session(self):
        current = snapshot("2026-10-23")
        earlier = history.point_from_snapshot(snapshot("2026-10-22"))
        latest = history.point_from_snapshot(current)
        payload = {"schemaVersion": history.SCHEMA, "scope": latest["scope"],
                   "points": [earlier, latest]}
        history.verify_latest_point(payload, current)

    def test_latest_eod_rejects_missing_radar(self):
        payload = {"schemaVersion": history.SCHEMA, "scope": None, "points": []}
        with self.assertRaisesRegex(ValueError, "no verifiable"):
            history.verify_latest_point(payload, {"source": {"sessionDate": "2026-10-23"}})

    def test_latest_eod_rejects_stale_history_and_conflicting_counts(self):
        earlier = history.point_from_snapshot(snapshot("2026-10-22"))
        payload = {"schemaVersion": history.SCHEMA, "scope": earlier["scope"],
                   "points": [earlier]}
        with self.assertRaisesRegex(ValueError, "does not match"):
            history.verify_latest_point(payload, snapshot("2026-10-23"))
        latest = history.point_from_snapshot(snapshot("2026-10-23"))
        payload["points"].append(latest)
        with self.assertRaisesRegex(ValueError, "does not match"):
            history.verify_latest_point(payload, snapshot(
                "2026-10-23", counts={"0": 9, "1": 9, "2": 6, "3": 3, "4": 1}))

    def test_latest_eod_rejects_snapshot_older_than_history(self):
        points = [history.point_from_snapshot(snapshot(day))
                  for day in ("2026-10-22", "2026-10-23")]
        payload = {"schemaVersion": history.SCHEMA, "scope": points[0]["scope"],
                   "points": points}
        with self.assertRaisesRegex(ValueError, "does not match"):
            history.verify_latest_point(payload, snapshot("2026-10-22"))


if __name__ == "__main__":
    unittest.main()
