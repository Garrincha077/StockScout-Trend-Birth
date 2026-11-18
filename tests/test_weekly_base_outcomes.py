import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from market_sessions import exchange_sessions
from market_actions import MarketAction
from weekly_base_outcomes import _valuation, report


class WeeklyBaseOutcomesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.calendar = exchange_sessions("2026-11-17")[-58:]
        self.source = {"sessionDate": self.calendar[-1], "unifiedManifestSha256": "a" * 64}
        self.prices = {ticker: dict.fromkeys(self.calendar, 100)
                       for ticker in ("BASE", "AAA", "PEER", "GAP", "BAD", "LATE", "MISSING")}
        self.points = [
            {"sessionDate": day, "runId": day + "-run",
             "stages": {ticker: [1 if ticker in ("AAA", "PEER", "BAD") else 3, 0]
                        for ticker in self.prices if (ticker != "MISSING" or index > 24)
                        and (ticker != "BAD" or index >= 30)}}
            for index, day in enumerate(self.calendar)
        ]

    def put(self, index, rows, run=None):
        day = self.calendar[index]
        payload = {
            "schemaVersion": "weekly-birth-shadow-audit-v1", "sessionDate": day, "runId": run or day + "-run",
            "unifiedManifestSha256": "a" * 64, "selectedCount": len(rows),
            "selected": [{"ticker": ticker, "stage": stage} for ticker, stage in rows],
        }
        (self.directory / (day + ".json")).write_text(json.dumps(payload), encoding="utf-8")

    def result(self, **options):
        return report(self.directory, self.points, self.prices, self.calendar, [], self.source, **options)

    def test_only_first_comparable_appearances_mature_from_the_next_close(self):
        base = [("BASE", "Compressed")]
        self.put(24, base)
        self.put(25, base + [("AAA", "Ready"), ("MISSING", "Ready")])
        self.put(26, base)
        entries_after_gap = base + [("AAA", "Ready"), ("GAP", "Trigger"), ("MISSING", "Ready")]
        for index in range(28, len(self.calendar)):
            entries = entries_after_gap.copy()
            if index >= 42:
                entries.append(("BAD", "Ready"))
            if index >= 54:
                entries.append(("LATE", "Trigger"))
            self.put(index, entries)
        self.prices["AAA"][self.calendar[25]] = 97
        self.prices["AAA"][self.calendar[26]] = 100
        self.prices["AAA"][self.calendar[31]] = 110
        self.prices["PEER"][self.calendar[31]] = 105
        del self.prices["BAD"][self.calendar[48]]
        cases = {}
        schedule = tuple(day for day in exchange_sessions(self.source["sessionDate"], include_future=True)
                         if day >= self.calendar[0])
        result = self.result(schedule=schedule, cases=cases)
        self.assertEqual(result["unknownFirstDate"], 2)
        self.assertEqual(result["missingPriorOrCurrentCoverage"], 1)
        self.assertEqual(result["missingSessions"], [self.calendar[27]])
        self.assertEqual(result["groups"]["all"]["entries"], 3)
        self.assertEqual(result["groups"]["3"]["entries"], 2)
        self.assertEqual(result["groups"]["4"]["entries"], 1)
        first = result["groups"]["all"]["outcomes"]["5"]
        self.assertEqual((first["observed"], first["pending"], first["missing"]), (1, 1, 1))
        self.assertEqual((first["meanPct"], first["medianPct"], first["positivePct"]), (10, 10, 100))
        self.assertEqual(first["matched"]["observed"], 1)
        self.assertEqual(first["matched"]["signalPct"], 10)
        self.assertEqual(first["matched"]["controlPct"], 5)
        self.assertEqual(first["matched"]["differencePp"], 5)
        self.assertEqual(result["groups"]["all"]["outcomes"]["126"]["pending"], 3)
        self.assertEqual(result["caseCount"], 3)
        original, missing, pending = cases["days"]
        self.assertEqual((original["entryDate"], original["exitDates"]["5"]),
                         (self.calendar[26], self.calendar[31]))
        self.assertEqual(original["cases"][0]["controlTicker"], "PEER")
        self.assertAlmostEqual(original["cases"][0]["outcomes"]["5"]["signal"]["returnPct"], 10)
        self.assertEqual(missing["cases"][0]["outcomes"]["5"]["signal"]["reasons"], ["exit_quote"])
        self.assertEqual(pending["exitDates"]["5"], schedule[60])
        self.assertIsNone(pending["cases"][0]["outcomes"]["5"]["signal"]["exitClose"])
        self.assertEqual(pending["cases"][0]["outcomes"]["5"]["signal"]["status"], "pending")

    def test_archive_revision_cannot_claim_a_first_entry_and_latest_must_align(self):
        self.put(24, [("BASE", "Compressed")])
        self.put(25, [("AAA", "Ready")], run="wrong")
        self.put(26, [("AAA", "Ready")])
        self.put(57, [("LATE", "Trigger")], run="wrong")
        with self.assertRaisesRegex(ValueError, "Latest Weekly Birth shortlist"):
            self.result()
        self.put(57, [("LATE", "Trigger")])
        result = self.result()
        self.assertEqual(result["rejectedArchives"], [self.calendar[25]])
        self.assertEqual(result["unknownFirstDate"], 3)
        self.assertEqual(result["groups"]["all"]["entries"], 0)

    def test_case_records_separate_a_missing_eod_from_an_unvalued_distribution(self):
        entry, exit_day = self.calendar[30], self.calendar[35]
        prices = {"AAA": {entry: 100, exit_day: 108}}
        gap = _valuation("NEW", entry, exit_day, self.source["sessionDate"], prices, {exit_day}, [])
        self.assertEqual(gap["reasons"], ["entry_session", "exit_quote"])
        action = MarketAction("AAA", self.calendar[32], "spin_off", .1, "MISSING")
        outcome = _valuation("AAA", entry, exit_day, self.source["sessionDate"], prices, {entry, exit_day}, [action])
        self.assertEqual(outcome["reasons"], ["valuation"])
        self.assertEqual((outcome["entryClose"], outcome["exitClose"]), (100, 108))
        self.assertIsNone(outcome["returnPct"])
