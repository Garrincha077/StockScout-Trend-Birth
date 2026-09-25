import importlib.util
import json
from pathlib import Path
import unittest

MODULE = Path(__file__).parents[1] / "scripts" / "sync_owner_watchlist.py"
spec = importlib.util.spec_from_file_location("sync_owner_watchlist", MODULE)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class OwnerWatchlistSyncTests(unittest.TestCase):
    def test_normalize_tickers_is_uppercase_deduplicated_and_safe(self):
        self.assertEqual(
            sync.normalize_tickers([" clov ", "CLOV", "BRK.B", "bad ticker", "", None]),
            ["BRK.B", "CLOV"],
        )

    def test_oidc_request_adds_expected_audience(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["auth"] = request.headers["Authorization"]
            captured["timeout"] = timeout
            return Response({"value": "jwt-token"})

        token = sync.github_oidc_token(
            "https://actions.example/token?foo=bar",
            "request-token",
            opener=opener,
        )
        self.assertEqual(token, "jwt-token")
        self.assertIn("audience=stockscout-unified-operations", captured["url"])
        self.assertIn("foo=bar", captured["url"])
        self.assertEqual(captured["auth"], "Bearer request-token")
        self.assertEqual(captured["timeout"], 30)

    def test_fetch_watchlist_accepts_only_scoped_data_payload(self):
        captured = {}

        def opener(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["auth"] = request.headers["Authorization"]
            return Response({"ok": True, "data": {"tickers": ["clov", "NVDA", "CLOV"]}})

        tickers = sync.fetch_watchlist("https://example.test/function", "jwt", opener=opener)
        self.assertEqual(tickers, ["CLOV", "NVDA"])
        self.assertEqual(captured["body"], {"action": "watchlist_tickers"})
        self.assertEqual(captured["auth"], "Bearer jwt")

    def test_write_watchlist_keeps_builder_compatible_tickers_field(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "tracked.json"
            payload = sync.write_watchlist(target, ["clov", "NVDA"])
            saved = json.loads(target.read_text())
            self.assertEqual(payload["schemaVersion"], "trend-birth-tracked-watchlist-v2")
            self.assertEqual(saved["source"], "stockscout-unified-owner-state")
            self.assertEqual(saved["tickers"], ["CLOV", "NVDA"])


if __name__ == "__main__":
    unittest.main()
