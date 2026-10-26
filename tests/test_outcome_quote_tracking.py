import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import outcome_quote_tracking as tracking
import trend_birth_stage_forward as forward

CALENDAR = json.loads((Path(__file__).resolve().parents[1] / "lab/data/exchange-sessions-v1.json").read_text())
DATES = [day for day, close in CALENDAR["sessions"] if day >= "2026-06-01"][:90]
POLICY = {"schemaVersion": "trend-birth-outcome-policy-v1", "startAfterSessionDate": DATES[0],
          "maxHorizon": 60, "provider": "yahoo-chart-v8"}


def source(day):
    return {"sessionDate": day, "runId": "run-" + day, "unifiedManifestSha256": "a" * 64}


def payload(ticker, day, value):
    close = datetime.fromisoformat(dict(CALENDAR["sessions"])[day])
    return {"chart": {"result": [{"meta": {"symbol": ticker, "currency": "USD",
        "exchangeTimezoneName": "America/New_York", "regularMarketTime": close.timestamp()-1,
        "regularMarketPrice": value}, "timestamp": [close.timestamp()-3600],
        "indicators": {"quote": [{"close": [value]}]}}]}}


def quote_record(ticker, day, close, now):
    return tracking.parse_quote(payload(ticker, day, 100 + DATES.index(day)), ticker,
                                day, close, now, "query1.finance.yahoo.com")


def fixture(root, last):
    stages, prices = root / "stages", root / "prices"
    stages.mkdir(exist_ok=True); prices.mkdir(exist_ok=True)
    grouped_stages, grouped_prices = {}, {}
    points = []
    for i, day in enumerate(DATES[:last+1]):
        values = {"AAPL": [0, 0]}
        closes = {"AAPL": 100+i}
        if i < 3:
            values["AAA"] = [0 if i == 0 else 3, 0]
            closes["AAA"] = 100+i
        counts = {str(stage): sum(v[0] == stage for v in values.values()) for stage in range(5)}
        point = {"sessionDate": day, "runId": source(day)["runId"], "stages": values,
                 "counts": counts, "evaluatedCount": len(values), "unavailable": [], "unavailableCount": 0}
        points.append(point)
        grouped_stages.setdefault(day[:7], []).append(point)
        grouped_prices.setdefault(day[:7], []).append({"sessionDate": day, "runId": source(day)["runId"],
            "expectedEvaluated": len(values), "priceCount": len(closes), "prices": closes})
    for folder, grouped, schema in [(stages, grouped_stages, "trend-birth-ticker-month-v1"),
                                     (prices, grouped_prices, "trend-birth-close-month-v1")]:
        for month, sessions in grouped.items():
            (folder/(month+".json")).write_text(json.dumps({"schemaVersion": schema,
                "scope": forward.SCOPE, "month": month, "sessions": sessions}))
    latest = root / "latest.json"
    chart_days = [day for day, close in CALENDAR['sessions'] if day < DATES[0]][-3:] + DATES[:last+1]
    latest.write_text(json.dumps({"source": source(DATES[last]), "trendBirthCandidateIndex": [
        {"ticker": "AAPL", "chartBars": [{"time": day, "close": 100+i}
                                          for i, day in enumerate(chart_days)]}]}))
    return latest, stages, prices, points


