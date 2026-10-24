"""Regression tests for permanent point-in-time market internals."""
import importlib.util
import json
from pathlib import Path
import unittest

BASE = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "trend_birth_intelligence", BASE / "scripts" / "trend_birth_intelligence.py"
)
intel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intel)


def point(day, stages, unavailable=()):
    counts = {str(i): 0 for i in range(5)}
    for stage in stages.values():
        counts[str(stage)] += 1
    value = {
        "sessionDate": day, "runId": day + "-eod-1",
        "counts": counts, "evaluatedCount": len(stages),
        "unavailableCount": len(unavailable),
        "stages": {ticker: [stage, 0] for ticker, stage in stages.items()},
        "unavailable": list(unavailable),
    }
    intel._point_counts(value)
    return value


class MarketInternalsTests(unittest.TestCase):
    def test_baseline_has_null_transition_not_invented_zeros(self):
        result = intel.build_market_internals([
            point("2026-10-22", {"AAA": 0, "BBB": 3}, ["OFF"])
        ])
        first = result["points"][0]
        self.assertEqual(first["qualityBreadthPct"], 50.0)
        self.assertEqual(first["pressurePct"], 37.5)
        self.assertIsNone(first["transitions"])
        self.assertIsNone(first["matchedCount"])
        self.assertIsNone(first["qualityFlow"]["net"])

    def test_migration_and_dynamic_coverage(self):
        before = point("2026-10-22", {"AAA": 2, "BBB": 4, "CCC": 0, "GONE": 3}, ["UNAV"])
        after = point("2026-10-23", {"AAA": 3, "BBB": 2, "CCC": 4, "NEW": 0}, ["GONE"])
        got = intel.build_market_internals([before, after])["points"][1]
        self.assertEqual(got["matchedCount"], 3)
        self.assertEqual((got["newCoverage"], got["lostCoverage"]), (1, 1))
        self.assertEqual(got["transitions"][2][3], 1)
        self.assertEqual(got["transitions"][4][2], 1)
        self.assertEqual(got["transitions"][0][4], 1)
        self.assertEqual(sum(map(sum, got["transitions"])), 3)
        self.assertEqual(got["qualityFlow"], {"in": 2, "out": 1, "net": 1})
        self.assertEqual(got["fourFlow"], {"in": 1, "out": 1, "net": 0})
        self.assertAlmostEqual(got["matchedQualityDeltaPp"], 33.3333)
        self.assertEqual(got["overlapPct"], 60.0)
        # Newly introduced/removed/unavailable tickers cannot count as 0-stage exits.
        self.assertEqual(got["transitions"][3][0], 0)

    def test_rejects_empty_and_out_of_order_history(self):
        with self.assertRaisesRegex(ValueError, "without EOD"):
            intel.build_market_internals([])
        a = point("2026-10-23", {"AAA": 0})
        with self.assertRaisesRegex(ValueError, "ordered"):
            intel.build_market_internals([a, a])
        with self.assertRaisesRegex(ValueError, "ordered"):
            intel.build_market_internals([a, point("2026-10-22", {"AAA": 0})])

    def test_reconcile_actual_monthly_points_to_published_compact_series(self):
        months = intel.load_months(BASE / "lab" / "data" / "trend-birth-ticker-history")
        computed = intel.build_market_internals(intel.all_points(months))
        stored = json.loads(
            (BASE / "lab" / "data" / "trend-birth-market-internals.json").read_text(encoding="utf-8")
        )
        self.assertEqual(computed, stored)
        self.assertGreaterEqual(len(computed["points"]), 20)
        self.assertEqual(computed["points"][-1]["sessionDate"], computed["latestSessionDate"])
        for record in computed["points"]:
            self.assertEqual(sum(record["counts"].values()), record["evaluatedCount"])


if __name__ == "__main__":
    unittest.main()
