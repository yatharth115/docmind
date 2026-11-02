import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import ask, auth, config_info, documents, search
from app.core.config import settings
from app.services.ratelimit import RateLimiter


def test_limiter_blocks_after_limit():
    lim = RateLimiter(2, window_seconds=60)
    assert lim.allow("a", now=0) and lim.allow("a", now=1)
    assert lim.allow("a", now=2) is False


def test_limiter_window_expires():
    lim = RateLimiter(1, window_seconds=60)
    assert lim.allow("a", now=0)
    assert lim.allow("a", now=30) is False
    assert lim.allow("a", now=61)


def test_limiter_keys_are_independent():
    lim = RateLimiter(1, window_seconds=60)
    assert lim.allow("a", now=0)
    assert lim.allow("b", now=0)


def test_limiter_zero_means_unlimited():
    lim = RateLimiter(0)
    assert all(lim.allow("a", now=i) for i in range(100))


def test_config_endpoint_reflects_settings(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_RERANK", False)
    monkeypatch.setattr(settings, "ALLOW_REGISTRATION", False)
    monkeypatch.setattr(settings, "READ_ONLY_DOCS", True)
    assert config_info.public_config() == {
        "rerank_enabled": False,
        "registration_enabled": False,
        "read_only": True,
    }


def test_register_blocked_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_REGISTRATION", False)
    with pytest.raises(HTTPException) as e:
        auth.register(auth.RegisterIn(email="a@b.com", password="secret123"), db=None)
    assert e.value.status_code == 403


def test_upload_and_delete_blocked_when_read_only(monkeypatch):
    monkeypatch.setattr(settings, "READ_ONLY_DOCS", True)
    with pytest.raises(HTTPException) as e1:
        asyncio.run(documents.upload_document(background=None, file=None, db=None, user=None))
    assert e1.value.status_code == 403
    with pytest.raises(HTTPException) as e2:
        documents.delete_document(1, db=None, user=None)
    assert e2.value.status_code == 403


def test_rerank_blocked_in_ask_and_search(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_RERANK", False)
    user = SimpleNamespace(id=1)
    with pytest.raises(HTTPException) as e1:
        ask.ask(ask.AskIn(question="hello there", mode="hybrid_rerank"), db=None, user=user)
    assert e1.value.status_code == 400
    with pytest.raises(HTTPException) as e2:
        search.search(search.SearchIn(query="hello there", mode="hybrid_rerank"), db=None, user=user)
    assert e2.value.status_code == 400


def test_ask_is_rate_limited_per_user(monkeypatch):
    monkeypatch.setattr(ask, "user_limiter", RateLimiter(1))
    monkeypatch.setattr(ask, "global_limiter", RateLimiter(100))
    monkeypatch.setattr(ask, "answer_question", lambda *a, **k: {"answer": "ok"})
    user = SimpleNamespace(id=7)
    data = ask.AskIn(question="hello there", mode="vector")
    assert ask.ask(data, db=None, user=user) == {"answer": "ok"}
    with pytest.raises(HTTPException) as e:
        ask.ask(data, db=None, user=user)
    assert e.value.status_code == 429


def test_ask_global_limit_applies_across_users(monkeypatch):
    monkeypatch.setattr(ask, "user_limiter", RateLimiter(100))
    monkeypatch.setattr(ask, "global_limiter", RateLimiter(1))
    monkeypatch.setattr(ask, "answer_question", lambda *a, **k: {"answer": "ok"})
    data = ask.AskIn(question="hello there", mode="vector")
    ask.ask(data, db=None, user=SimpleNamespace(id=1))
    with pytest.raises(HTTPException) as e:
        ask.ask(data, db=None, user=SimpleNamespace(id=2))
    assert e.value.status_code == 429


def test_defaults_keep_everything_on():
    from app.core.config import Settings
    s = Settings(DATABASE_URL="postgresql+psycopg2://u:p@h/d", SECRET_KEY="x", _env_file=None)
    assert s.ENABLE_RERANK and s.ALLOW_REGISTRATION and not s.READ_ONLY_DOCS