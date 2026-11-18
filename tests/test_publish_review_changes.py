import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from publish_review_changes import EARLY_MODEL, KELL_MODEL, build, strategy_feed, validate
from publish_review_snapshot import encode, write_changed

PRIOR = "2026-11-13"
TODAY = "2026-11-16"
CALENDAR = {"schemaVersion": "xnys-eod-sessions-v1", "sessions": [[PRIOR], [TODAY]]}


def ticker(symbol, day, price, early=None, kell=None):
    result = {"ticker": symbol, "trendBirth": {"available": True, "barDate": day, "metrics": {"price": price}}}
    if early:
        result["earlyTrend"] = {"model": EARLY_MODEL, "sessionDate": day, "phase": early, "invalidation": 9}
    if kell:
        result["kellSwing"] = {"model": KELL_MODEL, "sessionDate": day, "state": kell, "stop": 8,
                               "signalClose": price, "setup": "wedge_pop"}
    return result


def snapshot(day, rows, early=(), kell=(), charts=()):
    return {"source": {"sessionDate": day, "runId": f"{day}-eod-test-1", "unifiedManifestSha256": "f" * 64},
            "earlyTrendResearch": {"model": EARLY_MODEL}, "trendBirthCandidateIndex": rows,
            "unifiedCandidateIndex": rows, "candidates": list(charts),
            "shortlists": {"earlyTrendBirth": [{"ticker": name} for name in early],
                           "kellSwing": [{"ticker": name} for name in kell]}}


class PublishReviewChangesTest(unittest.TestCase):
    def test_early_joins_and_drops_use_the_full_common_scope(self):
        before = snapshot(PRIOR, [ticker("FALL", PRIOR, 10, "reclaim"), ticker("DROP", PRIOR, 10, "reclaim"),
                                  ticker("NEW", PRIOR, 10), ticker("GONE", PRIOR, 10, "reclaim")],
                          early=["FALL", "DROP", "GONE"])
        after = snapshot(TODAY, [ticker("FALL", TODAY, 8), ticker("DROP", TODAY, 10, "reclaim"),
                                 ticker("NEW", TODAY, 11, "reclaim"), ticker("UNSEEN", TODAY, 11, "reclaim")],
                         early=["NEW", "UNSEEN"], charts=[{"ticker": "FALL", "chartBars": [[PRIOR, 10, 11, 9, 10]]}])
        feed = strategy_feed(after, before, "early")
        self.assertEqual(feed["compared"], 3)
        self.assertEqual([(row["ticker"], row["kind"]) for row in feed["events"]],
                         [("FALL", "level_broken"), ("NEW", "appeared"), ("DROP", "left_list")])
        self.assertEqual(feed["events"][0]["priorLevel"], 9)
        self.assertFalse(feed["events"][0]["after"]["listed"])

    def test_rebased_archive_does_not_imply_a_broken_prior_level(self):
        before = snapshot(PRIOR, [ticker("SPLT", PRIOR, 10, "reclaim")])
        after = snapshot(TODAY, [ticker("SPLT", TODAY, 8)],
                         charts=[{"ticker": "SPLT", "chartBars": [[PRIOR, 5, 6, 4, 5]]}])
        row, = strategy_feed(after, before, "early")["events"]
        self.assertEqual(row["kind"], "lost")
        self.assertIsNone(row["priorLevel"])

    def test_kell_uses_its_own_transition_and_rejects_stale_plans(self):
        before = snapshot(PRIOR, [ticker("XYZ", PRIOR, 10, kell="watch")])
        after = snapshot(TODAY, [ticker("XYZ", TODAY, 11, kell="triggered")], kell=["XYZ"])
        row, = strategy_feed(after, before, "kell")["events"]
        self.assertEqual((row["kind"], row["before"]["state"], row["after"]["state"]),
                         ("triggered", "watch", "triggered"))
        after["unifiedCandidateIndex"][0]["kellSwing"]["sessionDate"] = PRIOR
        with self.assertRaisesRegex(ValueError, "plan provenance"):
            strategy_feed(after, before, "kell")

    def test_old_archive_preserves_today_list_and_never_labels_a_change(self):
        before = snapshot(PRIOR, [ticker("XYZ", PRIOR, 10)])
        del before["earlyTrendResearch"]
        del before["shortlists"]["kellSwing"]
        after = snapshot(TODAY, [ticker("XYZ", TODAY, 11, "reclaim", "watch")], early=["XYZ"], kell=["XYZ"])
        for strategy in ("early", "kell"):
            feed = strategy_feed(after, before, strategy)
            self.assertEqual((feed["status"], feed["events"]), ("no_baseline", []))
            self.assertEqual(feed["current"][0]["ticker"], "XYZ")

    def test_artifact_is_content_addressed_and_binds_to_the_exact_prior_session(self):
        with TemporaryDirectory() as work:
            directory = Path(work)
            today = snapshot(TODAY, [ticker("A", TODAY, 11, "confirmed")], early=["A"])
            prior = snapshot(PRIOR, [ticker("A", PRIOR, 10, "reclaim")], early=["A"])
            raw = encode(today)
            digest = hashlib.sha256(raw).hexdigest()
            sid = today["source"]["runId"] + "--" + digest
            path = f"snapshots/{sid}.json"
            write_changed(directory / path, raw)
            write_changed(directory / "history" / f"{PRIOR}.json", encode(prior))
            pointer = directory / "publication.json"
            write_changed(pointer, encode({**today["source"], "snapshotId": sid, "sha256": digest,
                                           "snapshotPath": "data/" + path}))
            result = build(directory, CALENDAR)
            self.assertEqual(result["previousSession"], PRIOR)
            self.assertEqual(result["strategies"]["early"]["events"][0]["kind"], "advanced")
            original = pointer.read_bytes()
            build(directory, CALENDAR)
            self.assertEqual(pointer.read_bytes(), original)
            manifest = json.loads(original)
            artifact = directory / manifest["changes"]["path"].removeprefix("data/")
            artifact.write_bytes(artifact.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "differs from active"):
                validate(directory, manifest, CALENDAR)
