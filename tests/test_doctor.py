# -*- coding: utf-8 -*-
"""Tests for doctor output."""

import re

import pytest

import x_reach.doctor as doctor
from x_reach.config import Config


class _StubChannel:
    auth_kind = "cookie"
    entrypoint_kind = "cli"
    operations = ["search", "user"]
    required_commands = ["twitter"]
    host_patterns = []
    example_invocations = []
    supports_probe = True
    probe_operations = ["user", "search"]
    install_hints = []
    operation_contracts = {
        "search": {
            "name": "search",
            "input_kind": "query",
            "accepts_limit": True,
            "options": [],
        },
        "user": {
            "name": "user",
            "input_kind": "profile",
            "accepts_limit": False,
            "options": [],
        },
    }

    def __init__(self, name, description, status, message, backends=None):
        self.name = name
        self.description = description
        self._status = status
        self._message = message
        self.backends = backends or []

    def check(self, config=None):
        return self._status, self._message

    def probe(self, config=None):
        return "ok", f"probe:{self.name}"

    def to_contract(self):
        return {
            "name": self.name,
            "description": self.description,
            "backends": self.backends,
            "auth_kind": self.auth_kind,
            "entrypoint_kind": self.entrypoint_kind,
            "operations": self.operations,
            "required_commands": self.required_commands,
            "host_patterns": self.host_patterns,
            "example_invocations": self.example_invocations,
            "supports_probe": self.supports_probe,
            "probe_operations": self.probe_operations,
            "probe_coverage": "partial",
            "install_hints": self.install_hints,
            "operation_contracts": self.operation_contracts,
        }


@pytest.fixture
def tmp_config(tmp_path):
    return Config(config_path=tmp_path / "config.yaml")


def test_check_all_collects_channel_results(tmp_config, monkeypatch):
    monkeypatch.setattr(
        doctor,
        "get_all_channels",
        lambda: [
            _StubChannel("twitter", "Twitter/X", "warn", "twitter missing", ["twitter-cli"]),
        ],
    )

    results = doctor.check_all(tmp_config)
    assert results["twitter"]["name"] == "twitter"
    assert results["twitter"]["backends"] == ["twitter-cli"]
    assert results["twitter"]["probe_operations"] == ["user", "search"]


def test_check_all_uses_probe_when_requested(tmp_config, monkeypatch):
    monkeypatch.setattr(doctor, "get_all_channels", lambda: [_StubChannel("twitter", "Twitter/X", "warn", "ignored")])

    results = doctor.check_all(tmp_config, probe=True)
    assert results["twitter"]["status"] == "ok"
    assert results["twitter"]["message"] == "probe:twitter"


def test_format_report_lists_required_markers():
    report = doctor.format_report(
        {
            "twitter": {
                "status": "warn",
                "name": "twitter",
                "description": "Twitter/X",
                "message": "not authenticated",
                "backends": ["twitter-cli"],
                "supports_probe": True,
                "probe_coverage": "partial",
                "probe_run_coverage": "not_run",
                "unprobed_operations": ["search", "user"],
            },
        },
        required_channels=["twitter"],
    )

    plain = re.sub(r"\[[^\]]*\]", "", report)
    assert "(required)" in report
    assert "X Reach Health" in plain
    assert "Readiness policy: required channels = twitter" in plain


def test_doctor_payload_and_exit_code():
    results = {
        "twitter": {
            "name": "twitter",
            "description": "Twitter/X",
            "status": "warn",
            "message": "auth missing",
        },
    }

    payload = doctor.make_doctor_payload(results, probe=True, required_channels=["twitter"])
    assert payload["summary"]["required_not_ready"] == ["twitter"]
    assert doctor.doctor_exit_code(results, required_channels=["twitter"]) == 1


def test_doctor_rejects_unknown_required_channel():
    results = {
        "twitter": {"name": "twitter", "description": "Twitter/X", "status": "ok", "message": "ok"},
    }

    with pytest.raises(ValueError, match="Unknown required channel"):
        doctor.make_doctor_payload(results, required_channels=["missing"])

