# -*- coding: utf-8 -*-
"""Tests that lock in repository cleanup decisions."""

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_legacy_files_are_removed():
    repo_root = _repo_root()

    assert not (repo_root / ".mcp.json").exists()
    assert not (repo_root / ".github" / "actions" / "setup-agent-reach").exists()
    assert not (repo_root / ".github" / "workflows" / "agent-reach-smoke.yml").exists()
    assert not (repo_root / "agent_reach" / "channels" / "github.py").exists()
    assert not (repo_root / "agent_reach" / "channels" / "web.py").exists()
    assert not (repo_root / "agent_reach" / "adapters" / "reddit.py").exists()
    assert not (repo_root / "agent_reach" / "skills").exists()
    assert not (repo_root / "agent_reach" / "source_hints.py").exists()
    assert not (repo_root / "agent_reach" / "extraction_hygiene.py").exists()
    assert not (repo_root / "agent_reach" / "utils" / "paths.py").exists()
    assert not (repo_root / "x_reach" / "skills" / "x-reach" / "references" / "search.md").exists()


def test_docs_folder_only_contains_supported_docs():
    docs_dir = _repo_root() / "docs"
    names = {path.name for path in docs_dir.iterdir()}

    expected_docs = {
        "codex-integration.md",
        "downstream-usage.md",
        "install.md",
        "python-sdk.md",
        "troubleshooting.md",
    }

    assert names == expected_docs


def test_llms_txt_points_at_current_fork_docs():
    llms = (_repo_root() / "llms.txt").read_text(encoding="utf-8")

    assert "github.com/iwachacha/twitter-reach/blob/main/docs/install.md" in llms
    assert "github.com/iwachacha/Agent-Reach/blob/main/" not in llms
    assert "twitter" in llms


def test_caller_control_policy_is_documented_consistently():
    repo_root = _repo_root()
    files = {
        "readme": repo_root / "README.md",
        "skill": repo_root / "x_reach" / "skills" / "x-reach" / "SKILL.md",
        "agent_prompt": repo_root / "x_reach" / "skills" / "x-reach" / "agents" / "openai.yaml",
    }

    texts = {name: path.read_text(encoding="utf-8") for name, path in files.items()}

    assert "X Reach does not choose" in texts["readme"]
    assert "auto-escalate" in texts["readme"]
    assert "explicit opt-in" in texts["readme"]
    assert "--limit 20" in texts["readme"]

    assert "The caller chooses scale" in texts["skill"]
    assert "auto-escalate" in texts["skill"]
    assert "explicit opt-in" in texts["skill"]
    assert "--limit 20" in texts["skill"]

    assert "does not choose scope" in texts["agent_prompt"]


def test_skill_suite_files_exist():
    repo_root = _repo_root()
    suite_root = repo_root / "x_reach" / "skills"
    expected = [
        "x-reach",
        "x-reach-shape-brief",
        "x-reach-budgeted-research",
        "x-reach-orchestrate",
        "x-reach-propose-improvements",
        "x-reach-maintain-proposals",
        "x-reach-maintain-release",
    ]

    for skill_name in expected:
        skill_dir = suite_root / skill_name
        assert (skill_dir / "SKILL.md").exists()
        assert (skill_dir / "agents" / "openai.yaml").exists()

