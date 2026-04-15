# -*- coding: utf-8 -*-
"""Contract tests for the Twitter-only channel surface."""

from agent_reach.channels import get_all_channels
from agent_reach.config import Config


def test_channel_registry_contract():
    channels = get_all_channels()
    assert len(channels) == 1

    contract = channels[0].to_contract()
    assert contract["name"] == "twitter"
    assert contract["description"]
    assert contract["backends"] == ["twitter-cli"]
    assert contract["auth_kind"] == "cookie"
    assert contract["entrypoint_kind"] == "cli"
    assert contract["operations"] == ["search", "user", "user_posts", "tweet"]
    assert contract["required_commands"] == ["twitter"]
    assert contract["supports_probe"] is True
    assert contract["probe_operations"] == ["user", "search"]
    assert contract["probe_coverage"] == "partial"

    search = contract["operation_contracts"]["search"]
    assert search["input_kind"] == "query"
    assert [option["name"] for option in search["options"]] == ["since", "until"]


def test_channel_check_contract_with_minimal_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    config = Config(config_path=tmp_path / "config.yaml")

    for channel in get_all_channels():
        status, message = channel.check(config)
        assert status in {"ok", "warn", "off", "error"}
        assert isinstance(message, str) and message.strip()


def test_channel_can_handle_contract():
    channel = get_all_channels()[0]
    assert isinstance(channel.can_handle("https://x.com/openai/status/1"), bool)
