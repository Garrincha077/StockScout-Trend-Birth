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


if __name__ == "__main__":
    unittest.main()
