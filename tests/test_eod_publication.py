import copy
from datetime import datetime
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_eod_publication import expected_session, validate


class EodPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calendar = json.loads((ROOT / "lab/data/exchange-sessions-v1.json").read_text())

    def expected(self, stamp):
        return expected_session(self.calendar, datetime.fromisoformat(stamp))

    def test_weekend_and_monday_before_deadline_keep_friday(self):
        self.assertEqual(self.expected("2026-10-25T12:00:00+00:00"), "2026-10-23")
        self.assertEqual(self.expected("2026-10-26T23:59:59+00:00"), "2026-10-23")
        self.assertEqual(self.expected("2026-10-27T00:00:00+00:00"), "2026-10-26")

    def test_early_close_holiday_and_dst(self):
        self.assertEqual(self.expected("2026-11-27T21:59:59+00:00"), "2026-11-25")
        self.assertEqual(self.expected("2026-11-27T22:00:00+00:00"), "2026-11-27")
        self.assertEqual(self.expected("2026-11-03T00:30:00+00:00"), "2026-10-30")
        self.assertEqual(self.expected("2026-11-03T01:00:00+00:00"), "2026-11-02")

    def test_expired_or_unsupported_calendar_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "expired"):
            self.expected("2031-01-02T00:00:00+00:00")
        wrong = copy.deepcopy(self.calendar)
        wrong["publicationGraceHours"] = 3
        with self.assertRaisesRegex(ValueError, "policy"):
            expected_session(wrong, datetime.fromisoformat("2026-10-26T00:00:00+00:00"))

    def test_stale_source_rejected_before_other_bundle_reads(self):
        # Small fixture suffices: stale inputs must fail before downstream reads.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "publication.json").write_text("{}")
            (path / "latest.json").write_text(json.dumps({"source": {
                "runId": "old", "sessionDate": "2026-10-23", "unifiedManifestSha256": "a" * 64}}))
            with self.assertRaisesRegex(ValueError, "expected 2026-10-26"):
                validate(path, self.calendar, datetime.fromisoformat("2026-10-27T00:00:00+00:00"))


if __name__ == "__main__":
    unittest.main()
