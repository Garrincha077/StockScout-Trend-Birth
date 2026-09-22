import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).parents[1] / "scripts" / "kell_scoring.py"
spec = importlib.util.spec_from_file_location("kell_scoring", MODULE)
kell = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kell)


def make_bars(count=260, start=10.0, daily=0.003, volume=1_000_000):
    rows = []
    price = start
    for i in range(count):
        prev = price
        price = price * (1.0 + daily)
        rows.append({
            "time": f"2026-01-{(i % 28) + 1:02d}",
            "open": prev,
            "high": price * 1.01,
            "low": prev * 0.99,
            "close": price,
            "volume": volume,
        })
    return rows


class KellScoringTests(unittest.TestCase):
    def test_score_exposes_requested_fields(self):
        bars = make_bars()
        out = kell.score_candidate(bars)
        for field in (
            "kell_52w_high",
            "kell_unusual_volume",
            "kell_rvol_3x",
            "kell_bull_snort",
            "kell_doubler",
            "kell_gapper",
            "kell_strength_on_down_day",
            "kell_ema_readiness",
            "kell_wedge_pop",
            "kell_ema_crossback",
            "kell_base_n_break",
            "kell_tightening",
            "kell_breakout_proximity",
            "kell_score",
            "score_breakdown",
        ):
            self.assertIn(field, out)
        self.assertGreaterEqual(out["kell_score"], 0)
        self.assertLessEqual(out["kell_score"], 100)

    def test_bull_snort_and_unusual_volume_proxy(self):
        bars = make_bars(count=80, daily=0.001)
        prev_close = bars[-2]["close"]
        bars[-1] = {
            "time": "2026-09-21",
            "open": prev_close * 1.01,
            "high": prev_close * 1.07,
            "low": prev_close * 1.005,
            "close": prev_close * 1.06,
            "volume": 3_000_000,
        }
        out = kell.score_candidate(bars)
        self.assertTrue(out["kell_unusual_volume"])
        self.assertTrue(out["kell_rvol_3x"])
        self.assertTrue(out["kell_bull_snort"])

    def test_doubler_accepts_strong_3m_momentum(self):
        bars = make_bars(count=140, daily=0.007)
        out = kell.score_candidate(bars)
        self.assertTrue(out["kell_doubler"])
        self.assertGreater(out["kell_metrics"]["ret_3m_pct"], 50)

    def test_gapper_proxy(self):
        bars = make_bars(count=40, daily=0.001)
        prev_close = bars[-2]["close"]
        bars[-1]["open"] = prev_close * 1.04
        bars[-1]["high"] = prev_close * 1.06
        bars[-1]["low"] = prev_close * 1.035
        bars[-1]["close"] = prev_close * 1.05
        out = kell.score_candidate(bars)
        self.assertTrue(out["kell_gapper"])

    def test_strength_on_down_day_requires_benchmark(self):
        bars = make_bars(count=40, daily=0.001)
        bench = make_bars(count=40, start=100.0, daily=0.001)
        stock_prev = bars[-2]["close"]
        bench_prev = bench[-2]["close"]
        bars[-1].update({
            "open": stock_prev * 0.995,
            "low": stock_prev * 0.99,
            "high": stock_prev * 1.035,
            "close": stock_prev * 1.03,
        })
        bench[-1].update({
            "open": bench_prev,
            "high": bench_prev * 1.001,
            "low": bench_prev * 0.97,
            "close": bench_prev * 0.98,
        })
        out = kell.score_candidate(bars, bench)
        self.assertTrue(out["kell_strength_on_down_day"])
        without = kell.score_candidate(bars)
        self.assertIsNone(without["kell_strength_on_down_day"])
        self.assertFalse(
            without["score_breakdown"]["criteria"]["strength_on_down_day"]["available"]
        )

    def test_enrich_snapshot_preserves_membership_and_order(self):
        snapshot = {
            "source": {"sessionDate": "2026-09-17"},
            "candidates": [
                {"ticker": "AAA", "chartBars": make_bars(80)},
                {"ticker": "BBB", "chartBars": make_bars(80, start=20)},
            ],
        }
        before = [x["ticker"] for x in snapshot["candidates"]]
        result = kell.enrich_snapshot(snapshot)
        self.assertEqual(before, [x["ticker"] for x in result["candidates"]])
        self.assertFalse(result["kellScoring"]["candidateGenerationChanged"])


if __name__ == "__main__":
    unittest.main()
