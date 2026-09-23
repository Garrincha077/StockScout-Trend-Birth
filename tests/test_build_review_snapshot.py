import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).parents[1] / "scripts" / "build_review_snapshot.py"
spec = importlib.util.spec_from_file_location("builder", MODULE)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuilderTests(unittest.TestCase):
    def test_kell_dimensions_are_disjoint(self):
        self.assertTrue(set(builder.KELL_SCREEN_FIELDS).isdisjoint(builder.KELL_SETUP_FIELDS))
        self.assertTrue(set(builder.KELL_SCREEN_FIELDS).isdisjoint(builder.KELL_CONTEXT_FIELDS))
        self.assertTrue(set(builder.KELL_SETUP_FIELDS).isdisjoint(builder.KELL_CONTEXT_FIELDS))
        self.assertIn("kell_gapper", builder.KELL_SCREEN_FIELDS)
        self.assertIn("kell_wedge_pop", builder.KELL_SETUP_FIELDS)
        self.assertIn("kell_weekly_trend_ok", builder.KELL_CONTEXT_FIELDS)

    def test_relative_volume_uses_strongest_available_field(self):
        row = {"rvolToday": 2.2, "currentThrustRelVolume": 3.4, "weeklyBreakoutRvol": 2.9}
        self.assertEqual(builder.relative_volume(row), 3.4)

    def test_ryan_prefers_buy_signals(self):
        rows = [
            {"ticker": "AAA", "originalRunBuySignal": False},
            {"ticker": "BBB", "originalRunBuySignal": True},
            {"ticker": "CCC", "originalRunBuySignal": True},
        ]
        self.assertEqual([r["ticker"] for r in builder.select_mode_rows("ryan-original", rows)], ["BBB", "CCC"])

    def test_bottom_priority_rewards_structural_scores(self):
        rows = [
            {"ticker": "AAA", "score": 50, "rsRating": 70},
            {"ticker": "BBB", "longBaseScore": 80, "rsRating": 55},
        ]
        selected = builder.select_mode_rows("bottom-fishing", rows)
        self.assertEqual(selected[0]["ticker"], "BBB")

    def test_kell_gap_screen_matches_canonical_thresholds(self):
        row = {
            "ticker": "AAA",
            "close": 25.2,
            "open": 25.0,
            "ret_1d_pct": 5.0,
            "avg_volume_20d": 600_000,
        }
        metrics = builder.kell_gap_metrics(row)
        self.assertGreater(metrics["gapPct"], 3.0)
        self.assertTrue(builder.is_kell_gap_up(row))
        row["avg_volume_20d"] = 499_999
        self.assertFalse(builder.is_kell_gap_up(row))

    def test_kell_gap_exact_chart_verification(self):
        rows = []
        for index in range(20):
            rows.append({
                "time": f"2026-08-{index + 1:02d}",
                "open": 24.0,
                "high": 24.5,
                "low": 23.8,
                "close": 24.0,
                "volume": 600_000,
            })
        rows.append({
            "time": "2026-09-18",
            "open": 25.0,
            "high": 26.0,
            "low": 24.9,
            "close": 25.7,
            "volume": 1_200_000,
        })
        metrics = builder.kell_gap_from_bars(rows)
        self.assertGreater(metrics["gapPct"], 3.0)
        self.assertGreater(metrics["gapHeldPct"], 100.0)
        self.assertTrue(builder.is_kell_gap_from_bars(rows))

    def test_kell_gap_requires_price_above_20(self):
        row = {
            "ticker": "AAA",
            "close": 19.8,
            "open": 19.6,
            "ret_1d_pct": 1.0,
            "avg_volume_20d": 900_000,
        }
        self.assertFalse(builder.is_kell_gap_up(row))

    def test_kell_daily_power_requires_3x_liquid_positive_day(self):
        row = {
            "ticker": "AAA",
            "rvolToday": 3.2,
            "avgDollarVolume50d": 25_000_000,
            "price": 12,
            "ret1dPct": 4.0,
            "rsRating": 90,
        }
        self.assertIn("Daily 3x RVOL", builder.kell_signals(row, 3.0))
        row["rvolToday"] = 2.9
        self.assertNotIn("Daily 3x RVOL", builder.kell_signals(row, 3.0))

    def test_kell_full_union_chart_priority_is_next_then_ryan_then_bottom(self):
        payloads = {
            "bottom-fishing": ("bottom", {}, {}),
            "next": ("next", {}, {}),
            "ryan-original": ("ryan", {}, {}),
        }
        pool = {
            "AAA": {"chartModes": ["bottom-fishing", "next", "ryan-original"]},
            "BBB": {"chartModes": ["bottom-fishing", "ryan-original"]},
            "CCC": {"chartModes": ["bottom-fishing"]},
        }
        calls = []
        original = builder.load_charts

        def fake(root, manifest, core, tickers):
            calls.append((root, set(tickers)))
            if root == "next":
                return {"AAA": [["NEXT"]]} if "AAA" in tickers else {}
            if root == "ryan":
                return {"BBB": [["RYAN"]]} if "BBB" in tickers else {}
            if root == "bottom":
                return {ticker: [["BOTTOM"]] for ticker in tickers}
            return {}

        builder.load_charts = fake
        try:
            out = builder._load_preferred_kell_charts(payloads, pool)
        finally:
            builder.load_charts = original

        self.assertEqual(out["AAA"], [["NEXT"]])
        self.assertEqual(out["BBB"], [["RYAN"]])
        self.assertEqual(out["CCC"], [["BOTTOM"]])
        self.assertEqual(calls[0], ("next", {"AAA"}))
        self.assertEqual(calls[1], ("ryan", {"BBB"}))
        self.assertEqual(calls[2], ("bottom", {"CCC"}))

    def test_embedded_spy_benchmark_from_rs_column(self):
        charts = {
            "AAA": [
                ["2026-09-18", 100, 102, 99, 100, 1_000_000, 20.0],
                ["2026-09-21", 101, 103, 100, 102, 1_100_000, 20.8082],
            ]
        }
        benchmark = builder._embedded_spy_benchmark(charts)
        self.assertEqual(len(benchmark), 2)
        # Day 1 implies SPY=500; day 2 implies roughly SPY=490.2.
        self.assertLess(benchmark[-1]["close"], benchmark[-2]["close"])

    def test_weekly_bars_aggregate_iso_and_epoch_dates(self):
        rows = [
            ["2026-09-14", 10.0, 11.0, 9.5, 10.5, 100],
            ["2026-09-15", 10.5, 12.0, 10.0, 11.5, 150],
            [1790035200, 11.5, 13.0, 11.0, 12.5, 200],  # 2026-09-22 UTC
        ]
        weekly = builder._weekly_bars(rows, 260)
        self.assertEqual(len(weekly), 2)
        self.assertEqual(weekly[0][1], 10.0)
        self.assertEqual(weekly[0][2], 12.0)
        self.assertEqual(weekly[0][3], 9.5)
        self.assertEqual(weekly[0][4], 11.5)
        self.assertEqual(weekly[0][5], 250.0)
        self.assertEqual(weekly[1][4], 12.5)

    def test_chart_metrics_expose_turning_structure(self):
        rows = []
        price = 10.0
        for index in range(90):
            price += 0.03
            rows.append({
                "time": f"2026-01-{(index % 28) + 1:02d}",
                "open": price - 0.05,
                "high": price + 0.12,
                "low": price - 0.12,
                "close": price,
                "volume": 1_000_000 + index * 1000,
            })
        metrics = builder._chart_metrics(rows)
        self.assertIn("emaGapPct", metrics)
        self.assertIn("slope50", metrics)
        self.assertIn("swingState", metrics)
        self.assertIn("baseLike", metrics)


if __name__ == "__main__":
    unittest.main()
