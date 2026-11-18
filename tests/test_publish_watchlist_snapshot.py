import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from publish_watchlist_snapshot import bucket, build, validate
from publish_review_snapshot import encode, write_changed


class PublishWatchlistTest(unittest.TestCase):
    def test_ticker_buckets_are_exact_idempotent_and_reject_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            run = "2026-11-17-eod-42-1"
            source = {"runId": run, "sessionDate": "2026-11-17", "unifiedManifestSha256": "a" * 64}
            tracked = {"ticker": "ZZZ", "trackedWatchlist": True, "trendBirth": {"stage": 2},
                       "chartBars": [["2026-11-17", 15, 17, 14, 16, 100]]}
            full = {"source": source, "trendBirthCandidateIndex": [{"ticker": "AAA"}, tracked]}
            raw = encode(full)
            sha = hashlib.sha256(raw).hexdigest()
            snapshot_id = run + "--" + sha
            review_path = directory / "latest.json"
            manifest_path = directory / "publication.json"
            chart_base = "data/kell-chart-runs/" + run + "--" + "b" * 64
            write_changed(review_path, raw)
            write_changed(manifest_path, encode({**source, "snapshotId": snapshot_id, "sha256": sha}))
            write_changed(directory / "kell-snapshots" / (snapshot_id + ".json"), encode({
                "source": {**source, "reviewSnapshotId": snapshot_id},
                "kellChartData": {"basePath": chart_base},
                "kellCandidates": [{"ticker": "AAA", "chartAvailable": True, "chartShard": 1}],
            }))
            write_changed(directory / chart_base.removeprefix("data/") / "shard-001.json", encode({
                "source": source, "charts": {"AAA": {"daily": []}},
            }))

            build(directory, review_path, manifest_path)
            original = manifest_path.read_bytes()
            build(directory, review_path, manifest_path)
            self.assertEqual(original, manifest_path.read_bytes())
            manifest = json.loads(original)
            self.assertEqual(manifest["watchlist"]["tickers"], 2)
            base_path = directory / manifest["watchlist"]["basePath"].removeprefix("data/")
            lookup = lambda ticker: base_path / f"{bucket(ticker):02x}.json"
            self.assertEqual(json.loads(lookup("AAA").read_bytes())["rows"]["AAA"]["chartShard"], 1)
            self.assertEqual(json.loads(lookup("ZZZ").read_bytes())["rows"]["ZZZ"]["chartBars"][0][4], 16)
            lookup("AAA").write_bytes(lookup("AAA").read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "does not match publication"):
                validate(directory, manifest)
