import importlib.util
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


kell = load_module("kell_scoring_validation_fixture", ROOT / "scripts" / "kell_scoring.py")
validation = load_module("kell_signal_validation", ROOT / "scripts" / "kell_signal_validation.py")


def make_bars(count=260, start=25.0, daily=0.001, volume=1_000_000, start_date=date(2025, 9, 1)):
    rows = []
    price = start
    for i in range(count):
        prev = price
        price *= 1.0 + daily
        rows.append({
            "time": (start_date + timedelta(days=i)).isoformat(),
            "open": prev,
            "high": max(prev, price) * 1.005,
            "low": min(prev, price) * 0.995,
            "close": price,
            "volume": volume,
        })
    return rows


def scored_candidate(ticker="AAA", bars=None, context=None):
    bars = bars or make_bars()
    item = {"ticker": ticker, "chartBars": bars}
    item.update(kell.score_candidate(bars, candidate_context=context or {"rsRank": 92, "beta": 1.2}))
    return item


def snapshot(*items):
    return {
        "source": {"runId": 1, "sessionDate": "2026-09-23"},
        "kellScoring": {
            "modelVersion": kell.MODEL_VERSION,
            "unifiedCandidateCount": len(items),
            "candidateGenerationChanged": False,
        },
        "kellCandidates": list(items),
    }


