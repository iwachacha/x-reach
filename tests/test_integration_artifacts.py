# -*- coding: utf-8 -*-
"""Tests for repo-shipped integration artifacts."""

import json
from pathlib import Path
from unittest.mock import patch

import yaml

from x_reach.integrations.codex import (
    export_codex_integration,
    render_codex_integration_powershell,
    render_codex_integration_text,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_codex_plugin_manifest_exists_and_is_valid():
    manifest_path = _repo_root() / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "x-reach"
    assert manifest["skills"] == "../x_reach/skills"
    assert "mcpServers" not in manifest
    assert manifest["interface"]["displayName"] == "X Reach"
    assert "Collection" in manifest["interface"]["capabilities"]
    assert len(manifest["interface"]["defaultPrompt"]) == 4


def test_setup_x_reach_action_installs_from_repo_root():
    action_path = _repo_root() / ".github" / "actions" / "setup-x-reach" / "action.yml"
    action_text = action_path.read_text(encoding="utf-8")
    action = yaml.safe_load(action_text)

    assert action["name"] == "Setup X Reach"
    assert action["runs"]["using"] == "composite"
    assert 'repo_root="$(cd "$GITHUB_ACTION_PATH/../../.." && pwd)"' in action_text
    assert 'uv tool install --force "$repo_root"' in action_text
    assert list(action["inputs"]) == ["install-twitter-cli"]
    assert 'uv tool install --force twitter-cli' in action_text


def test_pytest_workflow_runs_lint_type_and_test_gates():
    workflow_path = _repo_root() / ".github" / "workflows" / "pytest.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    workflow = yaml.safe_load(workflow_text)

    assert workflow["name"] == "CI"
    assert set(workflow["on"]) == {"push", "pull_request"}
    assert set(workflow["jobs"]) == {"lint", "typecheck", "test"}
    assert "ruff check ." in workflow_text
    assert "mypy --follow-imports skip" in workflow_text
    assert "x_reach/channels" in workflow_text
    assert "x_reach/candidates.py" in workflow_text
    assert "x_reach/client.py" in workflow_text
    assert "x_reach/core.py" in workflow_text
    assert "x_reach/doctor.py" in workflow_text
    assert "x_reach/integrations/codex.py" in workflow_text
    assert "x_reach/ledger.py" in workflow_text
    assert "x_reach/results.py" in workflow_text
    assert "x_reach/schemas.py" in workflow_text
    assert "x_reach/scout.py" in workflow_text
    assert "agent_reach/cli.py" in workflow_text
    assert "pytest -q" in workflow_text
    assert "windows-latest" in workflow_text
    assert "ubuntu-latest" in workflow_text


def test_x_reach_smoke_workflow_collects_and_uploads_raw_artifacts():
    workflow_path = _repo_root() / ".github" / "workflows" / "x-reach-smoke.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    workflow = yaml.safe_load(workflow_text)

    assert "workflow_dispatch" in workflow["on"]
    assert "uses: ./.github/actions/setup-x-reach" in workflow_text
    assert "install-twitter-cli: \"true\"" in workflow_text
    assert "Capture required smoke contracts" in workflow_text
    assert "Capture observational live smoke outputs" in workflow_text
    assert "x-reach channels --json" in workflow_text
    assert "x-reach doctor --json" in workflow_text
    assert "x-reach doctor --json --probe" in workflow_text
    assert "x-reach collect --json --save" in workflow_text
    assert "|| true" in workflow_text
    assert ": > .x-reach/evidence.jsonl" in workflow_text
    assert "actions/upload-artifact" in workflow_text
    assert ".x-reach/doctor-probe.json" in workflow_text
    assert ".x-reach/twitter.json" in workflow_text
    assert ".x-reach/candidates.json" in workflow_text


def test_downstream_examples_are_collect_only_patterns():
    example_paths = [
        _repo_root() / "examples" / "research-ledger.ps1",
        _repo_root() / "examples" / "discord_news_collect.ps1",
    ]

    for path in example_paths:
        text = path.read_text(encoding="utf-8")
        assert "x-reach collect --json --save" in text
        assert "x-reach plan candidates" in text
        assert ".codex-plugin" not in text
        assert "agent_reach" not in text


def test_export_points_at_existing_checkout_artifacts():
    payload = export_codex_integration()

    assert payload["client"] == "codex"
    assert payload["profile"] == "full"
    assert payload["execution_context"] == "checkout"
    assert payload["plugin_manifest"] is not None
    assert payload["mcp_config"] is None
    assert all(Path(path).exists() for path in payload["recommended_docs"])
    assert any(path.endswith("project-principles.md") for path in payload["recommended_docs"])
    assert any(path.endswith("improvement-plan.md") for path in payload["recommended_docs"])
    channel_contracts = {channel["name"]: channel for channel in payload["channels"]}
    assert list(channel_contracts) == ["twitter"]
    assert channel_contracts["twitter"]["operation_contracts"]["search"]["options"][0]["name"] == "from"
    assert channel_contracts["twitter"]["operation_contracts"]["search"]["options"][-1]["name"] == "quality_profile"
    assert channel_contracts["twitter"]["operation_contracts"]["hashtag"]["input_kind"] == "hashtag"
    assert channel_contracts["twitter"]["probe_operations"] == ["search", "hashtag", "user", "user_posts", "tweet"]
    assert channel_contracts["twitter"]["probe_coverage"] == "full"
    assert payload["skill"]["names"]
    assert Path(payload["skill"]["source"]).exists()
    assert payload["python_sdk"]["availability"] == "project_env_only"
    assert payload["python_sdk"]["import"] == "from x_reach import XReachClient"
    assert any("client.twitter.user_posts" in line for line in payload["python_sdk"]["quickstart"])
    assert payload["readiness_controls"]["doctor_args"][0] == "--require-channel <name>"
    assert payload["external_project_usage"]["preferred_interface"] == "x-reach collect --json"
    assert payload["codex_runtime_policy"]["default_interface"] == "x-reach collect --json"
    assert any(command.startswith("x-reach collect ") for command in payload["verification_commands"])


def test_export_runtime_minimal_omits_bootstrap_payloads():
    payload = export_codex_integration(profile="runtime-minimal")

    assert payload["client"] == "codex"
    assert payload["profile"] == "runtime-minimal"
    assert "channels" not in payload
    assert payload["channel_names"] == ["twitter"]
    assert any("--profile runtime-minimal" in command for command in payload["verification_commands"])
    assert any("runtime-minimal omits full channel contracts" in note for note in payload["notes"])
    assert any("Python SDK quickstart" in note for note in payload["notes"])


def test_export_renderers_support_twitter_only_payload():
    payload = export_codex_integration()

    text = render_codex_integration_text(payload)
    powershell = render_codex_integration_powershell(payload)

    assert "Channels: twitter" in text
    assert "x-reach collect --operation search" in text
    assert "$pluginManifestJson = @'" in powershell
    assert "$mcpConfigJson = $null" in powershell
    assert "x-reach doctor --json --probe" in powershell


def test_export_tool_install_omits_dead_paths(tmp_path):
    fake_repo_root = tmp_path / "site-packages"
    fake_repo_root.mkdir(parents=True)

    with patch("x_reach.integrations.codex._repo_root", return_value=fake_repo_root), patch(
        "x_reach.integrations.codex._current_working_dir",
        return_value=tmp_path / "consumer-project",
    ):
        payload = export_codex_integration()

    assert payload["execution_context"] == "tool_install"
    assert payload["plugin_manifest"] is None
    assert payload["mcp_config"] is None
    assert payload["recommended_docs"] == []
    assert payload["plugin_manifest_inline"]["name"] == "x-reach"
    assert payload["mcp_config_inline"] is None
    assert payload["external_project_usage"]["github_actions"]["uses"].startswith("iwachacha/x-reach/")

