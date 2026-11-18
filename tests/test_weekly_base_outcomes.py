import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from market_sessions import exchange_sessions
from weekly_base_outcomes import report


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

    def result(self):
        return report(self.directory, self.points, self.prices, self.calendar, [], self.source)

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
        result = self.result()
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
