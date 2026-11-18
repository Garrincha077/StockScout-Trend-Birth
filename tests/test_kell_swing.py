import unittest
from datetime import date, timedelta

from scripts.kell_swing import MODEL, build_plan, priority
from scripts import replay_kell_swing
from scripts.market_actions import MarketAction


def candles(close, volume=900_000):
    bars = [
        {"time": "2026-11-16", "open": 99, "high": 100, "low": 97, "close": 99, "volume": volume}
        for _ in range(21)
    ]
    bars[-1] = {"time": "2026-11-17", "open": 99.5, "high": max(100, close), "low": 97.5,
                "close": close, "volume": volume}
    return bars


class KellSwingTests(unittest.TestCase):
    def plan(self, close, stage="wedge_pop", volume=900_000):
        return build_plan(candles(close, volume), {"kell_wedge_pop": True}, stage, 98.5, 98.0)

    def test_wedge_flag_without_a_pivot_break_is_a_watch(self):
        result = self.plan(99.75)
        self.assertEqual((result["state"], result["reason"]), ("watch", "below_pivot"))
        self.assertEqual(result["pivot"], 100.01)
        self.assertEqual(result["stop"], 97.5)

    def test_confirmed_pivot_and_overextended_close_have_distinct_states(self):
        result = self.plan(100.75)
        self.assertEqual((result["state"], result["orderEarliest"]), ("triggered", "next_session"))
        self.assertGreater(result["maxEntry"], result["pivot"])
        extended = self.plan(105)
        self.assertEqual((extended["state"], extended["reason"]), ("extended", "above_max_entry"))

    def test_exhaustion_low_liquidity_and_stale_bar_cannot_trigger(self):
        self.assertEqual(self.plan(101, "exhaustion_extension")["state"], "invalidated")
        self.assertEqual(self.plan(101, volume=1000)["reason"], "insufficient_liquidity")
        self.assertIsNone(build_plan(candles(101), {"kell_wedge_pop": True}, "wedge_pop", 98, 98,
                                     expected_session="2026-11-18"))

    def test_priority_puts_confirmed_pivot_above_high_score_without_trigger(self):
        watch = {"ticker": "A", "kellSwing": self.plan(99.8), "kell_readiness_score": 99}
        trigger = {"ticker": "B", "kellSwing": self.plan(100.8), "kell_readiness_score": 50}
        self.assertEqual(sorted([watch, trigger], key=priority), [trigger, watch])

    def test_replay_caps_entry_and_preserves_ambiguous_stop_and_target(self):
        plan = {"pivot": 10, "stop": 9, "maxEntry": 10.5}
        self.assertIsNone(replay_kell_swing.fills(plan, [
            {"open": 11, "high": 12, "low": 10, "close": 11.5},
        ]))
        bounds, ratio = replay_kell_swing.fills(plan, [
            {"open": 9.9, "high": 12.5, "low": 8.9, "close": 11},
        ])
        self.assertEqual(bounds, (-1, 2))
        self.assertEqual(ratio, 10)

    def test_reconstruction_pairs_identical_counts_or_drops_date(self):
        days = [(date(2026, 7, 1) + timedelta(days=i)).isoformat() for i in range(85)]
        signal = days[63]
        charts = {ticker: [{"date": day, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1_000_000}
                           for day in days]
                  for ticker in ("P1", "P2", "OLD1", "OLD2")}
        for ticker in ("P1", "P2"):
            charts[ticker][63].update(close=102, high=103)
        charts["OLD2"].pop(65)
        candidates = [{"ticker": ticker, "kell_readiness_score": 20, "stage": "wedge_pop",
                       "setups": ["kell_wedge_pop"]} for ticker in ("P1", "P2")] + [
                      {"ticker": ticker, "kell_readiness_score": 99} for ticker in ("OLD1", "OLD2")]
        snapshot = {"sessionDate": signal, "source": {}, "candidates": candidates}
        original = replay_kell_swing.replay([snapshot], charts, days, [], top=2)
        strict = replay_kell_swing.replay([snapshot], charts, days, [], top=2, complete_pairs=True)
        self.assertEqual(original["comparisons"]["5"]["pairedDates"], 1)
        self.assertEqual(strict["comparisons"]["5"]["selectedDates"], 1)
        self.assertEqual(strict["comparisons"]["5"]["pairedDates"], 0)
        self.assertIsNone(strict["comparisons"]["5"]["returnPctByCost"]["20bp"])

    def test_actual_orders_report_pending_exclusions_basis_and_fills_separately(self):
        days = tuple((date(2026, 11, 9) + timedelta(days=i)).isoformat() for i in range(9))
        plan = {"state": "triggered", "model": MODEL, "sessionDate": days[0], "setup": "wedge_pop",
                "pivot": 10, "stop": 9, "maxEntry": 10.5, "signalClose": 10.2}
        snapshots = [{"source": {}, "sessionDate": days[0], "candidates": [
            {"ticker": "A", "swing": plan},
            {"ticker": "B", "swing": {**plan, "signalClose": 20.4}},
            {"ticker": "C", "swing": plan},
            {"ticker": "D", "swing": plan},
        ]}]
        chart = [{"date": day, "open": 10, "high": 11, "low": 9.9, "close": 10.2, "volume": 1000}
                 for day in days]
        split = MarketAction("C", days[2], "split", 2, None)
        data = replay_kell_swing.build_statistics(snapshots, {ticker: chart for ticker in ("A", "B", "C")},
                                                  days, [split])
        self.assertEqual(data["reconstructed"]["sessionCount"], 0)
        self.assertEqual(data["published"]["sessionCount"], 1)
        outcome = data["published"]["outcomes"]["5"]
        self.assertEqual((outcome["selected"], outcome["pending"], outcome["corporateAction"],
                          outcome["missingBars"], outcome["unmatchedClose"], outcome["fills"]), (4, 0, 1, 1, 1, 1))
        self.assertEqual(outcome["netRByCost"]["20bp"], [0.18, 0.18])
        self.assertEqual(data["published"]["outcomes"]["20"]["pending"], 4)
