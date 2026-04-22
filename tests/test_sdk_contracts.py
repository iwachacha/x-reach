# -*- coding: utf-8 -*-
"""SDK contract tests that guard the documented public Python surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import agent_reach
import x_reach
from x_reach import AgentReach, AgentReachClient, XReach, XReachClient
from x_reach.channels import get_channel_contract
from x_reach.config import Config
from x_reach.ledger import build_ledger_record
from x_reach.results import build_item, build_result


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> XReachClient:
    monkeypatch.setattr(Config, "CONFIG_FILE", tmp_path / "config.yaml")
    return XReachClient()


def test_primary_sdk_import_contract():
    assert x_reach.XReachClient is XReachClient
    assert x_reach.XReach is XReach
    assert AgentReachClient is XReachClient
    assert AgentReach is XReach
    assert issubclass(XReach, XReachClient)

    assert agent_reach.XReachClient is XReachClient
    assert agent_reach.XReach is XReach
    assert agent_reach.AgentReachClient is XReachClient
    assert agent_reach.AgentReach is XReach


def test_x_reach_client_channels_contract(client: XReachClient):
    channels = client.channels()

    assert isinstance(channels, list)
    assert len(channels) == 1
    twitter = channels[0]
    assert twitter["name"] == "twitter"
    assert twitter["entrypoint_kind"] == "cli"
    assert twitter["required_commands"] == ["twitter"]
    assert twitter["supports_probe"] is True
    assert twitter["probe_coverage"] == "full"
    assert set(twitter["operations"]) == {"search", "hashtag", "user", "user_posts", "tweet"}
    assert twitter["operation_contracts"]["search"]["input_kind"] == "query"
    assert twitter["operation_contracts"]["user_posts"]["input_kind"] == "profile"


def test_x_reach_client_doctor_payload_contract(client: XReachClient, monkeypatch: pytest.MonkeyPatch):
    contract = get_channel_contract("twitter")
    assert contract is not None

    def fake_check_all(config: Config, probe: bool = False) -> dict[str, dict[str, Any]]:
        assert config is client.config
        return {
            "twitter": {
                **contract,
                "status": "ok",
                "message": "ready",
                "operation_statuses": {
                    "search": {"status": "ok", "message": "ok"},
                    "user_posts": {"status": "ok", "message": "ok"},
                },
                "probed_operations": ["search", "user_posts"] if probe else [],
                "unprobed_operations": [] if probe else list(contract["operations"]),
                "probe_run_coverage": "full" if probe else "not_run",
            }
        }

    monkeypatch.setattr("x_reach.doctor.check_all", fake_check_all)

    payload = client.doctor_payload(probe=True, required_channels=["twitter"])

    assert payload["schema_version"]
    assert payload["generated_at"]
    assert payload["probe"] is True
    assert payload["summary"]["readiness_mode"] == "selected"
    assert payload["summary"]["required_channels"] == ["twitter"]
    assert payload["summary"]["exit_code"] == 0
    assert payload["channels"][0]["name"] == "twitter"
    assert payload["channels"][0]["probe_run_coverage"] == "full"
    assert payload["channels"][0]["operation_statuses"]["search"]["status"] == "ok"


def test_x_reach_client_plan_candidates_contract(
    client: XReachClient,
    tmp_path: Path,
    assert_candidate_plan_quality_contract,
):
    ledger_path = _write_candidate_fixture(tmp_path / "evidence.jsonl")

    payload = client.plan_candidates(ledger_path, by="url", min_seen_in=1)

    assert_candidate_plan_quality_contract(payload)
    assert payload["schema_version"]
    assert payload["generated_at"]
    assert payload["command"] == "plan candidates"
    assert payload["input"] == str(ledger_path)
    assert payload["by"] == "url"
    assert payload["sort_by"] == "first_seen"
    assert payload["topic_fit"]["enabled"] is False
    assert payload["summary"]["collection_results"] == 1
    assert payload["summary"]["candidate_count"] == 1
    assert payload["summary"]["returned"] == 1
    candidate = payload["candidates"][0]
    assert candidate["id"] == "tweet-1"
    assert candidate["url"] == "https://x.com/openai/status/1"
    assert candidate["seen_in_count"] == 1
    assert "query_match" in candidate["quality_reasons"]
    assert payload["summary"]["quality_reason_counts"]["strong_query_match"] == 1
    assert candidate["extras"]["seen_in"][0]["run_id"] == "sdk-contract-run"


def test_x_reach_client_mission_plan_contract(
    client: XReachClient,
    tmp_path: Path,
    assert_mission_plan_envelope,
):
    spec_path = _write_mission_spec(tmp_path / "mission.json")
    output_dir = tmp_path / "mission-output"

    payload = client.mission_plan(spec_path, output_dir=output_dir, run_id="sdk-mission-run")

    assert_mission_plan_envelope(
        payload,
        spec_path=spec_path,
        output_dir=output_dir,
        objective="SDK contract mission",
        quality_profile="balanced",
        target_posts=5,
    )
    assert payload["run_id"] == "sdk-mission-run"
    assert payload["query_count"] == 1
    assert payload["normalized_spec"]["queries"][0]["input"] == "OpenAI"
    assert payload["batch_plan"]["queries"][0]["input"] == "OpenAI"
    assert payload["outputs"]["raw_jsonl"] == str(output_dir / "raw.jsonl")
    assert payload["outputs"]["manifest"] == str(output_dir / "mission-result.json")


def test_x_reach_client_collect_spec_dry_run_contract(
    client: XReachClient,
    tmp_path: Path,
    assert_mission_plan_envelope,
):
    spec_path = _write_mission_spec(tmp_path / "mission.json")
    output_dir = tmp_path / "mission-output"

    payload = client.collect_spec(
        spec_path,
        output_dir=output_dir,
        run_id="sdk-mission-run",
        dry_run=True,
        query_delay_seconds=1,
        throttle_cooldown_seconds=30,
    )

    assert_mission_plan_envelope(
        payload,
        spec_path=spec_path,
        output_dir=output_dir,
        objective="SDK contract mission",
        quality_profile="balanced",
        target_posts=5,
    )
    assert payload["dry_run"] is True
    assert payload["pacing"]["query_delay_seconds"] == 1
    assert payload["pacing"]["throttle_cooldown_seconds"] == 30
    assert not output_dir.exists()


def _write_candidate_fixture(path: Path) -> Path:
    result = build_result(
        ok=True,
        channel="twitter",
        operation="search",
        items=[
            build_item(
                item_id="tweet-1",
                kind="post",
                title="OpenAI ships a Python SDK contract update",
                url="https://x.com/openai/status/1",
                text="OpenAI ships a Python SDK contract update with stable JSON output.",
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
    record = build_ledger_record(result, run_id="sdk-contract-run", input_value="OpenAI")
    path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _write_mission_spec(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "objective": "SDK contract mission",
                "queries": ["OpenAI"],
                "target_posts": 5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path
