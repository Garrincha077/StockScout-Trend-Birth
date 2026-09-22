import importlib.util
import pathlib
import unittest
from datetime import date, timedelta

MODULE = pathlib.Path(__file__).parents[1] / "scripts" / "kell_scoring.py"
spec = importlib.util.spec_from_file_location("kell_scoring", MODULE)
kell = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kell)


def make_bars(count=260, start=20.0, daily=0.003, volume=1_200_000, start_date=date(2025, 9, 1)):
    rows = []
    price = start
    for i in range(count):
        prev = price
        price = price * (1.0 + daily)
        rows.append({
            "time": (start_date + timedelta(days=i)).isoformat(),
            "open": prev,
            "high": max(prev, price) * 1.005,
            "low": min(prev, price) * 0.995,
            "close": price,
            "volume": volume,
        })
    return rows


def set_close(row, close, spread=0.004, volume=None):
    row["open"] = close * 0.998
    row["high"] = close * (1.0 + spread)
    row["low"] = close * (1.0 - spread)
    row["close"] = close
    if volume is not None:
        row["volume"] = volume


class KellScoringTests(unittest.TestCase):
    def test_score_exposes_v2_fields(self):
        out = kell.score_candidate(make_bars())
        for field in (
            "kell_52w_high",
            "kell_unusual_volume",
            "kell_rvol_3x",
            "kell_bull_snort",
            "kell_momentum_3m_50",
            "kell_doubler_6m",
            "kell_doubler",
            "kell_gapper",
            "kell_buyable_gap_proxy",
            "kell_strength_on_down_day",
            "kell_rs_divergence",
            "kell_name_selection_ok",
            "kell_weekly_trend_ok",
            "kell_ema_readiness",
            "kell_wedge_pop",
            "kell_ema_crossback",
            "kell_base_n_break",
            "kell_tightening",
            "kell_ttftl_warning",
            "kell_breakout_proximity",
            "kell_cycle_stage",
            "kell_score",
            "score_breakdown",
        ):
            self.assertIn(field, out)
        self.assertEqual(out["score_breakdown"]["model_version"], "kell-overlay-v2-pdf")
        self.assertGreaterEqual(out["kell_score"], 0)
        self.assertLessEqual(out["kell_score"], 100)

    def test_bull_snort_is_heavy_volume_bullish_response(self):
        bars = make_bars(count=80, daily=0.001)
        prev_close = bars[-2]["close"]
        bars[-1] = {
            "time": bars[-1]["time"],
            "open": prev_close * 1.005,
            "high": prev_close * 1.045,
            "low": prev_close * 1.002,
            "close": prev_close * 1.04,
            "volume": 3_600_000,
        }
        out = kell.score_candidate(bars)
        self.assertTrue(out["kell_unusual_volume"])
        self.assertTrue(out["kell_rvol_3x"])
        self.assertTrue(out["kell_bull_snort"])

    def test_three_month_momentum_is_separate_from_true_six_month_doubler(self):
        bars = make_bars(count=150, daily=0.0)
        base = bars[-65]["close"]
        price = base
        for row in bars[-64:]:
            price *= 1.0066
            set_close(row, price)
        out = kell.score_candidate(bars)
        self.assertTrue(out["kell_momentum_3m_50"])
        self.assertFalse(out["kell_doubler_6m"])
        self.assertFalse(out["kell_doubler"])

    def test_true_six_month_doubler(self):
        bars = make_bars(count=150, daily=0.006)
        out = kell.score_candidate(bars)
        self.assertTrue(out["kell_doubler_6m"])
        self.assertTrue(out["kell_doubler"])
        self.assertGreaterEqual(out["kell_metrics"]["ret_6m_pct"], 100)

    def test_buyable_gap_proxy_requires_breakout_unfilled_gap_and_volume(self):
        bars = make_bars(count=70, daily=0.001)
        prior20_high = max(x["high"] for x in bars[-21:-1])
        prev_close = bars[-2]["close"]
        open_price = max(prior20_high * 1.02, prev_close * 1.04)
        bars[-1] = {
            "time": bars[-1]["time"],
            "open": open_price,
            "high": open_price * 1.04,
            "low": max(prev_close * 1.01, open_price * 0.995),
            "close": open_price * 1.025,
            "volume": 2_400_000,
        }
        out = kell.score_candidate(bars)
        self.assertTrue(out["kell_gapper"])
        self.assertTrue(out["kell_buyable_gap_proxy"])
        self.assertTrue(out["kell_metrics"]["gap_unfilled"])

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
        self.assertFalse(without["score_breakdown"]["criteria"]["strength_on_down_day"]["available"])

    def test_rs_divergence_detects_stock_higher_low_vs_benchmark_lower_low(self):
        bars = make_bars(count=50, daily=0.0)
        bench = make_bars(count=50, start=100.0, daily=0.0)
        for offset in range(20, 10, -1):
            idx = -offset
            set_close(bars[idx], 96.0 + (20 - offset) * 0.05)
            set_close(bench[idx], 100.0 - (20 - offset) * 0.05)
        for offset in range(10, 0, -1):
            idx = -offset
            set_close(bars[idx], 98.0 + (10 - offset) * 0.05)
            set_close(bench[idx], 97.0 - (10 - offset) * 0.15)
        out = kell.score_candidate(bars, bench)
        self.assertTrue(out["kell_rs_divergence"])

    def test_name_selection_price_and_liquidity_context(self):
        liquid = make_bars(count=40, start=20.0, volume=1_500_000)
        self.assertTrue(kell.score_candidate(liquid)["kell_name_selection_ok"])
        cheap = make_bars(count=40, start=5.0, volume=1_500_000)
        self.assertFalse(kell.score_candidate(cheap)["kell_name_selection_ok"])
        thin = make_bars(count=40, start=20.0, volume=400_000)
        self.assertFalse(kell.score_candidate(thin)["kell_name_selection_ok"])

    def test_wedge_pop_is_recapture_of_tight_ema_cluster(self):
        bars = make_bars(count=50, start=100.0, daily=0.0)
        closes = [99.8, 99.5, 99.1, 98.8, 98.6, 98.4, 98.25, 98.15, 98.08, 98.0]
        for row, close in zip(bars[-11:-1], closes):
            set_close(row, close, spread=0.002)
        set_close(bars[-1], 99.6, spread=0.003)
        bars[-1]["open"] = 98.2
        out = kell.score_candidate(bars)
        self.assertTrue(out["kell_wedge_pop"])
        self.assertEqual(out["kell_cycle_stage"], "wedge_pop")

    def test_tightening_requires_tr_contraction_plus_dryup_or_inside_bars(self):
        bars = make_bars(count=50, start=30.0, daily=0.0, volume=1_500_000)
        for row in bars[-20:-5]:
            row["high"] = 31.0
            row["low"] = 29.0
            row["volume"] = 1_500_000
        for row in bars[-5:]:
            row["open"] = 30.0
            row["high"] = 30.15
            row["low"] = 29.85
            row["close"] = 30.0
            row["volume"] = 500_000
        out = kell.score_candidate(bars)
        self.assertTrue(out["kell_tightening"])

    def test_enrich_snapshot_preserves_membership_and_order(self):
        snapshot = {
            "source": {"sessionDate": "2026-09-17"},
            "candidates": [
                {"ticker": "AAA", "chartBars": make_bars(80)},
                {"ticker": "BBB", "chartBars": make_bars(80, start=40)},
            ],
        }
        before = [x["ticker"] for x in snapshot["candidates"]]
        result = kell.enrich_snapshot(snapshot)
        self.assertEqual(before, [x["ticker"] for x in result["candidates"]])
        self.assertFalse(result["kellScoring"]["candidateGenerationChanged"])


if __name__ == "__main__":
    unittest.main()
