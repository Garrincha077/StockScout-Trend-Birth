import unittest

from scripts.build_trend_birth_alerts import build_alerts


def item(ticker, stage, score=70, missing=None):
    checks = {
        "sma50Rising": True,
        "sma30wRising": True,
        "structureValid": True,
        "notExtended": True,
        "recentPullbackCompression": True,
        "ema10Rising": stage >= 4,
        "ema20NonFalling": stage >= 4,
        "ema10AboveEma20": stage >= 4,
        "closeAboveShortEmas": stage >= 4,
        "bullishReexpansion": stage >= 4,
    }
    return {
        "ticker": ticker,
        "kell_score": score,
        "kell_readiness_score": score,
        "kell_quality_score": score,
        "trendBirth": {
            "stage": stage,
            "stageLabel": {0: "NO SETUP / INVALIDATED", 1: "WATCH", 2: "WATCH CLOSELY", 3: "READY", 4: "TRIGGER"}[stage],
            "checks": checks,
            "missingFor4": missing or ([] if stage == 4 else ["Bullish EMA re-expansion"]),
        },
    }


class TrendBirthAlertTests(unittest.TestCase):
    def test_first_radar_day_is_baseline_only(self):
        current = {"source": {"sessionDate": "2026-09-24"}, "unifiedCandidateIndex": [item("AAA", 4)]}
        previous = {"source": {"sessionDate": "2026-09-23"}, "unifiedCandidateIndex": [{"ticker": "AAA"}]}
        payload = build_alerts(current, previous, "https://example.test/")
        self.assertTrue(payload["baselineOnly"])
        self.assertEqual(payload["messages"], [])

    def test_ready_candidates_are_grouped_and_additions_linked(self):
        current = {
            "source": {"sessionDate": "2026-09-24"},
            "unifiedCandidateIndex": [item(f"T{i}", 3, 90 - i) for i in range(7)],
        }
        previous = {
            "source": {"sessionDate": "2026-09-23"},
            "unifiedCandidateIndex": [item(f"T{i}", 2) for i in range(7)],
        }
        payload = build_alerts(current, previous, "https://example.test/?snapshot=abc", max_ready=5)
        self.assertEqual(payload["readyCount"], 7)
        self.assertEqual(len(payload["messages"]), 1)
        text = payload["messages"][0]["text"]
        self.assertIn("+2 additional candidates — View dashboard: https://example.test/?snapshot=abc", text)

    def test_each_new_trigger_gets_own_message(self):
        current = {
            "source": {"sessionDate": "2026-09-24"},
            "unifiedCandidateIndex": [item("AAA", 4), item("BBB", 4)],
        }
        previous = {
            "source": {"sessionDate": "2026-09-23"},
            "unifiedCandidateIndex": [item("AAA", 3), item("BBB", 2)],
        }
        payload = build_alerts(current, previous, "https://example.test/")
        self.assertEqual(payload["triggerCount"], 2)
        self.assertEqual([m["kind"] for m in payload["messages"]], ["trigger", "trigger"])
        self.assertTrue(all("View dashboard: https://example.test/" in m["text"] for m in payload["messages"]))

    def test_alerts_prefer_quality_screened_kell_candidates(self):
        current = {
            "source": {"sessionDate": "2026-09-24"},
            "unifiedCandidateIndex": [item("NOISY", 4, 99), item("QUALITY", 4, 70)],
            "kellCandidates": [item("QUALITY", 4, 70)],
        }
        previous = {
            "source": {"sessionDate": "2026-09-23"},
            "unifiedCandidateIndex": [item("NOISY", 3), item("QUALITY", 3)],
            "kellCandidates": [item("QUALITY", 3)],
        }
        payload = build_alerts(current, previous, "https://example.test/")
        self.assertEqual(payload["triggerCount"], 1)
        self.assertEqual(payload["messages"][0]["ticker"], "QUALITY")
        self.assertNotIn("NOISY", payload["messages"][0]["text"])

    def test_tracked_only_name_is_alert_eligible_without_widening_unified_noise(self):
        current = {
            "source": {"sessionDate": "2026-09-24"},
            "unifiedCandidateIndex": [item("NOISY", 4, 99)],
            "kellCandidates": [],
            "trendBirthCandidateIndex": [
                {**item("NOISY", 4, 99), "trackedWatchlist": False},
                {**item("CLOV", 4, 0), "trackedWatchlist": True, "trackedOnly": True},
            ],
        }
        previous = {
            "source": {"sessionDate": "2026-09-23"},
            "unifiedCandidateIndex": [item("NOISY", 3, 99)],
            "kellCandidates": [],
            "trendBirthCandidateIndex": [
                {**item("NOISY", 3, 99), "trackedWatchlist": False},
                {**item("CLOV", 3, 0), "trackedWatchlist": True, "trackedOnly": True},
            ],
        }
        payload = build_alerts(current, previous, "https://example.test/")
        self.assertEqual(payload["triggerCount"], 1)
        self.assertEqual(payload["messages"][0]["ticker"], "CLOV")
        self.assertNotIn("NOISY", payload["messages"][0]["text"])

    def test_invalidation_only_after_ready_or_trigger(self):
        current = {
            "source": {"sessionDate": "2026-09-24"},
            "unifiedCandidateIndex": [item("AAA", 0), item("BBB", 0)],
        }
        previous = {
            "source": {"sessionDate": "2026-09-23"},
            "unifiedCandidateIndex": [item("AAA", 3), item("BBB", 2)],
        }
        payload = build_alerts(current, previous, "https://example.test/")
        self.assertEqual(payload["invalidatedCount"], 1)
        self.assertIn("AAA — 3/4 → 0/4", payload["messages"][0]["text"])
        self.assertNotIn("BBB", payload["messages"][0]["text"])


if __name__ == "__main__":
    unittest.main()
