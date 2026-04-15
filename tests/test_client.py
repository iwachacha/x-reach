# -*- coding: utf-8 -*-
"""Tests for the external Agent Reach SDK surface."""

from agent_reach.client import AgentReach, AgentReachClient
from agent_reach.config import Config
from agent_reach.results import build_result


class _StubAdapter:
    channel = "twitter"

    def __init__(self, config=None):
        self.config = config

    def supported_operations(self):
        return ("search",)

    def search(self, value, limit=None, since=None, until=None):
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
            raw={"value": value, "limit": limit, "since": since, "until": until},
            meta={"input": value},
            error=None,
        )


def test_agent_reach_alias_and_namespace_access(tmp_path, monkeypatch):
    config = Config(config_path=tmp_path / "config.yaml")
    monkeypatch.setattr("agent_reach.client.get_adapter", lambda channel, config=None: _StubAdapter(config=config))

    client = AgentReachClient(config=config)
    legacy = AgentReach(config=config)

    assert isinstance(legacy, AgentReachClient)
    assert client.twitter._channel == "twitter"
    assert client.twitter.search("OpenAI")["ok"] is True


def test_collect_rejects_blank_input(tmp_path):
    client = AgentReachClient(config=Config(config_path=tmp_path / "config.yaml"))
    payload = client.collect("twitter", "search", "   ")
    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_input"


def test_collect_rejects_invalid_limit(tmp_path):
    client = AgentReachClient(config=Config(config_path=tmp_path / "config.yaml"))
    payload = client.collect("twitter", "search", "OpenAI", limit=0)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_input"


def test_collect_reports_unsupported_operation(tmp_path, monkeypatch):
    config = Config(config_path=tmp_path / "config.yaml")
    monkeypatch.setattr("agent_reach.client.get_adapter", lambda channel, config=None: _StubAdapter(config=config))
    client = AgentReachClient(config=config)

    payload = client.collect("twitter", "user", "openai")

    assert payload["ok"] is False
    assert payload["error"]["code"] == "unsupported_operation"
    assert payload["meta"]["supported_operations"] == ["search"]


def test_collect_reports_unknown_channel(tmp_path, monkeypatch):
    config = Config(config_path=tmp_path / "config.yaml")
    monkeypatch.setattr("agent_reach.client.get_adapter", lambda channel, config=None: None)
    client = AgentReachClient(config=config)

    payload = client.collect("missing", "search", "value")

    assert payload["ok"] is False
    assert payload["error"]["code"] == "unknown_channel"


def test_collect_passes_twitter_since_until_from_contract(tmp_path, monkeypatch):
    config = Config(config_path=tmp_path / "config.yaml")
    monkeypatch.setattr("agent_reach.client.get_adapter", lambda channel, config=None: _StubAdapter(config=config))
    client = AgentReachClient(config=config)

    payload = client.collect("twitter", "search", "OpenAI", since="2026-01-01", until="2026-12-31")

    assert payload["ok"] is True
    assert payload["raw"] == {"value": "OpenAI", "limit": None, "since": "2026-01-01", "until": "2026-12-31"}


def test_collect_catches_unexpected_adapter_error(tmp_path, monkeypatch):
    class _BoomAdapter:
        def supported_operations(self):
            return ("search",)

        def search(self, value):
            raise RuntimeError("boom")

    config = Config(config_path=tmp_path / "config.yaml")
    monkeypatch.setattr("agent_reach.client.get_adapter", lambda channel, config=None: _BoomAdapter())
    client = AgentReachClient(config=config)

    payload = client.collect("twitter", "search", "OpenAI")

    assert payload["ok"] is False
    assert payload["error"]["code"] == "internal_error"
