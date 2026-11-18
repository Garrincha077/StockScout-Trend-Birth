from pathlib import Path
import unittest

from scripts.market_actions import MarketAction, holding_return_pct, read_actions


class MarketActionsTests(unittest.TestCase):
    def test_spin_off_prices_both_holdings_and_can_adjust_the_distributed_stock(self):
        actions = [
            MarketAction("CTVA", "2026-10-01", "spin_off", 1, "VYLR"),
            MarketAction("VYLR", "2026-10-05", "split", 2, None),
            MarketAction("CTVA", "2026-10-06", "cash", 1, None),
        ]
        prices = {
            "CTVA": {"2026-09-30": 80, "2026-10-06": 12},
            "VYLR": {"2026-10-06": 35},
        }
        self.assertAlmostEqual(
            holding_return_pct("CTVA", "2026-09-30", "2026-10-06", prices, actions),
            3.75,
        )
        self.assertIsNone(holding_return_pct(
            "CTVA", "2026-09-30", "2026-10-06", {"CTVA": prices["CTVA"]}, actions
        ))

    def test_entry_on_split_session_is_already_on_new_share_basis(self):
        actions = [MarketAction("ABC", "2026-11-16", "split", 4, None)]
        prices = {"ABC": {"2026-11-16": 25, "2026-11-17": 26}}
        self.assertAlmostEqual(
            holding_return_pct("ABC", "2026-11-16", "2026-11-17", prices, actions), 4.0
        )

    def test_curated_source_ledger_loads(self):
        path = Path(__file__).parents[1] / "scripts" / "data" / "review-market-actions-v1.json"
        actions, digest = read_actions(path)
        self.assertEqual([(a.ticker, a.value) for a in actions],
                         [("CTVA", 1.0), ("EMBJ", 4.0), ("SENEA", 5.0), ("SENEB", 5.0)])
        self.assertEqual(len(digest), 64)
