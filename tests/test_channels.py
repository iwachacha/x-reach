# -*- coding: utf-8 -*-
"""Tests for the narrowed Twitter-only channel registry."""

from agent_reach.channels import get_all_channels, get_channel
from agent_reach.channels.twitter import TwitterChannel


def test_registry_contains_only_twitter():
    names = [channel.name for channel in get_all_channels()]
    assert names == ["twitter"]


def test_get_channel_by_name():
    channel = get_channel("twitter")
    assert channel is not None
    assert channel.name == "twitter"


def test_get_unknown_channel_returns_none():
    assert get_channel("not-exists") is None


def test_twitter_can_handle_x_urls():
    channel = TwitterChannel()
    assert channel.can_handle("https://x.com/openai/status/1")
    assert channel.can_handle("https://twitter.com/openai/status/1")
    assert not channel.can_handle("https://example.com")
