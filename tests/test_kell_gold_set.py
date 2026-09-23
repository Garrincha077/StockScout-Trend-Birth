import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gold = load_module("kell_gold_set", ROOT / "scripts" / "kell_gold_set.py")


def label(ticker, layer, signal, verdict, baseline=True):
    return {
        "sessionDate": "2026-09-22",
        "ticker": ticker,
        "layer": layer,
        "signal": signal,
        "label": verdict,
        "predictionAtReview": baseline,
        "reasonCodes": ["reviewed"],
    }


class KellGoldSetTests(unittest.TestCase):
    def test_validation_rejects_duplicates_and_bad_labels(self):
        row = label("AAA", "setup", "kell_wedge_pop", "VALID")
        payload = {
            "schemaVersion": gold.GOLD_SCHEMA_VERSION,
            "labels": [row, dict(row, label="NOPE")],
        }
        errors = gold.validate_gold_set(payload)
        self.assertTrue(any("duplicate" in x for x in errors))
        self.assertTrue(any("invalid label" in x for x in errors))

    def test_validation_enforces_explicit_fp_fn_semantics(self):
        payload = {
            "schemaVersion": gold.GOLD_SCHEMA_VERSION,
            "labels": [
                label("AAA", "setup", "kell_wedge_pop", "FALSE_POSITIVE", baseline=False),
                label("BBB", "setup", "kell_wedge_pop", "FALSE_NEGATIVE", baseline=True),
                label("CCC", "setup", "kell_wedge_pop", "VALID", baseline=False),
            ],
        }
        errors = gold.validate_gold_set(payload)
        self.assertTrue(any("FALSE_POSITIVE requires" in x for x in errors))
        self.assertTrue(any("FALSE_NEGATIVE requires" in x for x in errors))
        self.assertTrue(any("must use FALSE_NEGATIVE" in x for x in errors))

    def test_before_after_metrics_distinguish_fix_and_regression(self):
        gold_set = {
            "schemaVersion": gold.GOLD_SCHEMA_VERSION,
            "labels": [
                label("AAA", "setup", "kell_wedge_pop", "VALID"),
                label("BBB", "setup", "kell_wedge_pop", "FALSE_POSITIVE"),
                label("CCC", "stage", "ema_crossback", "BORDERLINE"),
            ],
        }
        current = {
            "source": {"sessionDate": "2026-09-22"},
            "kellScoring": {"modelVersion": "v-test"},
            "kellCandidates": [
                {
                    "ticker": "BBB",
                    "kellSetups": [],
                    "kellScreens": [],
                    "kellContext": [],
                    "kell_stage": {"primary": "transition"},
                },
                {
                    "ticker": "CCC",
                    "kellSetups": [],
                    "kellScreens": [],
                    "kellContext": [],
                    "kell_stage": {"primary": "transition"},
                },
            ],
        }
        report = gold.evaluate_gold_set(gold_set, current=current)
        self.assertEqual(report["summary"]["fixedFalsePositives"], 1)
        self.assertEqual(report["summary"]["hardRegressions"], 1)
        self.assertEqual(report["summary"]["lostFromBaseline"], 3)
        rows = {row["ticker"]: row for row in report["rows"]}
        self.assertEqual(rows["AAA"]["change"], "regression_valid_lost")
        self.assertEqual(rows["BBB"]["change"], "fixed_false_positive")
        self.assertEqual(rows["CCC"]["change"], "borderline_removed")


    def test_recovered_v2_columnar_archive_is_supported(self):
        gold_set = {
            "schemaVersion": gold.GOLD_SCHEMA_VERSION,
            "labels": [
                label("AAA", "stage", "wedge_pop", "VALID"),
                label("AAA", "setup", "kell_wedge_pop", "VALID"),
            ],
        }
        archive = {
            "schemaVersion": "kell-score-history-v2",
            "source": {"sessionDate": "2026-09-22"},
            "kellScoring": {"modelVersion": "recovered-v2"},
            "columns": [
                "ticker", "kell_score", "legacy_v4_score", "kell_quality_score",
                "kell_readiness_score", "kell_context_score", "kell_evidence_coverage",
                "kell_stage_cap", "stage", "source_mask",
            ],
            "candidates": [["AAA", 70, 40, 60, 80, 50, 100, 100, "wedge_pop", 7]],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-09-22.json"
            path.write_text(__import__("json").dumps(archive), encoding="utf-8")
            report = gold.evaluate_gold_set(gold_set, scores_dir=Path(tmp))
        self.assertEqual(report["summary"]["evaluated"], 1)
        self.assertEqual(report["summary"]["unavailable"], 1)
        self.assertEqual(report["rows"][0]["predictionNow"], True)
        self.assertEqual(report["rows"][1]["unavailableReason"], "setup_not_archived")

    def test_legacy_archive_stage_is_evaluable_but_missing_setup_is_unavailable(self):
        gold_set = {
            "schemaVersion": gold.GOLD_SCHEMA_VERSION,
            "labels": [
                label("AAA", "stage", "wedge_pop", "VALID"),
                label("AAA", "setup", "kell_wedge_pop", "VALID"),
            ],
        }
        archive = {
            "schemaVersion": "kell-score-history-v1",
            "source": {"sessionDate": "2026-09-22"},
            "kellScoring": {"modelVersion": "old"},
            "candidates": [{"ticker": "AAA", "stage": "wedge_pop"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-09-22.json"
            path.write_text(__import__("json").dumps(archive), encoding="utf-8")
            report = gold.evaluate_gold_set(gold_set, scores_dir=Path(tmp))
        self.assertEqual(report["summary"]["evaluated"], 1)
        self.assertEqual(report["summary"]["unavailable"], 1)

    def test_false_negative_metrics_and_session_rollup(self):
        gold_set = {
            "schemaVersion": gold.GOLD_SCHEMA_VERSION,
            "labels": [
                dict(
                    label("AAA", "setup", "kell_wedge_pop", "FALSE_NEGATIVE", baseline=False),
                    sessionDate="2026-09-21",
                ),
                dict(
                    label("BBB", "setup", "kell_buyable_gap_proxy", "FALSE_POSITIVE"),
                    sessionDate="2026-09-21",
                ),
                dict(
                    label("CCC", "setup", "kell_wedge_pop", "FALSE_NEGATIVE", baseline=False),
                    sessionDate="2026-09-22",
                ),
            ],
        }
        archives = {
            "2026-09-21": {
                "source": {"sessionDate": "2026-09-21"},
                "kellScoring": {"modelVersion": "v-test"},
                "kellCandidates": [
                    {"ticker": "AAA", "kellSetups": [], "kell_stage": {"primary": "transition"}},
                    {
                        "ticker": "BBB",
                        "kellSetups": ["kell_buyable_gap_proxy"],
                        "kell_stage": {"primary": "transition"},
                    },
                ],
            },
            "2026-09-22": {
                "source": {"sessionDate": "2026-09-22"},
                "kellScoring": {"modelVersion": "v-test"},
                "kellCandidates": [
                    {
                        "ticker": "CCC",
                        "kellSetups": ["kell_wedge_pop"],
                        "kell_stage": {"primary": "wedge_pop"},
                    }
                ],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            for session, archive in archives.items():
                (Path(tmp) / f"{session}.json").write_text(
                    __import__("json").dumps(archive), encoding="utf-8"
                )
            report = gold.evaluate_gold_set(gold_set, scores_dir=Path(tmp))

        self.assertEqual(report["summary"]["observedFalsePositives"], 1)
        self.assertEqual(report["summary"]["observedFalseNegatives"], 2)
        self.assertEqual(report["summary"]["unresolvedFalsePositives"], 1)
        self.assertEqual(report["summary"]["unresolvedFalseNegatives"], 1)
        self.assertEqual(report["summary"]["fixedFalseNegatives"], 1)
        self.assertEqual(report["summary"]["labeledSessionCount"], 2)
        self.assertEqual(report["summary"]["sessionsWithFalsePositives"], 1)
        self.assertEqual(report["summary"]["sessionsWithFalseNegatives"], 2)
        self.assertEqual(set(report["sessions"]), {"2026-09-21", "2026-09-22"})

        rows = {(row["sessionDate"], row["ticker"]): row for row in report["rows"]}
        self.assertEqual(rows[("2026-09-21", "AAA")]["change"], "unresolved_false_negative")
        self.assertEqual(rows[("2026-09-21", "BBB")]["change"], "unresolved_false_positive")
        self.assertEqual(rows[("2026-09-22", "CCC")]["change"], "fixed_false_negative")


if __name__ == "__main__":
    unittest.main()
