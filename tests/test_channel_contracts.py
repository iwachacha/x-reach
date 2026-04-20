# -*- coding: utf-8 -*-
"""Contract tests for the Twitter-only channel surface."""

from x_reach.channels import get_all_channels
from x_reach.config import Config


def test_channel_registry_contract():
    channels = get_all_channels()
    assert len(channels) == 1

    contract = channels[0].to_contract()
    assert contract["name"] == "twitter"
    assert contract["description"]
    assert contract["backends"] == ["twitter-cli"]
    assert contract["auth_kind"] == "cookie"
    assert contract["entrypoint_kind"] == "cli"
    assert contract["operations"] == ["search", "hashtag", "user", "user_posts", "tweet"]
    assert contract["required_commands"] == ["twitter"]
    assert contract["supports_probe"] is True
    assert contract["probe_operations"] == ["search", "hashtag", "user", "user_posts", "tweet"]
    assert contract["probe_coverage"] == "full"

    search = contract["operation_contracts"]["search"]
    assert search["input_kind"] == "query"
    assert [option["name"] for option in search["options"]] == [
        "from",
        "to",
        "lang",
        "type",
        "has",
        "exclude",
        "since",
        "until",
        "min_likes",
        "min_retweets",
        "min_views",
        "quality_profile",
    ]
    hashtag = contract["operation_contracts"]["hashtag"]
    assert hashtag["input_kind"] == "hashtag"
    assert [option["name"] for option in hashtag["options"]] == [option["name"] for option in search["options"]]
    user_posts = contract["operation_contracts"]["user_posts"]
    assert user_posts["options"] == [
        {
            "name": "originals_only",
            "type": "boolean",
            "required": False,
            "cli_flag": "--originals-only",
            "description": "Filter timeline results down to authored posts by removing retweets client-side.",
        },
        {
            "name": "min_likes",
            "type": "integer",
            "required": False,
            "cli_flag": "--min-likes",
            "sdk_kwarg": "min_likes",
            "minimum": 0,
            "description": "Minimum likes applied after timeline lookup as a client-side post-filter.",
        },
        {
            "name": "min_retweets",
            "type": "integer",
            "required": False,
            "cli_flag": "--min-retweets",
            "sdk_kwarg": "min_retweets",
            "minimum": 0,
            "description": "Minimum retweets applied after timeline lookup as a client-side post-filter.",
        },
        {
            "name": "min_views",
            "type": "integer",
            "required": False,
            "cli_flag": "--min-views",
            "sdk_kwarg": "min_views",
            "minimum": 0,
            "description": "Minimum views applied after timeline lookup as a client-side post-filter.",
        },
        {
            "name": "topic_fit",
            "type": "object",
            "required": False,
            "cli_flag": "--topic-fit",
            "sdk_kwarg": "topic_fit",
            "description": "Caller-declared deterministic topic-fit rules applied after timeline lookup.",
        },
        {
            "name": "quality_profile",
            "type": "string",
            "required": False,
            "cli_flag": "--quality-profile",
            "choices": ["precision", "balanced", "recall"],
            "description": "High-signal collection profile that controls oversampling and noise filtering.",
        }
    ]


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
