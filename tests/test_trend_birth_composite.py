"""Offline regression checks for an explicitly exploratory ETF-proxy composite."""
import unittest

from scripts import backtest_market_internals as bt


class CompositeMarketInternalsTests(unittest.TestCase):
    def test_no_same_close_fill_and_only_complete_forward_label(self):
        prices = [float(100+i) for i in range(45)]
        self.assertAlmostEqual(bt.forward_label(prices, 0), (prices[21]/prices[1]-1)*100)
        self.assertIsNone(bt.forward_label(prices, 25))

    def test_percentile_uses_only_older_values_and_midrank_ties(self):
        self.assertEqual(bt.percent_rank(8, [2]*13),100)
        self.assertEqual(bt.percent_rank(2, [2]*13),50)
        self.assertEqual(bt.percent_rank(2, [5]*13),0)
        self.assertEqual(bt.percent_rank(8, [2]*3),50)  # insufficient baseline

    def test_score_bounds_and_frozen_profile(self):
        point = {field+'Rank':value for field,value in zip(bt.FIELDS,[0,20,40,60,80,100])}
        for profile in bt.PROFILES:
            score=bt.profile_score(point,profile)
            self.assertGreaterEqual(score,0)
            self.assertLessEqual(score,100)
        self.assertEqual(bt.choose_profile([])[0], "balanced")

    def test_actual_score_refresh_does_not_download_prices(self):
        points=[{"sessionDate":"2026-09-%02d" % (i+1) if i<30 else "2026-10-01",
                 "qualityBreadthPct":float(i),"pressurePct":float(i),
                 "matchedQualityDeltaPp":0.5} for i in range(20)]
        actual={"latestSessionDate":points[-1]["sessionDate"],"points":points}
        report={"schemaVersion":bt.SCHEMA,"calibration":{"selectedProfile":"recovery"}}
        result=bt.refresh_actual(report,actual)
        self.assertEqual(result["latestActual"]["actualHistoryCount"],20)
        self.assertEqual(result["latestActual"]["sessionDate"],actual["latestSessionDate"])
        self.assertTrue(0<=result["latestActual"]["score"]<=100)

    def test_historical_source_rejects_truncated_data(self):
        with self.assertRaises(ValueError):
            bt.load_prices("Date,SPY,XLE\n2008-10-01,100,50\n")

    def test_hierarchical_approximation_is_bounded(self):
        from datetime import date, timedelta
        days=[date(2017,1,1)+timedelta(days=i) for i in range(250)]
        prices=[100+i*0.13+(i%11)*0.08 for i in range(250)]
        stages=bt.stage_history(days,prices)
        self.assertEqual(len(stages),len(days))
        self.assertTrue(all(v is None or (isinstance(v,int) and 0<=v<=4) for v in stages))


if __name__ == "__main__":
    unittest.main()
