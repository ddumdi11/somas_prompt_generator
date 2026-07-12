"""Teil A (v0.12.3): Perplexity-Such-Tiefe `search_context_size`.

Inhaltliche Calls (`send_prompt`) müssen `web_search_options.search_context_size`
auf "high" setzen (Default wäre "low" = oberflächlichste Stufe). Der reine
Verbindungstest (`validate_key`) bleibt bewusst ohne den Parameter.

Lauf (ohne pytest):  python tests/test_perplexity_search_context.py
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.api_client import APIStatus
from src.core.perplexity_client import PerplexityClient


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = ""

    def json(self):
        return self._payload


def _capture_post(payload=None, status_code=200):
    """Patcht requests.post und gibt (captured_kwargs, response) zurück."""
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Resp(status_code, payload)

    return captured, fake_post


def test_content_call_sets_search_context_high():
    payload = {"choices": [{"message": {"content": "Antwort"}}],
               "usage": {"total_tokens": 3}}
    captured, fake_post = _capture_post(payload)
    with patch("src.core.perplexity_client.requests.post", side_effect=fake_post):
        r = PerplexityClient("dummy-key").send_prompt("prompt", "sonar-pro")
    assert r.status == APIStatus.RECEIVED, r.error_message
    assert captured["json"].get("web_search_options") == {
        "search_context_size": "high"
    }, captured["json"]
    print("  content_call_sets_search_context_high: web_search_options=high OK")


def test_search_context_size_is_configurable():
    """Das Attribut steuert den Payload (programmatisch überschreibbar)."""
    payload = {"choices": [{"message": {"content": "Antwort"}}]}
    captured, fake_post = _capture_post(payload)
    client = PerplexityClient("dummy-key")
    client._search_context_size = "medium"
    with patch("src.core.perplexity_client.requests.post", side_effect=fake_post):
        client.send_prompt("prompt", "sonar")
    assert captured["json"]["web_search_options"]["search_context_size"] == "medium"
    print("  search_context_size_is_configurable: Attribut steuert Payload OK")


def test_validate_key_has_no_search_context():
    """Verbindungstest bleibt schlank (kein web_search_options, 'low' genügt)."""
    captured, fake_post = _capture_post(status_code=200)
    with patch("src.core.perplexity_client.requests.post", side_effect=fake_post):
        ok = PerplexityClient("dummy-key").validate_key()
    assert ok is True
    assert "web_search_options" not in captured["json"], captured["json"]
    print("  validate_key_has_no_search_context: Verbindungstest ohne Such-Tiefe OK")


def main():
    print("Perplexity Such-Tiefe (Teil A):")
    test_content_call_sets_search_context_high()
    test_search_context_size_is_configurable()
    test_validate_key_has_no_search_context()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
