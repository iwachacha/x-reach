# -*- coding: utf-8 -*-
"""CLI contract tests that guard the stable public surface."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import agent_reach.cli as legacy_cli
from x_reach.cli import build_parser, main
from x_reach.ledger import build_ledger_record
from x_reach.results import build_item, build_result


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
    assert "--version" in output
    assert "collect" in output
    assert "doctor" in output
    assert "channels" in output
    assert "schema" in output
    assert "plan" in output


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


@pytest.mark.parametrize(
    ("schema_name", "title", "required_fields"),
    [
        (
            "collection-result",
            "X Reach CollectionResult",
            {"ok", "channel", "operation", "items", "meta", "error", "x_reach_version"},
        ),
        (
            "mission-spec",
            "X Reach MissionSpec",
            {"queries"},
        ),
        (
            "judge-result",
            "X Reach JudgeResult",
            {"record_type", "decision", "judge", "candidate", "fallback"},
        ),
    ],
)
def test_schema_contract_json_shape(capsys, schema_name, title, required_fields):
    assert main(["schema", schema_name, "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["title"] == title
    assert payload["type"] == "object"
    assert required_fields.issubset(set(payload["properties"]))

    if schema_name == "collection-result":
        assert "NormalizedItem" in payload["$defs"]
    elif schema_name == "mission-spec":
        assert payload["properties"]["queries"]["minItems"] == 1
        assert "coverage" in payload["properties"]
        assert "topic_fit" in payload["properties"]
    else:
        assert payload["properties"]["record_type"]["const"] == "judge_result"
        assert "fallback_keep" in payload["properties"]["decision"]["enum"]


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
    assert payload["probe"] is False
    assert payload["schema_version"]
    assert payload["summary"]["ready"] == 1
    assert payload["summary"]["exit_code"] == 0
    assert payload["channels"][0]["name"] == "twitter"
    assert payload["channels"][0]["supports_probe"] is True
    assert payload["channels"][0]["probe_run_coverage"] == "not_run"


def test_doctor_probe_contract_json_shape(capsys, monkeypatch):
    def fake_check_all(_config, probe=False):
        assert probe is True
        return {
            "twitter": {
                "name": "twitter",
                "description": "Twitter/X",
                "status": "ok",
                "message": "probe ready",
                "backends": ["twitter-cli"],
                "auth_kind": "cookie",
                "entrypoint_kind": "cli",
                "operations": ["search", "hashtag", "user", "user_posts", "tweet"],
                "required_commands": ["twitter"],
                "supports_probe": True,
                "probe_operations": ["search", "hashtag", "user", "user_posts", "tweet"],
                "probe_coverage": "full",
                "probe_run_coverage": "full",
                "probed_operations": ["search", "hashtag", "user", "user_posts", "tweet"],
                "unprobed_operations": [],
                "operation_statuses": {
                    "search": {"status": "ok", "message": "ok"},
                    "user": {"status": "ok", "message": "ok"},
                },
            }
        }

    monkeypatch.setattr("x_reach.doctor.check_all", fake_check_all)

    assert main(["doctor", "--json", "--probe"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["probe"] is True
    assert payload["summary"]["exit_code"] == 0
    assert payload["summary"]["probe_attention"] == []
    assert payload["channels"][0]["name"] == "twitter"
    assert payload["channels"][0]["probe_run_coverage"] == "full"
    assert payload["channels"][0]["operation_statuses"]["search"]["status"] == "ok"


def test_channels_contract_json_shape(capsys):
    assert main(["channels", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"]
    assert payload["generated_at"]
    assert payload["channels"][0]["name"] == "twitter"
    assert payload["channels"][0]["supports_probe"] is True
    assert payload["channels"][0]["probe_coverage"] == "full"
    assert payload["channels"][0]["operation_contracts"]["search"]["input_kind"] == "query"
    assert payload["channels"][0]["operation_contracts"]["user_posts"]["input_kind"] == "profile"


def test_plan_candidates_contract_json_shape(tmp_path, capsys):
    ledger_path = _write_candidate_fixture(tmp_path / "evidence.jsonl")

    assert main(["plan", "candidates", "--input", str(ledger_path), "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"]
    assert payload["command"] == "plan candidates"
    assert payload["input"] == str(ledger_path)
    assert payload["by"] == "url"
    assert payload["sort_by"] == "first_seen"
    assert payload["summary"]["candidate_count"] == 1
    assert payload["summary"]["returned"] == 1
    assert payload["summary"]["collection_results"] == 1
    assert payload["topic_fit"]["enabled"] is False
    assert payload["candidates"][0]["id"] == "tweet-1"
    assert payload["candidates"][0]["url"] == "https://x.com/openai/status/1"
    assert payload["candidates"][0]["extras"]["seen_in"][0]["run_id"] == "contract-run"


def test_legacy_agent_reach_cli_help_contract(capsys):
    with pytest.raises(SystemExit) as exc_info:
        legacy_cli.main(["--help"])

    assert exc_info.value.code == 0
    assert "usage: x-reach" in capsys.readouterr().out


def _write_candidate_fixture(path: Path) -> Path:
    result = build_result(
        ok=True,
        channel="twitter",
        operation="search",
        items=[
            build_item(
                item_id="tweet-1",
                kind="post",
                title="OpenAI ships a CLI contract update",
                url="https://x.com/openai/status/1",
                text="OpenAI ships a CLI contract update with stable JSON output.",
                author="openai",
                published_at=None,
                source="twitter",
                extras={"timeline_item_kind": "original"},
            )
        ],
        raw={"ok": True},
        meta={"input": "OpenAI", "count": 1, "query_tokens": ["openai"]},
        error=None,
    )
    record = build_ledger_record(result, run_id="contract-run", input_value="OpenAI")
    path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
