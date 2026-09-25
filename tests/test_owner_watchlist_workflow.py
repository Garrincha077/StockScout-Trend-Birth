from pathlib import Path
import unittest


class OwnerWatchlistWorkflowTests(unittest.TestCase):
    def test_lab_workflow_uses_oidc_only_on_real_lab_branch(self):
        path = Path(__file__).parents[1] / ".github" / "workflows" / "unified-review-grid-lab.yml"
        source = path.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: write\n  id-token: write", source)
        self.assertIn("- name: Sync owner watchlist into Trend Birth tracked input", source)
        self.assertIn("github.event_name != 'pull_request'", source)
        self.assertIn("refs/heads/feature/unified-review-grid-lab", source)
        self.assertIn("python scripts/sync_owner_watchlist.py", source)


if __name__ == "__main__":
    unittest.main()
