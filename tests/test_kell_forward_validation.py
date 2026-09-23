import importlib.util
import base64
import gzip
import json
import pathlib
import tempfile
import unittest
from datetime import date, timedelta

MODULE = pathlib.Path(__file__).parents[1] / "scripts" / "kell_forward_validation.py"
spec = importlib.util.spec_from_file_location("kell_forward_validation", MODULE)
validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)


def bars(start_price=100.0, daily=0.001, count=140, start=date(2026, 1, 2)):
    out = []
    price = start_price
    for i in range(count):
        current = start + timedelta(days=i)
        # keep only weekdays to mimic trading sessions
        if current.weekday() >= 5:
            continue
        prev = price
        price *= 1.0 + daily
        out.append([
            current.isoformat(),
            prev,
            max(prev, price) * 1.002,
            min(prev, price) * 0.998,
            price,
            1_000_000,
        ])
    return out


class KellForwardValidationTests(unittest.TestCase):
    def test_default_horizons_include_longer_returns(self):
        self.assertEqual(validation.DEFAULT_HORIZONS, (5, 10, 20, 40, 60, 120))

    def test_outcome_uses_trading_session_horizon_and_mfe_mae(self):
        series = [validation._normalize_bar(row) for row in bars(count=200)]
        series = [row for row in series if row is not None]
        session = series[10]["date"]
        out = validation._outcome(series, session, 20)
        self.assertIsNotNone(out)
        self.assertGreater(out["forward_return_pct"], 0)
        self.assertGreater(out["mfe_pct"], out["forward_return_pct"])
        self.assertLess(out["mae_pct"], out["mfe_pct"])

    def test_point_in_time_deciles_compare_v5_and_v4(self):
        base = bars(count=220, daily=0.0)
        session_date = base[20][0]
        snapshots = [{
            "sessionDate": session_date,
            "candidates": [],
        }]
        store = {}
        for i in range(20):
            ticker = f"T{i:02d}"
            v5 = float(i)
            v4 = float(19 - i)
            snapshots[0]["candidates"].append({
                "ticker": ticker,
                "kell_score": v5,
                "legacy_v4_score": v4,
            })
            # Higher v5 score gets better future drift.
            drift = (i - 9.5) / 9.5 * 0.002
            series = bars(start_price=100.0, daily=drift, count=220)
            store[ticker] = [validation._normalize_bar(row) for row in series]

        observations = validation.build_observations(snapshots, store, (20, 60))
        report = validation.summarize(observations, (20, 60))
        self.assertGreater(report["models"]["v5"]["20"]["topMinusBottomMeanReturnPct"], 0)
        self.assertLess(report["models"]["v4"]["20"]["topMinusBottomMeanReturnPct"], 0)
        self.assertGreater(report["models"]["v5"]["60"]["topDecile"]["mean_return_pct"], 0)

    def test_outcome_coverage_guard_blocks_incomplete_chart_store(self):
        dates = [
            "2026-09-01", "2026-09-02", "2026-09-03",
            "2026-09-04", "2026-09-07", "2026-09-08",
        ]
        bars = [
            {"date": day, "open": 10 + i, "high": 11 + i, "low": 9 + i, "close": 10 + i, "volume": 1_000_000}
            for i, day in enumerate(dates)
        ]
        snapshots = [{
            "sessionDate": "2026-09-01",
            "candidates": [
                {"ticker": "AAA", "kell_score": 90.0, "legacy_v4_score": 80.0},
                {"ticker": "BBB", "kell_score": 70.0, "legacy_v4_score": 60.0},
            ],
        }]
        observations = validation.build_observations(snapshots, {"AAA": bars}, (5,))
        coverage = validation.outcome_coverage(snapshots, {"AAA": bars}, observations, (5,))
        self.assertEqual(coverage["v5"]["5"]["expectedObservations"], 2)
        self.assertEqual(coverage["v5"]["5"]["observedObservations"], 1)
        self.assertEqual(coverage["v5"]["5"]["coveragePct"], 50.0)
        report = validation.summarize(
            observations,
            (5,),
            coverage=coverage,
            min_outcome_coverage_pct=99.0,
        )
        self.assertFalse(report["models"]["v5"]["5"]["eligibleForValidation"])
        self.assertFalse(report["comparison"]["5"]["eligibleForValidation"])
        self.assertIsNone(report["comparison"]["5"]["v5MinusV4TopDecileMeanReturnPct"])

    def test_immature_horizon_is_excluded(self):
        series = [validation._normalize_bar(row) for row in bars(count=40)]
        series = [row for row in series if row is not None]
        session = series[-10]["date"]
        out = validation._outcome(series, session, 20)
        self.assertIsNone(out)

    def test_load_score_snapshots_expands_recovered_bundle(self):
        snap = lambda d, t: {
            "schemaVersion": "kell-score-history-v2",
            "source": {"sessionDate": d, "runId": "r-" + d},
            "columns": ["ticker", "kell_score", "legacy_v4_score"],
            "candidates": [[t, 80.0, 60.0]],
        }
        payload = {
            "schemaVersion": "kell-score-history-bundle-v1",
            "snapshots": [snap("2026-09-09", "AAA"), snap("2026-09-10", "BBB")],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "recovered.json.gz"
            path.write_bytes(gzip.compress(json.dumps(payload).encode()))
            rows = validation.load_score_snapshots(pathlib.Path(tmp))
        self.assertEqual([row["sessionDate"] for row in rows], ["2026-09-09", "2026-09-10"])
        self.assertEqual(rows[1]["candidates"][0]["ticker"], "BBB")

    def test_load_score_snapshots_prefers_contemporaneous_archive_over_recovery(self):
        live = {
            "schemaVersion": "kell-score-history-v1",
            "source": {"sessionDate": "2026-09-22", "runId": "live-1"},
            "candidates": [{"ticker": "LIVE", "kell_score": 90.0, "legacy_v4_score": 70.0}],
        }
        recovered = {
            "schemaVersion": "kell-score-history-v2",
            "source": {
                "sessionDate": "2026-09-22",
                "runId": "2026-09-22-eod-123-2",
                "recovered": True,
                "recoveryReliability": "exact-pages-artifact",
                "artifactIdentityVerified": True,
                "pointInTimeCandidateMembership": True,
                "runAttempt": 2,
                "artifactId": 99,
            },
            "columns": ["ticker", "kell_score", "legacy_v4_score"],
            "candidates": [["REC", 80.0, 60.0]],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "live.json").write_text(json.dumps(live))
            (root / "recovered.json.gz").write_bytes(gzip.compress(json.dumps(recovered).encode()))
            rows = validation.load_score_snapshots(root)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["candidates"][0]["ticker"], "LIVE")
        self.assertFalse(rows[0]["source"].get("recovered", False))

    def test_load_score_snapshots_prefers_verified_exact_recovery(self):
        weak = {
            "schemaVersion": "kell-score-history-v2",
            "source": {
                "sessionDate": "2026-09-09",
                "runId": "2026-09-09-eod-123-1",
                "recovered": True,
                "pointInTimeCandidateMembership": True,
            },
            "columns": ["ticker", "kell_score", "legacy_v4_score"],
            "candidates": [["WEAK", 80.0, 60.0]],
        }
        exact = {
            "schemaVersion": "kell-score-history-v2",
            "source": {
                "sessionDate": "2026-09-09",
                "runId": "2026-09-09-eod-124-1",
                "recovered": True,
                "recoveryReliability": "exact-pages-artifact",
                "artifactIdentityVerified": True,
                "pointInTimeCandidateMembership": True,
                "artifactId": 124,
            },
            "columns": ["ticker", "kell_score", "legacy_v4_score"],
            "candidates": [["EXACT", 81.0, 61.0]],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "weak.json").write_text(json.dumps(weak))
            (root / "exact.json").write_text(json.dumps(exact))
            rows = validation.load_score_snapshots(root)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["candidates"][0]["ticker"], "EXACT")

    def test_load_score_snapshots_reads_base64_gzip_recovery(self):
        payload = {
            "schemaVersion": "kell-score-history-v2",
            "source": {
                "sessionDate": "2026-09-09",
                "runId": "2026-09-09-eod-123-1",
                "recovered": True,
                "recoveryReliability": "exact-pages-artifact",
                "artifactIdentityVerified": True,
                "pointInTimeCandidateMembership": True,
            },
            "columns": ["ticker", "kell_score", "legacy_v4_score"],
            "candidates": [["AAA", 80.0, 60.0]],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "2026-09-09.json.gz.b64"
            packed = gzip.compress(json.dumps(payload).encode())
            path.write_text(base64.b64encode(packed).decode("ascii"))
            rows = validation.load_score_snapshots(pathlib.Path(tmp))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sessionDate"], "2026-09-09")
        self.assertEqual(rows[0]["candidates"][0]["ticker"], "AAA")

    def test_load_score_snapshots_reads_json_gz(self):
        payload = {
            "schemaVersion": "kell-score-history-v2",
            "source": {"sessionDate": "2026-09-09", "runId": "r1"},
            "columns": ["ticker", "kell_score", "legacy_v4_score"],
            "candidates": [["AAA", 80.0, 60.0]],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "2026-09-09.json.gz"
            path.write_bytes(gzip.compress(json.dumps(payload).encode()))
            rows = validation.load_score_snapshots(pathlib.Path(tmp))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sessionDate"], "2026-09-09")
        self.assertEqual(rows[0]["candidates"][0]["ticker"], "AAA")

    def test_candidate_rows_reads_compact_recovered_v2(self):
        payload = {
            "schemaVersion": "kell-score-history-v2",
            "columns": ["ticker", "kell_score", "legacy_v4_score", "stage"],
            "candidates": [
                ["AAA", 82.5, 61.0, "ema_crossback"],
                ["BBB", 44.0, 55.0, "transition"],
            ],
        }
        rows = validation._candidate_rows(payload)
        self.assertEqual(rows[0]["ticker"], "AAA")
        self.assertEqual(rows[0]["kell_score"], 82.5)
        self.assertEqual(rows[1]["legacy_v4_score"], 55.0)

    def test_load_chart_store_from_shards(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "shard-000.json"
            path.write_text(json.dumps({
                "charts": {
                    "AAA": {"daily": bars(count=50), "weekly": []},
                }
            }))
            store = validation.load_chart_store(pathlib.Path(tmp))
            self.assertIn("AAA", store)
            self.assertGreater(len(store["AAA"]), 20)


if __name__ == "__main__":
    unittest.main()
