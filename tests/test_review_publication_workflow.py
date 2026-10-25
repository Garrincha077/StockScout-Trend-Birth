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
    def publish(self, *, stale_composite=False):
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
            shutil.copy2(ROOT / "scripts/trend_birth_quality_history.py", checkout / "scripts")

            def snapshot(day):
                source = {"sessionDate": day, "runId": day + "-eod-42-1", "unifiedManifestSha256": "a" * 64}
                return {"source": source, "trendBirthRadar": {
                    "schemaVersion": "trend-birth-radar-v1", "scope": "unified-plus-tracked-watchlist",
                    "stageCounts": {str(i): int(i == 4) for i in range(5)},
                    "evaluatedCount": 1, "unavailableCount": 0}}

            def bundle(day, score):
                latest = snapshot(day)
                write("lab/data/latest.json", latest)
                write("lab/data/history/" + day + ".json", latest)
                write("lab/data/publication.json", latest["source"])
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
            bundle("2026-10-26", 70)
            if stale_composite:
                # The inputs are fresh but an upstream generation failed to refresh Composite.
                old = json.loads(git("show", "HEAD:lab/data/trend-birth-composite-backtest.json"))
                write("lab/data/trend-birth-composite-backtest.json", old)
            result = subprocess.run(
                ["bash", "-euo", "pipefail", "-c", script.replace("/tmp/", str(scratch) + "/")],
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


if __name__ == "__main__":
    unittest.main()
