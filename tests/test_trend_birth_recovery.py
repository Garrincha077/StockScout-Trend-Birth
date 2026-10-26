import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import build_review_snapshot as builder
import recover_trend_birth_eod as recovery
import compare_trend_birth_recovery as comparison
from trend_birth_stage_forward import _events, _mature, report


class Artifact:
    def __init__(self, files):
        self.files = files
    def bytes(self, path):
        return self.files[path]


def fixture():
    day = '2026-10-15'
    run = day + '-eod-38825335004-1'
    files, mode_defs = {}, {}
    for mode in builder.MODES:
        core = {'universe': [{'ticker': 'AAA', 'price': 123 if mode == 'next' else 50}],
                'chartShards': {'AAA': '000.json'}}
        core_bytes = json.dumps(core).encode()
        core_path = 'runs/' + run + '/core.json'
        manifest = {'sessionDate': day, 'runId': run, 'status': 'healthy',
                    'assets': {'core': {'path': core_path, 'sha256': hashlib.sha256(core_bytes).hexdigest()},
                               'charts': {'path': 'runs/' + run + '/charts'}}}
        raw = json.dumps(manifest).encode()
        files['data/modes/' + mode + '/manifest.json'] = raw
        files['data/modes/' + mode + '/' + core_path] = core_bytes
        files['data/modes/' + mode + '/runs/' + run + '/charts/000.json'] = json.dumps({'AAA': [[day, 90, 101, 89, 100, 1000]]}).encode()
        mode_defs[mode] = {'manifestPath': 'modes/' + mode + '/manifest.json', 'manifestSha256': hashlib.sha256(raw).hexdigest()}
    files['data/manifest.json'] = json.dumps({'sessionDate': day, 'runId': run, 'status': 'healthy', 'modes': mode_defs}).encode()
    return Artifact(files)


