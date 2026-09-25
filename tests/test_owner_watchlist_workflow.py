from pathlib import Path
import unittest
import yaml


class OwnerWatchlistWorkflowTests(unittest.TestCase):
    def test_lab_workflow_uses_oidc_only_on_real_lab_branch(self):
        path = Path(__file__).parents[1] / ".github" / "workflows" / "unified-review-grid-lab.yml"
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(workflow["permissions"]["id-token"], "write")
        steps = workflow["jobs"]["build"]["steps"]
        sync = next(step for step in steps if step.get("name") == "Sync owner watchlist into Trend Birth tracked input")
        self.assertIn("github.event_name != 'pull_request'", sync["if"])
        self.assertIn("refs/heads/feature/unified-review-grid-lab", sync["if"])
        self.assertIn("scripts/sync_owner_watchlist.py", sync["run"])


if __name__ == "__main__":
    unittest.main()