class OutcomeTrackingTests(unittest.TestCase):
    def test_dropped_ticker_kept_through_exact_60d_exit_then_retires(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, points = fixture(Path(tmp), 63)
            self.assertEqual(tracking.active_tickers(points[:63], CALENDAR, DATES[62]), ["AAA"])
            self.assertEqual(tracking.active_tickers(points, CALENDAR, DATES[63]), [])

    def test_provider_rejects_live_intraday_stale_future_or_wrong_symbol_quotes(self):
        day = DATES[7]; close = dict(CALENDAR["sessions"])[day]
        after = datetime.fromisoformat(close)+timedelta(minutes=10)
        self.assertIsNotNone(tracking.parse_quote(payload("AAA", day, 12), "AAA", day, close, after,
                                                "query1.finance.yahoo.com")[0])
        self.assertIsNone(tracking.parse_quote(payload("AAA", day, 12), "AAA", day, close,
                                               after-timedelta(hours=1), "query1.finance.yahoo.com")[0])
        for mutate in [lambda p:p['chart']['result'][0]['meta'].update(symbol='BBB'),
                       lambda p:p['chart']['result'][0]['meta'].update(regularMarketTime=after.timestamp()+1),
                       lambda p:p['chart']['result'][0]['meta'].update(regularMarketPrice=True),
                       lambda p:p['chart']['result'][0]['meta'].update(currency='EUR'),
                       lambda p:p['chart']['result'][0]['meta'].update(regularMarketTime=after.timestamp()-86400),
                       lambda p:p['chart']['result'][0]['indicators']['quote'][0].update(close=[99])]:
            p=payload('AAA',day,12); mutate(p)
            self.assertIsNone(tracking.parse_quote(p,'AAA',day,close,after,'query1.finance.yahoo.com')[0])
        with patch.object(tracking.urllib.request, 'urlopen', side_effect=AssertionError('must not fetch old history')):
            self.assertEqual(tracking.fetch_quote('AAA',day,close,after+timedelta(days=1))[1],
                             'outside_same_market_day_capture_window')

    def test_cutoff_makes_no_historical_provider_calls_or_archive_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); latest, stages, prices, _=fixture(root,7)
            policy={**POLICY, 'startAfterSessionDate':DATES[7]}
            original={p.name:p.read_bytes() for p in prices.glob('*.json')}
            value=tracking.build(latest,stages,prices,root/'extra',policy,CALENDAR,root/'health.json',
                fetcher=lambda *args: self.fail('historical fetch'))
            self.assertFalse(value['enabled']); self.assertFalse((root/'extra').exists())
            self.assertEqual(original,{p.name:p.read_bytes() for p in prices.glob('*.json')})

    def test_retry_adds_observation_without_overwriting_original_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); latest, stages, prices, _=fixture(root,7)
            close=dict(CALENDAR['sessions'])[DATES[7]]; now=datetime.fromisoformat(close)+timedelta(minutes=20)
            directory=root/'extra'; output=root/'health.json'
            failed=tracking.build(latest,stages,prices,directory,POLICY,CALENDAR,output,now,
                                  fetcher=lambda *args:(None,'provider_request_failed'))
            self.assertEqual(failed['missingCount'],1)
            first=next(directory.glob('*.json')); original=first.read_bytes()
            ready=tracking.build(latest,stages,prices,directory,POLICY,CALENDAR,output,now,quote_record)
            self.assertEqual((ready['supplementalCount'],ready['missingCount']),(1,0))
            self.assertEqual(first.read_bytes(),original); self.assertEqual(len(list(directory.glob('*.json'))),2)
            tracking.build(latest,stages,prices,directory,POLICY,CALENDAR,output,now,
                           fetcher=lambda *args:self.fail('re-fetches recorded close'))
            self.assertEqual(len(list(directory.glob('*.json'))),2)
            current=next(p for p in directory.glob('*.json') if p!=first)
            wrong=json.loads(current.read_text());wrong['prices']['AAA']=0
            current.write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError,'content-address'):
                tracking.load_observations(directory,tracking.load_prices(prices),POLICY,CALENDAR)

    def test_forward_returns_mature_after_ticker_exits_universe_with_primary_bytes_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); directory=root/'extra'; output=root/'health.json'
            for last in [7,22,62]:
                latest,stages,prices,_=fixture(root,last)
                original={p.name:p.read_bytes() for p in prices.glob('*.json')}
                close=dict(CALENDAR['sessions'])[DATES[last]]
                health=tracking.build(latest,stages,prices,directory,POLICY,CALENDAR,output,
                    datetime.fromisoformat(close)+timedelta(minutes=20),quote_record)
                self.assertEqual(original,{p.name:p.read_bytes() for p in prices.glob('*.json')})
            forward.build(latest,stages,prices,root/'outcomes',root/'report.json',
                          directory,POLICY,CALENDAR,health)
            report=json.loads((root/'report.json').read_text())
            self.assertEqual(report['stageTransitions'],1)
            self.assertEqual(report['dataQuality']['sourcePriceCoveragePct'],100)
            for horizon in [5,20,60]:
                row=report['byHorizon'][str(horizon)]['3']
                self.assertEqual((row['n'],row['missingMatured']),(1,0))
                self.assertAlmostEqual(row['meanPct'],round(((102+horizon)/102-1)*100,3))
            self.assertEqual(report['outcomeTracking']['supplementalCount'],1)

    def test_missing_provider_quote_stays_explicit_and_health_cannot_be_falsified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); latest,stages,prices,points=fixture(root,7)
            close=dict(CALENDAR['sessions'])[DATES[7]]
            health=tracking.build(latest,stages,prices,root/'extra',POLICY,CALENDAR,root/'health.json',
                datetime.fromisoformat(close)+timedelta(minutes=20),lambda *args:(None,'provider_no_result'))
            forward.build(latest,stages,prices,root/'outcomes',root/'report.json',root/'extra',POLICY,CALENDAR,health)
            row=json.loads((root/'report.json').read_text())['byHorizon']['5']['3']
            self.assertEqual((row['n'],row['missingTickerQuote']),(0,1));self.assertIsNone(row['meanPct'])
            health['missingCount']=0
            with self.assertRaisesRegex(ValueError,'health mismatch'):
                tracking.validate_health(health,source(DATES[7]),POLICY,points,
                    tracking.load_prices(prices),tracking.load_observations(root/'extra',tracking.load_prices(prices),POLICY,CALENDAR),CALENDAR)


if __name__ == '__main__':
    unittest.main()
