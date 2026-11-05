"""Execute the production publication step against a tiny, local Git remote."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def publication_script():
    workflow = (ROOT / ".github/workflows/unified-review-grid-lab.yml").read_text()
    step = workflow.split("      - name: Publish aligned Review + Kell data atomically\n", 1)[1]
    body = step.split("        run: |\n", 1)[1].split("      - name:", 1)[0]
    return "\n".join(line[10:] if line.startswith("          ") else line
                     for line in body.splitlines())


class ReviewPublicationWorkflowTests(unittest.TestCase):
    def publish(self, *, stale_composite=False, missing_prices=False, skipped_session=False,
                bad_source=False, low_coverage=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout, remote, scratch = root / "checkout", root / "remote.git", root / "scratch"
            checkout.mkdir()
            scratch.mkdir()

            def git(*args):
                return subprocess.run(["git", *args], cwd=checkout, check=True,
                                      text=True, capture_output=True).stdout.strip()

            def write(path, value):
                target = checkout / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(value))

            script = publication_script()
            paths = shlex.split(next(line for line in script.splitlines() if line.startswith("git add ")))[2:]
            for path in paths:
                if Path(path).suffix:
                    write(path, {})
                else:
                    write(path + "/.keep", {})
            write("lab/data/kell-chart-runs/.keep", {})
            (checkout / "scripts").mkdir()
            for name in ["trend_birth_quality_history.py", "validate_eod_publication.py",
                         "archive_trend_birth_closes.py", "trend_birth_intelligence.py",
                         "validate_unified_review_bundle.py", "outcome_quote_tracking.py"]:
                shutil.copy2(ROOT / "scripts" / name, checkout / "scripts")
            shutil.copy2(ROOT / "lab/data/exchange-sessions-v1.json", checkout / "lab/data")
            shutil.copy2(ROOT / "lab/data/trend-birth-outcome-policy.json", checkout / "lab/data")

            def snapshot(day):
                source = {"sessionDate": day, "runId": day + "-eod-42-1", "unifiedManifestSha256": "a" * 64}
                return {"source": source, "trendBirthCandidateIndex": [{"ticker": "AAA",
                    "metrics": {"price": 10}, "trendBirth": {"available": True, "stage": 4, "checks": {}}}],
                    "trendBirthRadar": {
                    "schemaVersion": "trend-birth-radar-v1", "scope": "unified-plus-tracked-watchlist",
                    "stageCounts": {str(i): int(i == 4) for i in range(5)},
                    "evaluatedCount": 1, "unavailableCount": 0}}

            def bundle(day, score):
                latest = snapshot(day)
                write("lab/data/latest.json", latest)
                write("lab/data/history/" + day + ".json", latest)
                import hashlib
                write("lab/data/publication.json", {**latest["source"],
                    "sha256": hashlib.sha256((checkout / "lab/data/latest.json").read_bytes()).hexdigest()})
                import sys
                sys.path.insert(0, str(ROOT / "scripts"))
                from trend_birth_intelligence import point_from_snapshot
                from archive_trend_birth_closes import extract
                stage = point_from_snapshot(latest)
                for folder, schema, point in [
                    ("trend-birth-ticker-history", "trend-birth-ticker-month-v1", stage),
                    ("trend-birth-price-history", "trend-birth-close-month-v1", extract(latest, stage))]:
                    target = checkout / "lab/data" / folder / (day[:7] + ".json")
                    payload = json.loads(target.read_text()) if target.exists() else {
                        "schemaVersion": schema, "scope": "unified-plus-tracked-watchlist", "month": day[:7], "sessions": []}
                    payload["sessions"].append(point)
                    write(str(target.relative_to(checkout)), payload)
                from outcome_quote_tracking import build as track, load_policy
                health = track(checkout / "lab/data/latest.json",
                    checkout / "lab/data/trend-birth-ticker-history",
                    checkout / "lab/data/trend-birth-price-history",
                    checkout / "lab/data/trend-birth-outcome-quotes",
                    load_policy(checkout / "lab/data/trend-birth-outcome-policy.json"),
                    json.loads((checkout / "lab/data/exchange-sessions-v1.json").read_text()),
                    checkout / "lab/data/trend-birth-outcome-tracking.json")
                write("lab/data/trend-birth-stage-forward.json", {"asOf": day, "exchangeSessions": [day], "outcomeTracking": health})
                write("lab/data/kell-latest.json", {"source": latest["source"]})
                write("lab/data/trend-birth-market-internals.json", {
                    "latestSessionDate": day, "latestRunId": latest["source"]["runId"]})
                write("lab/data/trend-birth-composite-backtest.json", {
                    "latestActual": {"sessionDate": day, "score": score},
                    "actualHistory": [{"sessionDate": day, "score": score}],
                    "oos": {"n": 466, "topMinusBottomPp": 0.883}})

            bundle("2026-10-23", 50)
            (checkout / "lab/data/trend-birth-quality-history.json").unlink()
            git("init", "-q", "-b", "topic")
            git("config", "user.name", "Local workflow test")
            git("config", "user.email", "workflow@example.invalid")
            git("add", ".")
            git("-c", "commit.gpgSign=false", "commit", "-qm", "baseline")
            git("init", "--bare", "-q", str(remote))
            git("remote", "add", "origin", str(remote))
            git("push", "-qu", "origin", "topic")
            baseline = git("rev-parse", "HEAD")
            bundle("2026-10-28" if skipped_session else "2026-10-26", 70)
            if bad_source:
                write("lab/data/kell-latest.json", {"source": {
                    **snapshot("2026-10-26")["source"], "runId": "different-run"}})
            if missing_prices or low_coverage:
                target = checkout / "lab/data/trend-birth-price-history/2026-10.json"
                payload = json.loads(target.read_text())
                payload["sessions"][-1]["prices"] = {}
                payload["sessions"][-1]["priceCount"] = 0
                write(str(target.relative_to(checkout)), payload)
            if low_coverage:
                import hashlib
                latest = snapshot("2026-10-26")
                latest["trendBirthCandidateIndex"][0]["metrics"]["price"] = None
                write("lab/data/latest.json", latest)
                pointer = {**latest["source"], "sha256": hashlib.sha256(
                    (checkout / "lab/data/latest.json").read_bytes()).hexdigest()}
                write("lab/data/publication.json", pointer)
            if stale_composite:
                # The inputs are fresh but an upstream generation failed to refresh Composite.
                old = json.loads(git("show", "HEAD:lab/data/trend-birth-composite-backtest.json"))
                write("lab/data/trend-birth-composite-backtest.json", old)
            result = subprocess.run(
                ["bash", "-euo", "pipefail", "-c", script.replace("/tmp/", str(scratch) + "/").replace(
                    "python scripts/validate_eod_publication.py",
                    "python scripts/validate_eod_publication.py --now " +
                    ("2026-10-29T00:00:00+00:00" if skipped_session else "2026-10-27T00:00:00+00:00"))],
                cwd=checkout, env={**os.environ, "GITHUB_REF_NAME": "topic", "GITHUB_SHA": baseline},
                text=True, capture_output=True, timeout=30)
            published = json.loads(git("show", "HEAD:lab/data/trend-birth-composite-backtest.json"))
            return result, published, git("rev-parse", "HEAD") == baseline

    def test_new_composite_survives_reset_checkout_commit_and_push(self):
        result, published, unchanged = self.publish()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(unchanged)
        self.assertEqual(published["latestActual"], {"sessionDate": "2026-10-26", "score": 70})
        self.assertEqual(published["actualHistory"][-1], published["latestActual"])
        self.assertEqual(published["oos"], {"n": 466, "topMinusBottomPp": 0.883})

    def test_stale_composite_stops_publication_before_commit(self):
        result, _published, unchanged = self.publish(stale_composite=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AssertionError", result.stderr)
        self.assertTrue(unchanged)

    def test_missing_current_quotes_stops_publication_before_commit(self):
        result, _published, unchanged = self.publish(missing_prices=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("quote archive differs", result.stderr)
        self.assertTrue(unchanged)

    def test_skipping_new_sessions_keeps_last_published_commit(self):
        result, _published, unchanged = self.publish(skipped_session=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("New EOD session gap: 2026-10-26, 2026-10-27", result.stderr)
        self.assertTrue(unchanged)

    def test_mixed_run_keeps_last_published_commit(self):
        result, _published, unchanged = self.publish(bad_source=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(unchanged)

    def test_matching_but_insufficient_price_coverage_keeps_last_commit(self):
        result, _published, unchanged = self.publish(low_coverage=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("price coverage below 99%", result.stderr)
        self.assertTrue(unchanged)


if __name__ == "__main__":
    unittest.main()
