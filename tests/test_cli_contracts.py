# -*- coding: utf-8 -*-
"""CLI contract tests that guard the stable public surface."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

import agent_reach.cli as legacy_cli
from x_reach.cli import build_parser, main


def test_build_parser_registers_stable_root_commands():
    parser = build_parser()
    subparsers = next(
        action
        for action in parser._actions  # noqa: SLF001
        if action.__class__.__name__ == "_SubParsersAction"
    )

    assert set(subparsers.choices) >= {
        "install",
        "configure",
        "doctor",
        "collect",
        "search",
        "hashtag",
        "user",
        "posts",
        "tweet",
        "plan",
        "scout",
        "batch",
        "channels",
        "schema",
        "export-integration",
        "ledger",
        "uninstall",
        "skill",
        "check-update",
        "version",
    }


def test_build_parser_parses_major_command_shapes():
    parser = build_parser()

    assert parser.parse_args(["version"]).command == "version"
    assert parser.parse_args(["schema", "collection-result"]).name == "collection-result"
    assert parser.parse_args(["doctor", "--json"]).command == "doctor"
    assert parser.parse_args(["channels", "--json"]).command == "channels"
    assert parser.parse_args(["plan", "candidates", "--input", "evidence.jsonl"]).plan_command == "candidates"
    assert parser.parse_args(["ledger", "query", "--input", "evidence.jsonl"]).ledger_command == "query"


def test_root_help_contract(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "usage: x-reach" in output
    assert "collect" in output
    assert "doctor" in output
    assert "channels" in output
    assert "schema" in output


def test_version_contract(capsys):
    assert main(["version"]) == 0
    assert "X Reach v" in capsys.readouterr().out


def test_python_module_entrypoint_contract():
    result = subprocess.run(
        [sys.executable, "-m", "x_reach.cli", "version"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )

    assert result.returncode == 0
    assert "X Reach v" in result.stdout


def test_schema_contract_json_shape(capsys):
    assert main(["schema", "collection-result", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["title"] == "X Reach CollectionResult"
    assert "properties" in payload
    assert "ok" in payload["properties"]
    assert "x_reach_version" in payload["properties"]


def test_doctor_contract_json_shape(capsys, monkeypatch):
    monkeypatch.setattr(
        "x_reach.doctor.check_all",
        lambda _config, probe=False: {
            "twitter": {
                "name": "twitter",
                "description": "Twitter/X",
                "status": "ok",
                "message": "ready",
                "backends": ["twitter-cli"],
                "auth_kind": "cookie",
                "entrypoint_kind": "cli",
                "operations": ["search"],
                "required_commands": ["twitter"],
                "supports_probe": True,
                "probe_operations": ["search"],
                "probe_coverage": "full",
                "probe_run_coverage": "not_run",
                "unprobed_operations": ["search"],
            }
        },
    )

    assert main(["doctor", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"]
    assert payload["summary"]["ready"] == 1
    assert payload["channels"][0]["name"] == "twitter"


def test_channels_contract_json_shape(capsys):
    assert main(["channels", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"]
    assert payload["generated_at"]
    assert payload["channels"][0]["name"] == "twitter"
    assert payload["channels"][0]["operation_contracts"]["search"]["input_kind"] == "query"


def test_legacy_agent_reach_cli_help_contract(capsys):
    with pytest.raises(SystemExit) as exc_info:
        legacy_cli.main(["--help"])

    assert exc_info.value.code == 0
    assert "usage: x-reach" in capsys.readouterr().out
