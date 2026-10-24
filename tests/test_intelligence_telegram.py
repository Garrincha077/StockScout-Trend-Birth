import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "build_trend_birth_alerts", Path(__file__).parents[1] / "scripts" / "build_trend_birth_alerts.py")
alerts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alerts)


class IntelligenceTelegramTests(unittest.TestCase):
    def payload(self):
        return {
            "schemaVersion": "trend-birth-intelligence-v1",
            "source": {"sessionDate": "2026-10-23", "runId": "1234", "scope": "unified-plus-tracked-watchlist",
                       "previousSessionDate": "2026-10-22"},
            "counts": {"0": 1, "1": 1, "2": 1, "3": 1, "4": 1},
            "baselineOnly": False, "commonEvaluated": 5, "newFour": 1, "toReady": 1,
            "upgrades": 2, "downgrades": 1, "newFourTickers": ["AAA"],
        }

    def test_one_existing_sender_payload_receives_daily_eod_intelligence_message(self):
        current = {
            "source": {"sessionDate": "2026-10-23", "runId": "1234"},
            "trendBirthRadar": {"schemaVersion": "trend-birth-radar-v1",
                                "stageCounts": self.payload()["counts"],
                                "evaluatedCount": 5, "unavailableCount": 0},
        }
        prior = {"kellCandidates": [{"ticker": "AAA", "trendBirth": {"available": True, "stage": 3}}]}
        result = alerts.build_alerts(current, prior, "https://example.org/", intelligence=self.payload())
        messages = [item for item in result["messages"] if item["kind"] == "intelligence-eod"]
        self.assertEqual(len(messages), 1)
        self.assertIn("Nova 4/4: 1", messages[0]["text"])
        self.assertIn("AAA", messages[0]["text"])
        self.assertIn("0/4: 1", messages[0]["text"])

    def test_misaligned_eod_is_rejected(self):
        current = {"source": {"sessionDate": "2026-10-22", "runId": "1234"},
                   "trendBirthRadar": {"stageCounts": self.payload()["counts"]}}
        prior = {"kellCandidates": [{"ticker": "AAA", "trendBirth": {"available": True, "stage": 3}}]}
        with self.assertRaisesRegex(ValueError, "not aligned"):
            alerts.build_alerts(current, prior, "https://example.org/", intelligence=self.payload())


if __name__ == "__main__":
    unittest.main()
