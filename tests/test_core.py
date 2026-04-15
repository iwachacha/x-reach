# -*- coding: utf-8 -*-
"""Tests for the renamed X Reach core surface."""

import pytest

from agent_reach.config import Config
from agent_reach.core import AgentReach
from x_reach.core import XReach, XReachClient


@pytest.fixture
def eyes(tmp_path):
    config = Config(config_path=tmp_path / "config.yaml")
    return XReach(config=config)


class TestXReach:
    def test_init(self, eyes):
        assert eyes.config is not None

    def test_legacy_core_alias_still_resolves(self, eyes):
        legacy = AgentReach(config=eyes.config)
        assert isinstance(legacy, XReachClient)

    def test_doctor(self, eyes):
        results = eyes.doctor()
        assert isinstance(results, dict)
        assert "twitter" in results

    def test_doctor_report(self, eyes):
        report = eyes.doctor_report()
        assert isinstance(report, str)
        assert "X Reach" in report

    def test_doctor_payload(self, eyes):
        payload = eyes.doctor_payload()
        assert payload["schema_version"]
        assert "channels" in payload

    def test_channels(self, eyes):
        channels = eyes.channels()
        assert isinstance(channels, list)
        assert [channel["name"] for channel in channels] == ["twitter"]

