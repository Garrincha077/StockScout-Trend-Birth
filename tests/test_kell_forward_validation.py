import importlib.util
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

    def test_immature_horizon_is_excluded(self):
        series = [validation._normalize_bar(row) for row in bars(count=40)]
        series = [row for row in series if row is not None]
        session = series[-10]["date"]
        out = validation._outcome(series, session, 20)
        self.assertIsNone(out)

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