class KellSignalValidationTests(unittest.TestCase):
    def test_clean_scored_candidate_has_no_hard_contract_errors(self):
        report = validation.validate_snapshot(snapshot(scored_candidate()))
        self.assertTrue(report["universePreserved"])
        self.assertEqual(report["checks"]["screenContract"]["mismatchCount"], 0)
        self.assertEqual(report["checks"]["stageEventConsistency"]["mismatchCount"], 0)
        self.assertEqual(report["checks"]["layerSeparation"]["overlapCount"], 0)
        self.assertEqual(report["hardErrorCount"], 0)

    def test_screen_contract_tamper_is_detected(self):
        bars = make_bars(count=100, daily=0.001)
        prev = bars[-2]["close"]
        bars[-1].update({
            "open": prev * 1.01,
            "high": prev * 1.06,
            "low": prev * 1.005,
            "close": prev * 1.05,
            "volume": 4_000_000,
        })
        item = scored_candidate("VOL", bars)
        self.assertTrue(item["kell_bull_snort"])
        item["kell_bull_snort"] = False
        report = validation.validate_snapshot(snapshot(item))
        self.assertGreater(report["checks"]["screenContract"]["mismatchCount"], 0)
        self.assertGreater(report["hardErrorCount"], 0)

    def test_layer_overlap_is_hard_error(self):
        item = scored_candidate()
        item["kellScreens"] = ["same_tag"]
        item["kellSetups"] = ["same_tag"]
        report = validation.validate_snapshot(snapshot(item))
        self.assertEqual(report["checks"]["layerSeparation"]["overlapCount"], 1)
        self.assertGreater(report["hardErrorCount"], 0)

    def test_buyable_gap_contradiction_is_detected_independently(self):
        bars = make_bars(count=80, daily=0.001)
        prior20_high = max(row["high"] for row in bars[-21:-1])
        prev = bars[-2]["close"]
        open_price = max(prior20_high * 1.02, prev * 1.04)
        bars[-1].update({
            "open": open_price,
            "high": open_price * 1.04,
            "low": max(prev * 1.01, open_price * 0.995),
            "close": open_price * 1.025,
            "volume": 3_000_000,
        })
        item = scored_candidate("GAP", bars)
        self.assertTrue(item["kell_buyable_gap_proxy"])

        # Mutate raw bars after scoring so the validator independently catches
        # that the published setup no longer has an unfilled gap.
        item["chartBars"][-1]["low"] = prev * 0.99
        report = validation.validate_snapshot(snapshot(item))
        stats = report["checks"]["setupQuality"]["signals"]["kell_buyable_gap_proxy"]
        self.assertEqual(stats["contradiction"], 1)
        self.assertGreater(report["hardErrorCount"], 0)

    def test_crossback_raw_two_percent_wick_can_be_strong_when_under_one_atr(self):
        bars = make_bars(count=60, start=100.0, daily=0.0)
        for row in bars[-15:-1]:
            row.update({
                "open": 100.0,
                "high": 102.5,
                "low": 97.5,
                "close": 100.0,
                "volume": 1_000_000,
            })
        bars[-1].update({
            "open": 100.0,
            "high": 101.0,
            "low": 97.5,
            "close": 100.5,
            "volume": 1_000_000,
        })
        item = {
            "ticker": "WIDE",
            "kell_metrics": {"recent_wedge_pop_sessions_ago": 5},
        }
        grade, reasons = validation._audit_ema_crossback(item, validation._bars(bars))
        evidence = validation._ema_crossback_evidence(validation._bars(bars))
        self.assertLess(evidence["penetrationPct"], -2.0)
        self.assertLessEqual(evidence["undercutAtr"], 1.0)
        self.assertEqual(grade, "strong")
        self.assertNotIn("deep_ema_undercut_gt_1atr", reasons)

    def test_crossback_deep_undercut_over_one_atr_is_borderline(self):
        bars = make_bars(count=60, start=100.0, daily=0.0)
        for row in bars[-15:-1]:
            row.update({
                "open": 100.0,
                "high": 100.4,
                "low": 99.6,
                "close": 100.0,
                "volume": 1_000_000,
            })
        bars[-1].update({
            "open": 100.0,
            "high": 101.0,
            "low": 97.5,
            "close": 100.5,
            "volume": 1_000_000,
        })
        item = {
            "ticker": "DEEP",
            "kell_metrics": {"recent_wedge_pop_sessions_ago": 5},
        }
        grade, reasons = validation._audit_ema_crossback(item, validation._bars(bars))
        evidence = validation._ema_crossback_evidence(validation._bars(bars))
        self.assertGreater(evidence["undercutAtr"], 1.0)
        self.assertEqual(grade, "borderline")
        self.assertIn("deep_ema_undercut_gt_1atr", reasons)

    def test_crossback_support_distribution_is_exposed(self):
        bars = make_bars(count=60, start=100.0, daily=0.0)
        item = scored_candidate("XBACK", bars)
        item["kell_ema_crossback"] = True
        item["kell_stage"] = {"primary": "ema_crossback", "confidence": 0.9, "basis": []}
        item["kell_cycle_stage"] = "ema_crossback"
        item.setdefault("kell_metrics", {})["recent_wedge_pop_sessions_ago"] = 4
        report = validation.validate_snapshot(snapshot(item))
        support = report["checks"]["setupQuality"]["emaCrossbackSupport"]
        self.assertEqual(sum(support["distribution"].values()), 1)
        self.assertEqual(len(support["largestUndercuts"]), 1)

    def test_wedge_pop_weak_close_is_soft_quality_not_structural_borderline(self):
        bars = make_bars(count=60, start=100.0, daily=0.0)
        bars[-2].update({
            "open": 99.8,
            "high": 100.0,
            "low": 99.6,
            "close": 99.8,
            "volume": 1_000_000,
        })
        bars[-1].update({
            "open": 99.9,
            "high": 102.0,
            "low": 99.9,
            "close": 100.2,
            "volume": 1_000_000,
        })
        normalized = validation._bars(bars)
        grade, reasons = validation._audit_wedge_pop({}, normalized)
        flags, evidence = validation._wedge_pop_soft_quality_flags(normalized)
        self.assertEqual(grade, "strong")
        self.assertEqual(reasons, [])
        self.assertIn("weak_pop_close_location", flags)
        self.assertLess(evidence["closeLocationPct"], 55.0)

    def test_buyable_gap_weak_close_is_soft_quality_only(self):
        bars = make_bars(count=80, daily=0.0)
        prev = bars[-2]["close"]
        prior20_high = max(row["high"] for row in bars[-21:-1])
        open_price = max(prev * 1.05, prior20_high * 1.02)
        bars[-1].update({
            "open": open_price,
            "high": open_price * 1.08,
            "low": open_price * 0.995,
            "close": open_price * 1.001,
            "volume": 3_000_000,
        })
        item = {"kell_metrics": {"rvol20": 3.0}}
        normalized = validation._bars(bars)
        grade, reasons = validation._audit_buyable_gap(item, normalized)
        flags, evidence = validation._buyable_gap_soft_quality_flags(item, normalized)
        self.assertEqual(grade, "strong")
        self.assertEqual(reasons, [])
        self.assertIn("weak_gap_close", flags)
        self.assertLess(evidence["closeLocationPct"], 50.0)

    def test_base_n_break_falling_ema_is_borderline_not_contract_failure(self):
        bars = make_bars(count=80, start=100.0, daily=0.0)
        item = scored_candidate("BASE", bars)
        item["kell_base_n_break"] = True
        item["kell_stage"] = {"primary": "base_n_break", "confidence": 0.9, "basis": []}
        item["kell_cycle_stage"] = "base_n_break"

        # Construct a contracted 10D range with a current breakout while the
        # 20EMA has been drifting down; this is calibration evidence, not a
        # schema/contract failure.
        for i, row in enumerate(item["chartBars"][-21:-1]):
            close = 102.0 - i * 0.15
            row.update({
                "open": close,
                "high": close * 1.003,
                "low": close * 0.997,
                "close": close,
                "volume": 900_000,
            })
        prior_high = max(row["high"] for row in item["chartBars"][-11:-1])
        item["chartBars"][-1].update({
            "open": prior_high * 0.999,
            "high": prior_high * 1.02,
            "low": prior_high * 0.995,
            "close": prior_high * 1.01,
            "volume": 1_100_000,
        })
        grade, reasons = validation._audit_base_n_break(item, validation._bars(item["chartBars"]))
        self.assertIn(grade, {"borderline", "strong"})
        if grade == "borderline":
            self.assertTrue(
                "bearish_10_20_ema_structure" in reasons or "20ema_still_falling" in reasons
            )


if __name__ == "__main__":
    unittest.main()
