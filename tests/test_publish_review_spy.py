import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from market_sessions import CALENDAR_PATH, exchange_sessions
from publish_review_snapshot import encode, write_changed
from publish_review_spy import infer_points, publish, validate

DAY = "2026-11-17"
SOURCE = {"runId": DAY + "-eod-42-1", "sessionDate": DAY, "unifiedManifestSha256": "a" * 64}


def row(day, spy):
    return [day, 20, 21, 19, 20, 100, 2000 / spy]


class PublishReviewSpyTest(unittest.TestCase):
    def test_consensus_deduplicates_tickers_and_skips_outliers_closed_days_and_future(self):
        old = "2024-11-15"
        observations = [
            {"ticker": f"T{index}", "chartBars": [row(day, price) for day, price in (
                (old, 500), ("2024-11-16", 500), ("2025-01-01", 500),
                ("2026-11-13", 400 if index < 4 else 800),
                (DAY, 600 if index < 5 else 800), ("2026-11-18", 610)
            )]} for index in range(6)
        ]
        single = {"ticker": "DUPLICATE", "chartBars": [row("2026-11-16", 590)]}
        snapshot = {"source": SOURCE, "candidates": observations + [single] * 6, "kellCandidates": [single]}
        self.assertEqual(infer_points(snapshot, exchange_sessions(DAY), "2025-01-01"),
                         [[old, 500, 6, 6], [DAY, 600, 5, 6]])

    def test_artifact_is_bound_to_exact_activation_and_gives_idempotent_pointer(self):
        with TemporaryDirectory() as work:
            directory = Path(work)
            snapshot = {"source": SOURCE, "candidates":
                        [{"ticker": f"S{index}", "chartBars": [row(DAY, 610)]} for index in range(5)]}
            content = encode(snapshot)
            digest = hashlib.sha256(content).hexdigest()
            sid = SOURCE["runId"] + "--" + digest
            snapshot_path = f"snapshots/{sid}.json"
            write_changed(directory / snapshot_path, content)
            pointer = directory / "publication.json"
            write_changed(pointer, encode({**SOURCE, "snapshotId": sid, "sha256": digest,
                                           "snapshotPath": "data/" + snapshot_path}))
            artifact = publish(directory, CALENDAR_PATH)
            self.assertEqual(artifact["points"], [[DAY, 610, 5, 5]])
            expected = pointer.read_bytes()
            publish(directory, CALENDAR_PATH)
            self.assertEqual(pointer.read_bytes(), expected)
            manifest = json.loads(expected)
            path = directory / manifest["spyReference"]["path"].removeprefix("data/")
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "does not match"):
                validate(directory, manifest, CALENDAR_PATH)
