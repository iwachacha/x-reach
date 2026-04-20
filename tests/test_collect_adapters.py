# -*- coding: utf-8 -*-
"""Tests for the Twitter collection adapter."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from x_reach.adapters.base import BaseAdapter
from x_reach.adapters.twitter import TwitterAdapter
from x_reach.config import Config


@pytest.fixture
def config(tmp_path):
    return Config(config_path=tmp_path / "config.yaml")


def _cp(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_base_adapter_runtime_env_uses_twitter_config(config, monkeypatch):
    monkeypatch.delenv("TWITTER_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWITTER_CT0", raising=False)
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    monkeypatch.delenv("CT0", raising=False)
    config.set("twitter_auth_token", "auth-token")
    config.set("twitter_ct0", "ct0-token")

    env = BaseAdapter(config=config).runtime_env()

    assert env["TWITTER_AUTH_TOKEN"] == "auth-token"
    assert env["TWITTER_CT0"] == "ct0-token"
    assert env["AUTH_TOKEN"] == "auth-token"
    assert env["CT0"] == "ct0-token"


def test_twitter_adapter_success(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    captured = {}

    def fake_run(command, timeout=120, env=None):
        captured["command"] = command
        return _cp(
            stdout=json.dumps(
                {
                    "ok": True,
                    "data": [
                        {
                            "id": "123",
                            "text": "OpenAI shipped a thing",
                            "author": {"screenName": "OpenAI", "name": "OpenAI"},
                            "createdAtISO": "2026-04-10T00:00:00Z",
                            "metrics": {"likes": 10},
                        }
                    ],
                }
            )
        )

    monkeypatch.setattr(adapter, "run_command", fake_run)

    payload = adapter.search("OpenAI", limit=1)

    assert payload["ok"] is True
    assert payload["items"][0]["author"] == "OpenAI"
    assert payload["items"][0]["url"] == "https://x.com/OpenAI/status/123"
    assert payload["items"][0]["extras"]["author_name"] == "OpenAI"
    assert payload["items"][0]["engagement"] == {"likes": 10}
    assert payload["items"][0]["identifiers"] == {
        "domain": "x.com",
        "author_handle": "OpenAI",
        "post_id": "123",
    }
    assert payload["meta"]["quality_profile"] == "balanced"
    assert payload["meta"]["fetch_limit"] == 3
    assert payload["meta"]["diagnostics"]["unbounded_time_window"] is True
    assert payload["meta"]["item_shape"] == {"engagement": "partial", "media": "partial"}
    assert captured["command"] == [
        "twitter",
        "search",
        "--type",
        "top",
        "--exclude",
        "retweets",
        "--exclude",
        "replies",
        "OpenAI",
        "-n",
        "3",
        "--json",
    ]


def test_twitter_adapter_search_translates_common_advanced_tokens(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    captured = {}

    def fake_run(command, timeout=120, env=None):
        captured["command"] = command
        return _cp(stdout=json.dumps({"ok": True, "data": []}))

    monkeypatch.setattr(adapter, "run_command", fake_run)

    payload = adapter.search("from:OpenAI has:media type:photos lang:ja", limit=5)

    assert payload["ok"] is True
    assert captured["command"] == [
        "twitter",
        "search",
        "--from",
        "OpenAI",
        "--has",
        "media",
        "--type",
        "photos",
        "--lang",
        "ja",
        "--exclude",
        "retweets",
        "--exclude",
        "replies",
        "-n",
        "15",
        "--json",
    ]


def test_twitter_adapter_search_prefers_explicit_since_until(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    captured = {}

    def fake_run(command, timeout=120, env=None):
        captured["command"] = command
        return _cp(stdout=json.dumps({"ok": True, "data": []}))

    monkeypatch.setattr(adapter, "run_command", fake_run)

    payload = adapter.search("OpenAI since:2025-01-01", limit=5, since="2026-01-01", until="2026-12-31")

    assert payload["ok"] is True
    assert captured["command"] == [
        "twitter",
        "search",
        "--type",
        "top",
        "--exclude",
        "retweets",
        "--exclude",
        "replies",
        "OpenAI",
        "--since",
        "2026-01-01",
        "--until",
        "2026-12-31",
        "-n",
        "15",
        "--json",
    ]
    assert payload["meta"]["since"] == "2026-01-01"
    assert payload["meta"]["until"] == "2026-12-31"


def test_twitter_adapter_search_accepts_formalized_filters(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    captured = {}

    def fake_run(command, timeout=120, env=None):
        captured["command"] = command
        return _cp(stdout=json.dumps({"ok": True, "data": []}))

    monkeypatch.setattr(adapter, "run_command", fake_run)

    payload = adapter.search(
        "OpenAI",
        limit=5,
        from_user="OpenAI",
        search_type="latest",
        has=["links"],
        exclude=["retweets"],
        min_likes=10,
        min_retweets=5,
    )

    assert payload["ok"] is True
    assert captured["command"] == [
        "twitter",
        "search",
        "--type",
        "latest",
        "--from",
        "OpenAI",
        "--has",
        "links",
        "--exclude",
        "retweets",
        "--exclude",
        "replies",
        "--min-likes",
        "10",
        "--min-retweets",
        "5",
        "OpenAI",
        "-n",
        "15",
        "--json",
    ]


def test_twitter_adapter_search_applies_min_views_client_side(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    monkeypatch.setattr(
        adapter,
        "run_command",
        lambda command, timeout=120, env=None: _cp(
            stdout=json.dumps(
                {
                    "ok": True,
                    "data": [
                        {
                            "id": "1",
                            "text": "lower",
                            "author": {"screenName": "OpenAI", "name": "OpenAI"},
                            "createdAtISO": "2026-04-10T00:00:00Z",
                            "metrics": {"views": 99},
                        },
                        {
                            "id": "2",
                            "text": "higher",
                            "author": {"screenName": "OpenAI", "name": "OpenAI"},
                            "createdAtISO": "2026-04-10T00:00:00Z",
                            "metrics": {"views": 1000},
                        },
                    ],
                }
            )
        ),
    )

    payload = adapter.search("OpenAI", limit=5, min_views=100)

    assert payload["ok"] is True
    assert [item["id"] for item in payload["items"]] == ["2"]
    assert payload["meta"]["diagnostics"]["client_side_filters"]["min_views"] == 100


def test_twitter_adapter_search_balanced_filters_noise_but_backfills_on_topic_results(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    monkeypatch.setattr(
        adapter,
        "run_command",
        lambda command, timeout=120, env=None: _cp(
            stdout=json.dumps(
                {
                    "ok": True,
                    "data": [
                        {
                            "id": "1",
                            "text": "OpenAI signal retweeted",
                            "author": {"screenName": "someone", "name": "Someone"},
                            "createdAtISO": "2026-04-10T00:00:00Z",
                            "isRetweet": True,
                            "metrics": {"likes": 500},
                        },
                        {
                            "id": "2",
                            "text": "OpenAI giveaway whitelist now live",
                            "author": {"screenName": "spam", "name": "Spam"},
                            "createdAtISO": "2026-04-10T00:00:00Z",
                            "metrics": {"likes": 5000},
                        },
                        {
                            "id": "3",
                            "text": "OpenAI shipped a useful update",
                            "author": {"screenName": "openai_watch", "name": "Watcher"},
                            "createdAtISO": "2026-04-10T00:00:00Z",
                            "metrics": {"likes": 1},
                        },
                    ],
                }
            )
        ),
    )

    payload = adapter.search("OpenAI", limit=1)

    assert [item["id"] for item in payload["items"]] == ["3"]
    assert payload["meta"]["query_tokens"] == ["openai"]
    assert payload["meta"]["filter_drop_counts"] == {"promo_phrase": 1, "retweet": 1}
    assert payload["meta"]["diagnostics"]["quality_filter"]["fallback_used"] == 1
    dropped_samples = payload["meta"]["diagnostics"]["quality_filter"]["dropped_samples"]
    assert [sample["id"] for sample in dropped_samples] == ["1", "2"]
    assert dropped_samples[0]["reasons"] == ["retweet"]
    assert dropped_samples[1]["reasons"] == ["promo_phrase"]


def test_twitter_adapter_user_success(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    monkeypatch.setattr(
        adapter,
        "run_command",
        lambda command, timeout=120, env=None: _cp(
            stdout=json.dumps(
                {
                    "ok": True,
                    "data": {
                        "id": "4398626122",
                        "name": "OpenAI",
                        "screenName": "OpenAI",
                        "bio": "Research lab",
                        "followers": 100,
                        "following": 4,
                        "tweets": 10,
                        "likes": 5,
                        "verified": True,
                        "profileImageUrl": "https://pbs.twimg.com/profile_images/openai.png",
                        "url": "https://openai.com",
                        "createdAtISO": "2015-12-06T22:51:08+00:00",
                    },
                }
            )
        ),
    )

    payload = adapter.user("@OpenAI")

    assert payload["ok"] is True
    assert payload["items"][0]["kind"] == "profile"
    assert payload["items"][0]["url"] == "https://x.com/OpenAI"
    assert payload["items"][0]["extras"]["followers"] == 100
    assert payload["items"][0]["identifiers"] == {
        "domain": "x.com",
        "author_handle": "OpenAI",
        "profile_handle": "OpenAI",
    }


def test_twitter_adapter_user_posts_success(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    monkeypatch.setattr(
        adapter,
        "run_command",
        lambda command, timeout=120, env=None: _cp(
            stdout=json.dumps(
                {
                    "ok": True,
                    "data": [
                        {
                            "id": "123",
                            "text": "OpenAI shipped a thing",
                            "author": {"screenName": "OpenAI", "name": "OpenAI"},
                            "createdAtISO": "2026-04-10T00:00:00Z",
                            "media": [{"type": "photo", "url": "https://pbs.twimg.com/media/a.png"}],
                        }
                    ],
                }
            )
        ),
    )

    payload = adapter.user_posts("https://x.com/OpenAI", limit=1)

    assert payload["ok"] is True
    assert payload["operation"] == "user_posts"
    assert payload["items"][0]["media_references"][0]["media_type"] == "photo"
    assert payload["items"][0]["extras"]["timeline_owner_handle"] == "OpenAI"
    assert payload["items"][0]["extras"]["timeline_item_kind"] == "original"
    assert payload["meta"]["originals_only"] is True
    assert payload["meta"]["quality_profile"] == "balanced"
    assert payload["meta"]["fetch_limit"] == 3
    assert payload["meta"]["item_shape"] == {"engagement": "partial", "media": "partial"}


def test_twitter_adapter_user_posts_can_filter_retweets(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    monkeypatch.setattr(
        adapter,
        "run_command",
        lambda command, timeout=120, env=None: _cp(
            stdout=json.dumps(
                {
                    "ok": True,
                    "data": [
                        {
                            "id": "1",
                            "text": "original",
                            "author": {"screenName": "OpenAI", "name": "OpenAI"},
                            "createdAtISO": "2026-04-10T00:00:00Z",
                            "isRetweet": False,
                        },
                        {
                            "id": "2",
                            "text": "retweet",
                            "author": {"screenName": "someone", "name": "Someone"},
                            "createdAtISO": "2026-04-10T00:00:00Z",
                            "isRetweet": True,
                            "retweetedBy": "OpenAI",
                        },
                    ],
                }
            )
        ),
    )

    payload = adapter.user_posts("OpenAI", limit=5, originals_only=True)

    assert payload["ok"] is True
    assert [item["id"] for item in payload["items"]] == ["1"]
    assert payload["meta"]["originals_only"] is True
    assert payload["meta"]["diagnostics"]["client_side_filters"]["originals_only"] is True


def test_twitter_adapter_user_posts_applies_metric_filters(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    monkeypatch.setattr(
        adapter,
        "run_command",
        lambda command, timeout=120, env=None: _cp(
            stdout=json.dumps(
                {
                    "ok": True,
                    "data": [
                        {
                            "id": "1",
                            "text": "low likes",
                            "author": {"screenName": "OpenAI", "name": "OpenAI"},
                            "metrics": {"likes": 9, "retweets": 10, "views": 1000},
                        },
                        {
                            "id": "2",
                            "text": "low retweets and views",
                            "author": {"screenName": "OpenAI", "name": "OpenAI"},
                            "metrics": {"likes": 50, "retweets": 2, "views": 50},
                        },
                        {
                            "id": "3",
                            "text": "enough engagement",
                            "author": {"screenName": "OpenAI", "name": "OpenAI"},
                            "metrics": {"likes": 50, "retweets": 10, "views": 1000},
                        },
                    ],
                }
            )
        ),
    )

    payload = adapter.user_posts(
        "OpenAI",
        limit=5,
        quality_profile="recall",
        min_likes=10,
        min_retweets=5,
        min_views=100,
    )

    assert payload["ok"] is True
    assert [item["id"] for item in payload["items"]] == ["3"]
    assert payload["meta"]["filter_drop_counts"] == {
        "min_likes": 1,
        "min_retweets": 1,
        "min_views": 1,
    }
    diagnostics = payload["meta"]["diagnostics"]
    assert diagnostics["client_side_filters"]["min_likes"] == 10
    assert diagnostics["client_side_filters"]["items_after_metric_filters"] == 1
    assert diagnostics["metric_filters"]["dropped_samples"][0]["reasons"] == ["min_likes"]


def test_twitter_adapter_user_posts_topic_fit_required_rules(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    monkeypatch.setattr(
        adapter,
        "run_command",
        lambda command, timeout=120, env=None: _cp(
            stdout=json.dumps(
                {
                    "ok": True,
                    "data": [
                        {
                            "id": "1",
                            "text": "Codex coding agent update from OpenAI",
                            "author": {"screenName": "OpenAI", "name": "OpenAI"},
                        },
                        {
                            "id": "2",
                            "text": "Codex mention without the required organization",
                            "author": {"screenName": "someone", "name": "Someone"},
                        },
                        {
                            "id": "3",
                            "text": "Unrelated launch notes",
                            "author": {"screenName": "someone", "name": "Someone"},
                        },
                    ],
                }
            )
        ),
    )

    payload = adapter.user_posts(
        "OpenAI",
        limit=5,
        quality_profile="recall",
        topic_fit={
            "required_any_terms": ["codex"],
            "required_all_terms": ["openai"],
            "synonym_groups": [["codex", "coding agent"]],
        },
    )

    assert [item["id"] for item in payload["items"]] == ["1"]
    assert payload["meta"]["filter_drop_counts"] == {
        "topic_fit_missing_required_any": 1,
        "topic_fit_missing_required_all": 2,
    }
    assert payload["meta"]["topic_fit_reason_counts"]["topic_fit_required_any"] == 1
    assert payload["meta"]["topic_fit_reason_counts"]["topic_fit_synonym_group"] == 1
    assert payload["items"][0]["extras"]["topic_fit"]["matched_terms"]["required_any_terms"] == ["codex"]
    assert payload["meta"]["diagnostics"]["topic_fit"]["missing_required_counts"] == {
        "required_all_terms": 2,
        "required_any_terms": 1,
    }


def test_twitter_adapter_user_posts_topic_fit_excluded_and_negative_rules(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    monkeypatch.setattr(
        adapter,
        "run_command",
        lambda command, timeout=120, env=None: _cp(
            stdout=json.dumps(
                {
                    "ok": True,
                    "data": [
                        {
                            "id": "1",
                            "text": "Codex airdrop giveaway",
                            "author": {"screenName": "OpenAI", "name": "OpenAI"},
                        },
                        {
                            "id": "2",
                            "text": "This is not about Codex",
                            "author": {"screenName": "OpenAI", "name": "OpenAI"},
                        },
                        {
                            "id": "3",
                            "text": "Codex developer workflow details",
                            "author": {"screenName": "OpenAI", "name": "OpenAI"},
                            "quotedTweet": {"author": {"screenName": "OpenAIDevs", "name": "OpenAI Developers"}},
                            "urls": [{"expandedUrl": "https://openai.com/codex"}],
                        },
                    ],
                }
            )
        ),
    )

    payload = adapter.user_posts(
        "OpenAI",
        limit=5,
        quality_profile="recall",
        topic_fit={
            "required_any_terms": ["codex"],
            "preferred_terms": ["developer workflow"],
            "excluded_terms": ["airdrop"],
            "negative_phrases": ["not about codex"],
        },
    )

    assert [item["id"] for item in payload["items"]] == ["3"]
    assert payload["meta"]["filter_drop_counts"] == {
        "topic_fit_excluded_term": 1,
        "topic_fit_negative_phrase": 1,
    }
    assert payload["meta"]["topic_fit_reason_counts"]["topic_fit_preferred"] == 1
    assert payload["meta"]["diagnostics"]["topic_fit"]["drop_counts"] == {
        "topic_fit_excluded_term": 1,
        "topic_fit_negative_phrase": 1,
    }


def test_twitter_adapter_hashtag_success(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    captured = {}

    def fake_run(command, timeout=120, env=None):
        captured["command"] = command
        return _cp(stdout=json.dumps({"ok": True, "data": []}))

    monkeypatch.setattr(adapter, "run_command", fake_run)

    payload = adapter.hashtag("OpenAI", limit=5, min_views=100)

    assert payload["ok"] is True
    assert payload["operation"] == "hashtag"
    assert payload["meta"]["input"] == "OpenAI"
    assert payload["meta"]["resolved_query"] == "#OpenAI"
    assert payload["meta"]["hashtag"] == "OpenAI"
    assert captured["command"] == [
        "twitter",
        "search",
        "--type",
        "top",
        "--exclude",
        "retweets",
        "--exclude",
        "replies",
        "#OpenAI",
        "-n",
        "15",
        "--json",
    ]


def test_twitter_adapter_hashtag_rejects_whitespace(config):
    adapter = TwitterAdapter(config=config)

    payload = adapter.hashtag("Open AI")

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_input"


def test_twitter_adapter_tweet_success(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    captured = {}

    def fake_run(command, timeout=120, env=None):
        captured["command"] = command
        return _cp(
            stdout=json.dumps(
                {
                    "ok": True,
                    "data": [
                        {
                            "id": "123",
                            "text": "OpenAI shipped a thing",
                            "author": {"screenName": "OpenAI", "name": "OpenAI"},
                            "createdAtISO": "2026-04-10T00:00:00Z",
                        }
                    ],
                }
            )
        )

    monkeypatch.setattr(adapter, "run_command", fake_run)

    payload = adapter.tweet("https://x.com/OpenAI/status/123", limit=1)

    assert payload["ok"] is True
    assert captured["command"][2] == "123"
    assert payload["items"][0]["url"] == "https://x.com/OpenAI/status/123"
    assert payload["meta"]["item_shape"] == {"engagement": "complete", "media": "complete"}


def test_twitter_adapter_not_authenticated(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    monkeypatch.setattr(
        adapter,
        "run_command",
        lambda command, timeout=120, env=None: _cp(
            stderr="error:\n  code: not_authenticated\n",
            returncode=1,
        ),
    )

    payload = adapter.search("OpenAI", limit=1)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "not_authenticated"


def test_twitter_adapter_preserves_structured_backend_errors(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    monkeypatch.setattr(
        adapter,
        "run_command",
        lambda command, timeout=120, env=None: _cp(
            stdout=json.dumps(
                {
                    "ok": False,
                    "schema_version": "1",
                    "error": {
                        "code": "not_found",
                        "message": "Twitter API error (HTTP 404): Twitter API error 404: ",
                    },
                }
            ),
            returncode=1,
        ),
    )

    payload = adapter.search("OpenAI", limit=1)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "not_found"
    assert payload["raw"]["error"]["code"] == "not_found"


def test_twitter_adapter_classifies_plain_http_409_conflict(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    monkeypatch.setattr(
        adapter,
        "run_command",
        lambda command, timeout=120, env=None: _cp(
            stderr="Twitter API error (HTTP 409): conflict",
            returncode=1,
        ),
    )

    payload = adapter.search("OpenAI", limit=1)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "http_409"
    assert payload["error"]["category"] == "upstream_unavailable"
    assert payload["error"]["details"]["http_status"] == 409


def test_twitter_adapter_classifies_plain_http_429_rate_limit(config, monkeypatch):
    adapter = TwitterAdapter(config=config)
    monkeypatch.setattr(adapter, "command_path", lambda _name: "twitter")
    monkeypatch.setattr(
        adapter,
        "run_command",
        lambda command, timeout=120, env=None: _cp(
            stderr="Twitter API error (HTTP 429): too many requests",
            returncode=1,
        ),
    )

    payload = adapter.search("OpenAI", limit=1)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "rate_limited"
    assert payload["error"]["category"] == "rate_limited"
    assert payload["error"]["details"]["http_status"] == 429
