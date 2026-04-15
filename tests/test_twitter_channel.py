# -*- coding: utf-8 -*-
"""Tests for the Twitter/X channel."""

from unittest.mock import Mock, patch

from agent_reach.channels.twitter import TwitterChannel


def _cp(stdout="", stderr="", returncode=0):
    mock = Mock()
    mock.stdout = stdout
    mock.stderr = stderr
    mock.returncode = returncode
    return mock


def test_check_reports_warn_when_not_installed():
    with patch("agent_reach.channels.twitter.find_command", return_value=None), patch(
        "shutil.which", return_value=None
    ):
        status, message, extra = TwitterChannel().check_detailed()
    assert status == "warn"
    assert "uv tool install twitter-cli" in message
    assert extra["probe_run_coverage"] == "not_run"
    assert extra["probed_operations"] == []
    assert extra["unprobed_operations"] == ["search", "hashtag", "user", "user_posts", "tweet"]
    assert extra["operation_statuses"]["search"]["status"] == "off"


def test_check_preserves_two_tuple_contract():
    with patch("agent_reach.channels.twitter.find_command", return_value=None), patch(
        "shutil.which", return_value=None
    ):
        status, message = TwitterChannel().check()
    assert status == "warn"
    assert "twitter-cli" in message


def test_check_reports_warn_when_live_operations_are_unverified():
    channel = TwitterChannel()
    with patch(
        "agent_reach.channels.twitter.find_command",
        return_value="/usr/local/bin/twitter",
    ), patch(
        "subprocess.run",
        return_value=_cp(stdout="ok: true\nusername: testuser\n", returncode=0),
    ):
        status, message, extra = channel.check_detailed()
    assert status == "warn"
    assert "collect may work" in message
    assert extra["diagnostic_basis"] == "twitter_status_authenticated"
    assert extra["usability_hint"] == "authenticated_but_unprobed"
    assert extra["recommended_probe_command"] == "x-reach doctor --json --probe"
    assert extra["probe_run_coverage"] == "not_run"
    assert extra["unprobed_operations"] == ["search", "hashtag", "user", "user_posts", "tweet"]
    assert extra["operation_statuses"]["search"]["status"] == "unknown"
    assert extra["operation_statuses"]["search"]["usability_hint"] == "authenticated_but_unprobed"


def test_check_reports_warn_when_not_authenticated():
    channel = TwitterChannel()
    with patch(
        "agent_reach.channels.twitter.find_command",
        return_value="/usr/local/bin/twitter",
    ), patch(
        "subprocess.run",
        return_value=_cp(stderr="ok: false\nerror:\n  code: not_authenticated\n", returncode=1),
    ):
        status, message, extra = channel.check_detailed()
    assert status == "warn"
    assert "configure twitter-cookies" in message
    assert extra["operation_statuses"]["user"]["status"] == "off"


def test_check_passes_config_credentials_into_status(tmp_path):
    from agent_reach.config import Config

    config = Config(config_path=tmp_path / "config.yaml")
    config.set("twitter_auth_token", "auth-token")
    config.set("twitter_ct0", "ct0-token")

    captured = {}
    channel = TwitterChannel()
    with patch(
        "os.environ",
        {},
    ), patch(
        "agent_reach.channels.twitter.find_command",
        return_value="/usr/local/bin/twitter",
    ), patch(
        "subprocess.run",
        side_effect=lambda *args, **kwargs: captured.update({"env": kwargs.get("env")}) or _cp(stdout="ok: true", returncode=0),
    ):
        status, _message, _extra = channel.check_detailed(config)

    assert status == "warn"
    assert captured["env"]["AUTH_TOKEN"] == "auth-token"
    assert captured["env"]["CT0"] == "ct0-token"
    assert captured["env"]["PYTHONIOENCODING"] == "utf-8"
    assert captured["env"]["PYTHONUTF8"] == "1"


