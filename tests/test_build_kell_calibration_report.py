import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reporter = load_module(
    "build_kell_calibration_report",
    ROOT / "scripts" / "build_kell_calibration_report.py",
)


class KellCalibrationReportTests(unittest.TestCase):
    def test_collects_soft_flags_and_crossback_watch(self):
        bars = []
        for i in range(40):
            price = 100.0 + i * 0.2
            bars.append({
                "time": f"2026-08-{(i % 28) + 1:02d}",
                "open": price - 0.2,
                "high": price + 0.5,
                "low": price - 0.5,
                "close": price,
                "volume": 1_000_000,
            })
        snapshot = {
            "source": {"sessionDate": "2026-09-23"},
            "kellCandidates": [{
                "ticker": "AAA",
                "chartBars": bars,
                "kell_score": 75.0,
                "kell_readiness_score": 88.0,
                "kell_stage": {"primary": "ema_crossback"},
                "kell_metrics": {"rvol20": 1.4, "ret_3m_pct": 25, "rs_rank": 90},
            }],
        }
        validation = {
            "source": {"sessionDate": "2026-09-23"},
            "checks": {
                "setupQuality": {
                    "signals": {
                        "kell_ema_crossback": {
                            "total": 1, "strong": 1, "borderline": 0, "contradiction": 0,
                        }
                    },
                    "examples": {},
                    "softQualityFlags": {
                        "counts": {"kell_wedge_pop:weak_pop_close_location": 1},
                        "examples": [{
                            "ticker": "AAA",
                            "setup": "kell_wedge_pop",
                            "flags": ["weak_pop_close_location"],
                            "stage": "ema_crossback",
                        }],
                    },
                    "emaCrossbackSupport": {
                        "largestUndercuts": [{
                            "ticker": "AAA",
                            "undercutAtr": 0.7,
                        }],
                    },
                }
            },
        }

        items = reporter._collect_review_items(snapshot, validation)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["ticker"], "AAA")
        self.assertIn("kell_wedge_pop", items[0]["setups"])
        self.assertIn("kell_ema_crossback", items[0]["setups"])

        rendered = reporter.build_html(snapshot, validation)
        self.assertIn("Kell Signal Calibration", rendered)
        self.assertIn("AAA", rendered)
        self.assertIn("weak_pop_close_location", rendered)
        self.assertIn("<svg", rendered)
        self.assertIn("Visual review only", rendered)

    def test_no_review_candidates_renders_empty_state(self):
        snapshot = {"source": {"sessionDate": "2026-09-23"}, "kellCandidates": []}
        validation = {
            "source": {"sessionDate": "2026-09-23"},
            "checks": {"setupQuality": {"signals": {}, "examples": {}}},
        }
        rendered = reporter.build_html(snapshot, validation)
        self.assertIn("No calibration candidates", rendered)


if __name__ == "__main__":
    unittest.main()
