import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).parents[1] / "scripts" / "build_review_snapshot.py"
spec = importlib.util.spec_from_file_location("builder", MODULE)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuilderTests(unittest.TestCase):
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
