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

    def test_eod_collapses_legacy_per_ticker_alerts_into_single_grouped_message(self):
        def candidate(ticker, stage):
            return {"ticker": ticker, "trendBirth": {"available": True, "stage": stage}}
        current = {
            "source": {"sessionDate": "2026-10-23", "runId": "1234"},
            "trendBirthRadar": {"schemaVersion": "trend-birth-radar-v1",
                "stageCounts": self.payload()["counts"], "evaluatedCount": 5,
                "unavailableCount": 0},
            "kellCandidates": [candidate("AAA", 4), candidate("BBB", 4),
                               candidate("CCC", 3), candidate("DDD", 0)],
        }
        prior = {"kellCandidates": [candidate("AAA", 3), candidate("BBB", 2),
                                    candidate("CCC", 2), candidate("DDD", 4)]}
        intelligence = self.payload()
        intelligence["readyTickers"] = ["CCC"]
        intelligence["stability"] = {
            "quality": {"atLeast3": 2, "latestDropouts": 1,
                "retention": {"kept": 5, "eligible": 7, "percent": 71.4}},
            "four": {"atLeast3": 1, "latestDropouts": 1,
                "retention": {"kept": 4, "eligible": 5, "percent": 80.0}},
        }
        result = alerts.build_alerts(current, prior, "https://example.org/", intelligence=intelligence)
        self.assertEqual((result["triggerCount"], result["readyCount"], result["invalidatedCount"]), (2, 1, 1))
        self.assertEqual([m["kind"] for m in result["messages"]], ["intelligence-eod"])
        body = result["messages"][0]["text"]
        self.assertIn("Kell/tracked 4/4 (2): BBB, AAA", body)
        self.assertIn("Kell/tracked 3/4 (1): CCC", body)
        self.assertIn("Kell/tracked invalidirani (1): DDD", body)
        self.assertIn("Stabilni 3+/4", body)
        self.assertGreater(len(body.splitlines()), 6)
        fallback = alerts.build_alerts(current, prior, "https://example.org/")
        self.assertEqual(len([m for m in fallback["messages"] if m["kind"] == "trigger"]), 2)

    def test_misaligned_eod_is_rejected(self):
        current = {"source": {"sessionDate": "2026-10-22", "runId": "1234"},
                   "trendBirthRadar": {"stageCounts": self.payload()["counts"]}}
        prior = {"kellCandidates": [{"ticker": "AAA", "trendBirth": {"available": True, "stage": 3}}]}
        with self.assertRaisesRegex(ValueError, "not aligned"):
            alerts.build_alerts(current, prior, "https://example.org/", intelligence=self.payload())


if __name__ == "__main__":
    unittest.main()