class RecoveryTests(unittest.TestCase):
    def test_versioned_replay_reproduces_v2_and_preserves_all_input_bytes(self):
        dates = ['2026-10-14','2026-10-15','2026-10-16','2026-10-19','2026-10-20',
                 '2026-10-21','2026-10-22','2026-10-23','2026-10-26']
        def point(day, stage):
            return {'sessionDate': day, 'runId': day+'-eod-'+str(next((r['workflowRunId'] for r in recovery.SOURCES if r['sessionDate']==day),1))+'-1',
                    'stages': {'AAA': [stage, 0]}, 'unavailable': [], 'unavailableCount': 0,
                    'evaluatedCount': 1, 'counts': {str(i): int(i == stage) for i in range(5)}}
        def close(p):
            return {'sessionDate': p['sessionDate'], 'runId': p['runId'], 'expectedEvaluated': 1,
                    'priceCount': 1, 'prices': {'AAA': 100+dates.index(p['sessionDate'])}}
        observed = [point(day, 0 if day==dates[0] else 3 if day==dates[2] else 4)
                    for day in dates if day not in ('2026-10-15','2026-10-19')]
        closes = {p['sessionDate']:close(p) for p in observed}
        _, baseline = comparison.replay(observed, closes, dates, dates[-1])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stages, prices, recovered = root/'stages', root/'prices', root/'recovered'
            comparison.write(stages/'2026-10.json', {'schemaVersion':'trend-birth-ticker-month-v1',
                'month':'2026-10','scope':recovery.SCOPE,'sessions':observed})
            comparison.write(prices/'2026-10.json', {'schemaVersion':'trend-birth-close-month-v1',
                'month':'2026-10','scope':recovery.SCOPE,'sessions':list(closes.values())})
            comparison.write(root/'baseline.json', baseline)
            for day, prior, stage in [('2026-10-15','2026-10-14',2),('2026-10-19','2026-10-16',4)]:
                p = point(day, stage)
                comparison.write(recovered/(day+'.json'), {'schemaVersion':'trend-birth-recovered-input-v3',
                    'scope':recovery.SCOPE,'stagePoint':p,'closePoint':close(p),'source':{
                        'sessionDate':day,'runId':p['runId'],'originalArtifact':next(x for x in recovery.SOURCES if x['sessionDate']==day),
                        'radarSha256':recovery.RADAR_SHA256,'unifiedManifestSha256':recovery.PINNED_MANIFESTS[day],'observedByTrendBirthOnSession':False,'networkFallbacks':0,
                        'trackedMembershipExactOnRecoveredSession':False,
                        'trackedInput':{'schemaVersion':'tb-last-observed-tracked-v1','sourceRunId':{'2026-10-14':'2026-10-14-eod-38657441217-1','2026-10-16':'2026-10-16-eod-38982996258-1'}[prior],'sourceSessionDate':prior,'sourceSnapshotSha256':recovery.OBSERVED_WATCHLISTS[prior],
                                        'tickers':recovery.OBSERVED_TICKERS}}})
            protected = [stages/'2026-10.json', prices/'2026-10.json', root/'baseline.json']
            original = {p:p.read_bytes() for p in protected}
            result = comparison.compare(stages, prices, root/'baseline.json', recovered, root/'v3', 'baseline-test')
            self.assertEqual(7, result['before']['dataQuality']['archivedSessions'])
            self.assertEqual(9, result['after']['dataQuality']['archivedSessions'])
            self.assertEqual([], result['after']['dataQuality']['missingExchangeSessions'])
            self.assertFalse(result['migration']['activated'])
            self.assertTrue(result['baselineReplayMatchesPublished'])
            self.assertTrue(result['events']['added'])
            self.assertTrue(result['events']['removed'])
            for p in protected:
                self.assertEqual(original[p], p.read_bytes())
            self.assertEqual('trend-birth-ticker-month-v3', json.loads((root/'v3/stage-history/2026-10.json').read_bytes())['schemaVersion'])
            with self.assertRaisesRegex(ValueError,'new and separate'):
                comparison.compare(stages,prices,root/'baseline.json',recovered,root/'v3','baseline-test')

    def test_committed_inputs_have_pinned_provenance_and_no_future_watchlist(self):
        root = Path(__file__).parents[1]/'lab/data/recovery-v3'
        paths = sorted(root.glob('2026-*.json'))
        self.assertEqual(2, len(paths))
        for path in paths:
            value = json.loads(path.read_bytes())
            comparison.validate_recovered(value)
            for mutate in ('watchlist','artifact','manifest','price'):
                bad = copy.deepcopy(value)
                if mutate == 'watchlist':
                    bad['source']['trackedInput']['sourceSessionDate']='2026-10-26'
                elif mutate == 'artifact':
                    bad['source']['originalArtifact']['artifactDigest']='sha256:'+'0'*64
                elif mutate == 'manifest':
                    del bad['source']['unifiedManifestSha256']
                else:
                    bad['closePoint']['prices'].pop(next(iter(bad['closePoint']['prices'])))
                with self.assertRaises(ValueError):
                    comparison.validate_recovered(bad)

    def test_offline_source_merge_preserves_historical_membership_and_price_contract(self):
        artifact = fixture()
        evaluate = lambda rows: {'available': True, 'stage': 3, 'checks': {}}
        tracked = {'sourceSessionDate': '2026-10-14', 'tickers': []}
        with patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')):
            result = recovery.reconstruct(artifact, evaluate, tracked)
        self.assertEqual(result['stagePoint']['stages'], {'AAA': [3, 0]})
        self.assertEqual(result['closePoint']['prices'], {'AAA': 123})
        self.assertEqual(result['source']['networkFallbacks'], 0)
        self.assertFalse(result['source']['observedByTrendBirthOnSession'])

    def test_stale_chart_remains_unavailable_instead_of_creating_a_quote(self):
        artifact = fixture()
        for key in artifact.files:
            if key.endswith('/charts/000.json'):
                artifact.files[key] = json.dumps({'AAA': [['2026-10-14', 90, 101, 89, 100, 1000]]}).encode()
        result = recovery.reconstruct(artifact, lambda rows: self.fail('must not evaluate stale rows'),
                                      {'sourceSessionDate': '2026-10-14', 'tickers': []})
        self.assertEqual(result['stagePoint']['unavailable'], ['AAA'])
        self.assertEqual(result['closePoint']['prices'], {})

    def test_future_duplicate_and_unsorted_bars_are_rejected(self):
        for stamps in [('2026-10-16',), ('2026-10-15', '2026-10-15'), ('2026-10-15', '2026-10-14')]:
            with self.assertRaises(ValueError):
                recovery.dated_rows([[stamp, 1, 2, 1, 2, 100] for stamp in stamps], '2026-10-15')

    def test_mode_manifest_tampering_and_external_fallback_are_refused(self):
        artifact = fixture()
        artifact.files['data/modes/next/manifest.json'] += b' '
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            recovery.reconstruct(artifact, lambda rows: {}, {'sourceSessionDate': '2026-10-14', 'tickers': []})
        with recovery.offline_reader(artifact):
            with self.assertRaisesRegex(ValueError, 'Network fallback refused'):
                builder._get_bytes('https://example.test/prices')

    def test_intermediate_day_rebuilds_events_and_never_reuses_old_outcomes(self):
        def point(day, stage):
            return {'sessionDate': day, 'runId': day, 'stages': {'AAA': [stage, 0]},
                    'evaluatedCount': 1, 'unavailableCount': 0,
                    'counts': {str(i): int(i == stage) for i in range(5)}, 'unavailable': []}
        old = [point('2026-10-14', 0), point('2026-10-16', 4)]
        new = [old[0], point('2026-10-15', 3), old[1]]
        old_events, new_events = _events(old), _events(new)
        self.assertEqual(old_events[0]['events'][0][:3], ['AAA', 0, 4])
        self.assertEqual(new_events[0]['events'][0][:3], ['AAA', 0, 3])
        self.assertEqual(new_events[1]['events'][0][:3], ['AAA', 3, 4])
        self.assertEqual(new_events[1]['previousSessionDate'], '2026-10-15')
        self.assertEqual(new_events[1]['events'][0][3], {})
        self.assertEqual(old_events[0]['previousSessionDate'], '2026-10-14')


if __name__ == '__main__':
    unittest.main()
