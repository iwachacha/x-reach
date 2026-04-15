# -*- coding: utf-8 -*-
"""Tests for the X Reach SDK surface."""

from agent_reach.config import Config
from agent_reach.results import build_result
from x_reach import XReach, XReachClient


class _StubAdapter:
    channel = "twitter"

    def __init__(self, config=None):
        self.config = config

    def supported_operations(self):
        return ("search", "hashtag", "user_posts")

    def search(self, value, limit=None, since=None, until=None, **kwargs):
        return build_result(
            ok=True,
            channel="twitter",
            operation="search",
            items=[
                {
                    "id": value,
                    "kind": "post",
                    "title": value,
                    "url": "https://x.com/openai/status/1",
                    "text": None,
                    "author": "openai",
                    "published_at": None,
                    "source": "twitter",
                    "extras": {},
                }
            ],
            raw={
                "value": value,
                "limit": limit,
                "since": since,
                "until": until,
                **kwargs,
            },
            meta={"input": value},
            error=None,
        )

    def hashtag(self, value, limit=None, **kwargs):
        return self.search(value, limit=limit, **kwargs)

    def user_posts(self, value, limit=None, originals_only=None, **kwargs):
        return build_result(
            ok=True,
            channel="twitter",
            operation="user_posts",
            items=[],
            raw={
                "value": value,
                "limit": limit,
                "originals_only": originals_only,
                **kwargs,
            },
            meta={"input": value},
            error=None,
        )


def test_x_reach_surface_exposes_twitter_namespace(tmp_path, monkeypatch):
    config = Config(config_path=tmp_path / "config.yaml")
    monkeypatch.setattr("x_reach.client.get_adapter", lambda channel, config=None: _StubAdapter(config=config))

    client = XReachClient(config=config)
    renamed = XReach(config=config)

    assert isinstance(renamed, XReachClient)
    assert client.twitter._channel == "twitter"
    assert client.twitter.search("OpenAI")["ok"] is True
    assert client.twitter.hashtag("OpenAI")["ok"] is True


def test_collect_rejects_blank_input(tmp_path):
    client = XReachClient(config=Config(config_path=tmp_path / "config.yaml"))
    payload = client.collect("twitter", "search", "   ")
    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_input"


def test_collect_rejects_invalid_limit(tmp_path):
    client = XReachClient(config=Config(config_path=tmp_path / "config.yaml"))
    payload = client.collect("twitter", "search", "OpenAI", limit=0)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_input"


def test_collect_reports_unsupported_operation(tmp_path, monkeypatch):
    config = Config(config_path=tmp_path / "config.yaml")
    monkeypatch.setattr("x_reach.client.get_adapter", lambda channel, config=None: _StubAdapter(config=config))
    client = XReachClient(config=config)

    payload = client.collect("twitter", "user", "openai")

    assert payload["ok"] is False
    assert payload["error"]["code"] == "unsupported_operation"
    assert payload["meta"]["supported_operations"] == ["search", "hashtag", "user_posts"]


def test_collect_reports_unknown_channel(tmp_path, monkeypatch):
    config = Config(config_path=tmp_path / "config.yaml")
    monkeypatch.setattr("x_reach.client.get_adapter", lambda channel, config=None: None)
    client = XReachClient(config=config)

    payload = client.collect("missing", "search", "value")

    assert payload["ok"] is False
    assert payload["error"]["code"] == "unknown_channel"


def test_collect_passes_twitter_since_until_from_contract(tmp_path, monkeypatch):
    config = Config(config_path=tmp_path / "config.yaml")
    monkeypatch.setattr("x_reach.client.get_adapter", lambda channel, config=None: _StubAdapter(config=config))
    client = XReachClient(config=config)

    payload = client.collect("twitter", "search", "OpenAI", since="2026-01-01", until="2026-12-31")

    assert payload["ok"] is True
    assert payload["raw"] == {"value": "OpenAI", "limit": None, "since": "2026-01-01", "until": "2026-12-31"}


def test_collect_passes_formalized_search_filters(tmp_path, monkeypatch):
    config = Config(config_path=tmp_path / "config.yaml")
    monkeypatch.setattr("x_reach.client.get_adapter", lambda channel, config=None: _StubAdapter(config=config))
    client = XReachClient(config=config)

    payload = client.collect(
        "twitter",
        "search",
        "OpenAI",
        from_user="OpenAI",
        search_type="latest",
        has=["links"],
        min_likes=10,
        min_views=100,
    )

    assert payload["ok"] is True
    assert payload["raw"]["from_user"] == "OpenAI"
    assert payload["raw"]["search_type"] == "latest"
    assert payload["raw"]["has"] == ["links"]
    assert payload["raw"]["min_likes"] == 10
    assert payload["raw"]["min_views"] == 100


def test_collect_passes_user_posts_originals_only(tmp_path, monkeypatch):
    config = Config(config_path=tmp_path / "config.yaml")
    monkeypatch.setattr("x_reach.client.get_adapter", lambda channel, config=None: _StubAdapter(config=config))
    client = XReachClient(config=config)

    payload = client.twitter.user_posts("OpenAI", limit=5, originals_only=True)

    assert payload["ok"] is True
    assert payload["raw"]["originals_only"] is True


def test_collect_catches_unexpected_adapter_error(tmp_path, monkeypatch):
    class _BoomAdapter:
        def supported_operations(self):
            return ("search",)

        def search(self, value):
            raise RuntimeError("boom")

    config = Config(config_path=tmp_path / "config.yaml")
    monkeypatch.setattr("x_reach.client.get_adapter", lambda channel, config=None: _BoomAdapter())
    client = XReachClient(config=config)

    payload = client.collect("twitter", "search", "OpenAI")

    assert payload["ok"] is False
    assert payload["error"]["code"] == "internal_error"
