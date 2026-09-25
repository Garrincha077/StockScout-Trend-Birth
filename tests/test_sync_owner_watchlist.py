import importlib.util
import json
from pathlib import Path

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


def test_normalize_tickers_is_uppercase_deduplicated_and_safe():
    assert sync.normalize_tickers([" clov ", "CLOV", "BRK.B", "bad ticker", "", None]) == [
        "BRK.B",
        "CLOV",
    ]


def test_oidc_request_adds_expected_audience():
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
    assert token == "jwt-token"
    assert "audience=stockscout-unified-operations" in captured["url"]
    assert "foo=bar" in captured["url"]
    assert captured["auth"] == "Bearer request-token"
    assert captured["timeout"] == 30


def test_fetch_watchlist_accepts_only_scoped_data_payload():
    captured = {}
    def opener(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["auth"] = request.headers["Authorization"]
        return Response({"ok": True, "data": {"tickers": ["clov", "NVDA", "CLOV"]}})

    tickers = sync.fetch_watchlist("https://example.test/function", "jwt", opener=opener)
    assert tickers == ["CLOV", "NVDA"]
    assert captured["body"] == {"action": "watchlist_tickers"}
    assert captured["auth"] == "Bearer jwt"


def test_write_watchlist_keeps_builder_compatible_tickers_field(tmp_path):
    target = tmp_path / "tracked.json"
    payload = sync.write_watchlist(target, ["clov", "NVDA"])
    saved = json.loads(target.read_text())
    assert payload["schemaVersion"] == "trend-birth-tracked-watchlist-v2"
    assert saved["source"] == "stockscout-unified-owner-state"
    assert saved["tickers"] == ["CLOV", "NVDA"]
