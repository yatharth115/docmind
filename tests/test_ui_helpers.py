import pytest
import requests

from ui import api_client as api
from ui.helpers import location, safe_markdown, source_label, status_text


class FakeResp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_safe_markdown_escapes_dollar_signs():
    assert safe_markdown("US$ 13 million and US$ 37 million") == "US\\$ 13 million and US\\$ 37 million"
    assert safe_markdown("") == ""


def test_location_prefers_page_then_section():
    assert location({"page": 4, "section": None}) == "page 4"
    assert location({"page": None, "section": "Intro"}) == "section Intro"
    assert location({"page": None, "section": None}) == "unknown location"


def test_source_label():
    s = {"n": 2, "filename": "a.pdf", "page": 7, "section": None}
    assert source_label(s) == "[2] a.pdf, page 7"


def test_status_text():
    assert status_text({"status": "ready"}) == "Ready"
    assert status_text({"status": "failed"}) == "Failed"
    assert status_text({"status": "processing"}) == "Processing..."


def test_api_error_uses_server_detail(monkeypatch):
    monkeypatch.setattr(api.requests, "request", lambda *a, **k: FakeResp(401, {"detail": "Wrong email or password"}))
    with pytest.raises(api.ApiError) as e:
        api.login("a@b.com", "x")
    assert e.value.status == 401 and "Wrong email" in str(e.value)


def test_validation_error_list_is_joined(monkeypatch):
    payload = {"detail": [{"msg": "String should have at least 8 characters"}, {"msg": "value is not a valid email"}]}
    monkeypatch.setattr(api.requests, "request", lambda *a, **k: FakeResp(422, payload))
    with pytest.raises(api.ApiError) as e:
        api.register("a", "b")
    assert "at least 8 characters" in str(e.value) and "valid email" in str(e.value)


def test_unreachable_api_gives_friendly_error(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(api.requests, "request", boom)
    with pytest.raises(api.ApiError) as e:
        api.list_documents("tok")
    assert "Cannot reach" in str(e.value) and e.value.status is None


def test_login_returns_token(monkeypatch):
    monkeypatch.setattr(api.requests, "request", lambda *a, **k: FakeResp(200, {"access_token": "abc"}))
    assert api.login("a@b.com", "x") == "abc"


def test_delete_with_empty_body_is_ok(monkeypatch):
    monkeypatch.setattr(api.requests, "request", lambda *a, **k: FakeResp(204, None))
    assert api.delete_document("tok", 3) is None


def test_ask_sends_none_for_empty_doc_filter(monkeypatch):
    seen = {}

    def fake(method, url, **kwargs):
        seen.update(kwargs)
        return FakeResp(200, {"answer": "x", "sources": []})

    monkeypatch.setattr(api.requests, "request", fake)
    api.ask("tok", "q?", "hybrid", 5, [])
    assert seen["json"]["doc_ids"] is None
    assert seen["headers"]["Authorization"] == "Bearer tok"