def test_probe_uses_live_user_lookup():
    channel = TwitterChannel()
    with patch(
        "agent_reach.channels.twitter.find_command",
        return_value="/usr/local/bin/twitter",
    ), patch(
        "shutil.which",
        return_value="/usr/local/bin/twitter",
    ), patch(
        "agent_reach.channels.twitter.TwitterAdapter.user",
        return_value={
            "ok": True,
            "channel": "twitter",
            "operation": "user",
            "items": [{"id": "1"}],
            "raw": {"ok": True},
            "meta": {"count": 1},
            "error": None,
        },
    ) as mocked_user, patch(
        "agent_reach.channels.twitter.TwitterAdapter.search",
        return_value={
            "ok": True,
            "channel": "twitter",
            "operation": "search",
            "items": [{"id": "tweet-1"}],
            "raw": {"ok": True},
            "meta": {"count": 1},
            "error": None,
        },
    ) as mocked_search, patch(
        "agent_reach.channels.twitter.TwitterAdapter.user_posts",
        return_value={
            "ok": True,
            "channel": "twitter",
            "operation": "user_posts",
            "items": [{"id": "tweet-2", "url": "https://x.com/openai/status/2"}],
            "raw": {"ok": True},
            "meta": {"count": 1},
            "error": None,
        },
    ) as mocked_user_posts, patch(
        "agent_reach.channels.twitter.TwitterAdapter.tweet",
        return_value={
            "ok": True,
            "channel": "twitter",
            "operation": "tweet",
            "items": [{"id": "tweet-2"}],
            "raw": {"ok": True},
            "meta": {"count": 1},
            "error": None,
        },
    ) as mocked_tweet:
        status, message, extra = channel.probe_detailed()

    assert status == "ok"
    assert "user posts lookup" in message
    assert extra["probe_run_coverage"] == "full"
    assert extra["probed_operations"] == ["search", "hashtag", "user", "user_posts", "tweet"]
    assert extra["unprobed_operations"] == []
    assert extra["operation_statuses"]["user"]["status"] == "ok"
    assert extra["operation_statuses"]["search"]["status"] == "ok"
    assert extra["operation_statuses"]["hashtag"]["status"] == "ok"
    assert extra["operation_statuses"]["user_posts"]["status"] == "ok"
    assert extra["operation_statuses"]["tweet"]["status"] == "ok"
    mocked_user.assert_called_once_with("openai")
    mocked_search.assert_called_once_with("OpenAI", limit=1)
    mocked_user_posts.assert_called_once_with("openai", limit=1)
    mocked_tweet.assert_called_once_with("https://x.com/openai/status/2", limit=1)


def test_probe_reports_search_failure_separately_from_live_user_lookup():
    channel = TwitterChannel()
    with patch(
        "agent_reach.channels.twitter.find_command",
        return_value="/usr/local/bin/twitter",
    ), patch(
        "shutil.which",
        return_value="/usr/local/bin/twitter",
    ), patch(
        "agent_reach.channels.twitter.TwitterAdapter.user",
        return_value={
            "ok": True,
            "channel": "twitter",
            "operation": "user",
            "items": [{"id": "1"}],
            "raw": {"ok": True},
            "meta": {"count": 1},
            "error": None,
        },
    ), patch(
        "agent_reach.channels.twitter.TwitterAdapter.search",
        return_value={
            "ok": False,
            "channel": "twitter",
            "operation": "search",
            "items": [],
            "raw": {"ok": False},
            "meta": {"count": 0},
            "error": {
                "code": "not_found",
                "message": "Twitter API error (HTTP 404)",
                "details": {"returncode": 1},
            },
        },
    ), patch(
        "agent_reach.channels.twitter.TwitterAdapter.user_posts",
        return_value={
            "ok": True,
            "channel": "twitter",
            "operation": "user_posts",
            "items": [{"id": "tweet-2", "url": "https://x.com/openai/status/2"}],
            "raw": {"ok": True},
            "meta": {"count": 1},
            "error": None,
        },
    ), patch(
        "agent_reach.channels.twitter.TwitterAdapter.tweet",
        return_value={
            "ok": True,
            "channel": "twitter",
            "operation": "tweet",
            "items": [{"id": "tweet-2"}],
            "raw": {"ok": True},
            "meta": {"count": 1},
            "error": None,
        },
    ):
        status, message, extra = channel.probe_detailed()

    assert status == "warn"
    assert "search=not_found" in message
    assert extra["probe_run_coverage"] == "full"
    assert extra["probed_operations"] == ["search", "hashtag", "user", "user_posts", "tweet"]
    assert extra["unprobed_operations"] == []
    assert extra["operation_statuses"]["user"]["status"] == "ok"
    assert extra["operation_statuses"]["search"]["error_code"] == "not_found"
    assert extra["operation_statuses"]["hashtag"]["error_code"] == "not_found"

