import unittest

from scripts.build_trend_birth_alerts import build_alerts, build_v2_alerts


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
    def test_v2_baselines_then_groups_weekly_and_daily_changes(self):
        weekly = [{
            "ticker": "BASE",
            "weeklyBirth": {"stage": 3, "stageLabel": "Ready", "metrics": {
                "baseWeeks": 52, "weeklyMaClusterPct": 4.2, "runwayPct": 20,
            }},
        }]
        daily = [{"ticker": "KELL", "kell_stage": {"primary": "base_n_break"}, "kell_readiness_score": 85}]
        current = {"shortlists": {"schemaVersion": "stockscout-shortlists-v2", "weeklyTrendBirth": weekly, "kellDaily": daily}}
        previous = {"shortlists": {"schemaVersion": "stockscout-shortlists-v2", "weeklyTrendBirth": [], "kellDaily": []}}
        first = build_v2_alerts(current, None, "https://example.test/")
        self.assertTrue(first["baselineOnly"])
        self.assertEqual([], first["messages"])
        changed = build_v2_alerts(current, previous, "https://example.test/")
        self.assertEqual(["weekly", "kell-daily"], [message["kind"] for message in changed["messages"]])
        self.assertIn("52W base", changed["messages"][0]["text"])
        self.assertEqual([], build_v2_alerts(current, current, "https://example.test/")["messages"])
        empty = {"shortlists": {"schemaVersion": "stockscout-shortlists-v2", "weeklyTrendBirth": [], "kellDaily": []}}
        cleared = build_v2_alerts(empty, current, "https://example.test/")
        self.assertEqual(["weekly"], [message["kind"] for message in cleared["messages"]])
        self.assertIn("No qualified weekly setups", cleared["messages"][0]["text"])

    def test_research_watch_never_generates_weekly_alert(self):
        research = [{"ticker": "BASE", "weeklyBirth": {"eligible": False, "stage": 1}}]
        discovery = [{"ticker": "BOTTOM", "weeklyBirth": {"eligible": False, "tier": "D"}}]
        current = {"shortlists": {"schemaVersion": "stockscout-shortlists-v2",
                                  "weeklyTrendBirth": [], "weeklyResearchWatch": research,
                                  "weeklyDiscoveryWatch": discovery, "kellDaily": []}}
        previous = {"shortlists": {"schemaVersion": "stockscout-shortlists-v2",
                                   "weeklyTrendBirth": [], "weeklyResearchWatch": [], "kellDaily": []}}
        self.assertEqual([], build_v2_alerts(current, previous, "https://example.test/")["messages"])

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

    def test_new_tracked_name_establishes_baseline_without_alert(self):
        current = {
            "source": {"sessionDate": "2026-09-24"},
            "trendBirthCandidateIndex": [
                {**item("CLOV", 4, 0), "trackedWatchlist": True, "trackedOnly": True},
            ],
        }
        previous = {
            "source": {"sessionDate": "2026-09-23"},
            "unifiedCandidateIndex": [item("AAA", 2)],
        }
        payload = build_alerts(current, previous, "https://example.test/")
        self.assertEqual(payload["triggerCount"], 0)
        self.assertEqual(payload["messages"], [])

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
