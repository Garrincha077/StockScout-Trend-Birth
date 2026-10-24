import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).parents[1] / "scripts" / "trend_birth_stage_forward.py"
spec = importlib.util.spec_from_file_location("trend_birth_stage_forward", MODULE)
forward = importlib.util.module_from_spec(spec)
spec.loader.exec_module(forward)


def sessions(count=90):
    result = []
    current = date(2026, 6, 1)
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def point(day, aaa, bbb, run="r"):
    stages = {"AAPL": [0, 0], "AAA": [aaa, 0], "BBB": [bbb, 0]}
    counts = {str(i): 0 for i in range(5)}
    for stage, _ in stages.values():
        counts[str(stage)] += 1
    return {"sessionDate": day, "runId": run + day, "stages": stages,
            "counts": counts, "evaluatedCount": 3,
            "unavailableCount": 0, "unavailable": []}


class ForwardStageTests(unittest.TestCase):
    def fixture(self, base: Path, dates: list[str], missing_bbb=False):
        stage_dir = base / "stages"
        stage_dir.mkdir()
        pts = [point(dates[0], 0, 1), point(dates[1], 3, 0),
               point(dates[2], 3, 0), point(dates[3], 4, 0)]
        pts.extend(point(day, 4, 0) for day in dates[4:])
        grouped = {}
        for row in pts:
            grouped.setdefault(row["sessionDate"][:7], []).append(row)
        for month, rows in grouped.items():
            (stage_dir / (month + ".json")).write_text(json.dumps({
                "schemaVersion": "trend-birth-ticker-month-v1",
                "scope": forward.SCOPE, "month": month,
                "sessions": rows,
            }))
        latest = {
            "source": {"sessionDate": dates[-1]},
            "trendBirthCandidateIndex": [
                {"ticker": "AAPL", "chartBars": [
                    {"time": day, "close": 100 + index} for index, day in enumerate(dates)]},
                {"ticker": "AAA", "chartBars": [
                    {"time": day, "close": round(100 * (1.01 ** index), 5)}
                    for index, day in enumerate(dates)]},
                {"ticker": "BBB", "chartBars": [] if missing_bbb else [
                    {"time": day, "close": round(80 * (0.998 ** index), 5)}
                    for index, day in enumerate(dates)]},
            ],
        }
        latest_path = base / "latest.json"
        latest_path.write_text(json.dumps(latest))
        return stage_dir, latest_path

    def test_actual_stage_entry_not_daily_repeated_and_60d_matures(self):
        dates = sessions()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage_dir, latest = self.fixture(root, dates)
            out_dir, output = root / "outcomes", root / "report.json"
            result = forward.build(latest, stage_dir, out_dir, output)
            self.assertEqual(result["transitions"], 3)
            report = json.loads(output.read_text())
            h5 = report["byHorizon"]["5"]
            self.assertEqual(h5["3"]["n"], 1)
            self.assertEqual(h5["4"]["n"], 1)
            self.assertEqual(h5["0"]["n"], 1)
            self.assertAlmostEqual(h5["3"]["meanPct"], (1.01**5 - 1)*100, places=3)
            self.assertLess(h5["0"]["meanPct"], 0)
            self.assertEqual(report["byHorizon"]["60"]["4"]["n"], 1)
            first = (out_dir / "2026-06.json").read_bytes()
            forward.build(latest, stage_dir, out_dir, output)
            self.assertEqual(first, (out_dir / "2026-06.json").read_bytes())

    def test_pending_horizons_and_missing_price_are_not_filled_with_zero(self):
        dates = sessions(12)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage_dir, latest = self.fixture(root, dates, missing_bbb=True)
            forward.build(latest, stage_dir, root / "outcomes", root / "report.json")
            report = json.loads((root / "report.json").read_text())
            self.assertEqual(report["byHorizon"]["5"]["0"]["n"], 0)
            self.assertEqual(report["byHorizon"]["5"]["0"]["missingMatured"], 1)
            self.assertEqual(report["byHorizon"]["5"]["0"]["coveragePct"], 0)
            self.assertEqual(report["byHorizon"]["20"]["3"]["pending"], 1)
            self.assertIsNone(report["byHorizon"]["20"]["3"]["meanPct"])
            self.assertFalse(report["byHorizon"]["5"]["3"]["eligibleForCalibration"])

    def test_changed_point_in_time_stage_archive_is_rejected(self):
        dates = sessions()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            stage_dir, latest = self.fixture(root, dates)
            forward.build(latest, stage_dir, root / "outcomes", root / "report.json")
            path=stage_dir / "2026-06.json"
            payload=json.loads(path.read_text())
            payload["sessions"][1]["runId"]="rewritten"
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "Conflicting point-in-time"):
                forward.build(latest, stage_dir, root / "outcomes", root / "report.json")

    def test_compact_array_chart_and_unix_timestamp_normalization(self):
        from datetime import datetime, timezone
        day = "2026-10-23"
        seconds = int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())
        payload = {"chartBars": [
            [seconds, 98, 102, 97, 100, 300_000],
            [seconds * 1000, 98, 102, 97, 101, 300_000],
            {"time": "2026-10-22", "close": 99},
            ["2026-10-24", 100, 103, 98, 102, 300_000],
        ]}
        bars = forward._bars(payload, day)
        self.assertEqual(bars, {"2026-10-22": 99.0, "2026-10-23": 101.0})
        self.assertEqual(forward._date_from_stamp("garbage"), None)

    def test_calendar_uses_consensus_when_aapl_is_absent(self):
        dates=sessions(70)
        prices={
            "MSFT": {day: 100.0 for day in dates},
            "NVDA": {day: 200.0 for day in dates},
            "TINY": {dates[-1]: 4.0},  # one sparse ticker must not set calendar
        }
        self.assertEqual(forward._calendar(prices, dates[-1]), dates)

    def test_reference_calendar_requires_current_bar(self):
        dates=sessions()
        self.assertRaisesRegex(ValueError, "current", forward._calendar, {}, dates[-1])
        self.assertRaisesRegex(ValueError, "current", forward._calendar,
                               {"AAPL": {dates[0]: 100.0}}, dates[-1])


if __name__ == "__main__":
    unittest.main()
