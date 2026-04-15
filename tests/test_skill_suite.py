# -*- coding: utf-8 -*-
"""Tests for the bundled Agent Reach skill suite."""

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _skill_dir(name: str) -> Path:
    return _repo_root() / "agent_reach" / "skills" / name


def test_public_agent_reach_skills_require_explicit_opt_in():
    base_skill = (_skill_dir("agent-reach") / "SKILL.md").read_text(encoding="utf-8")
    base_metadata = (_skill_dir("agent-reach") / "agents" / "openai.yaml").read_text(encoding="utf-8")
    budgeted_skill = (_skill_dir("agent-reach-budgeted-research") / "SKILL.md").read_text(encoding="utf-8")
    orchestrate_skill = (_skill_dir("agent-reach-orchestrate") / "SKILL.md").read_text(encoding="utf-8")

    assert "explicitly asks to use Agent Reach" in base_skill
    assert "native browsing/search" in base_skill
    assert "`twitter`" in base_skill
    assert "explicitly asks for Agent Reach" in base_metadata
    assert "explicitly asks to use Agent Reach" in budgeted_skill
    assert "Do not start collection here." in budgeted_skill
    assert "explicitly asks to use Agent Reach" in orchestrate_skill


def test_orchestrate_references_cover_collection_start_rules():
    skill = (_skill_dir("agent-reach-orchestrate") / "SKILL.md").read_text(encoding="utf-8")
    flow = (_skill_dir("agent-reach-orchestrate") / "references" / "orchestration-flow.md").read_text(
        encoding="utf-8"
    )
    routing = (_skill_dir("agent-reach-orchestrate") / "references" / "routing-guides.md").read_text(
        encoding="utf-8"
    )
    examples = (_skill_dir("agent-reach-orchestrate") / "references" / "examples.md").read_text(
        encoding="utf-8"
    )

    assert "Start actual Agent Reach checks and collection in-session." in skill
    assert "run `agent-reach channels --json`" in flow
    assert "run `agent-reach doctor --json`" in flow
    assert "agent-reach collect --json" in flow
    assert "`twitter`" in routing
    assert "plan candidates" in examples


def test_budgeted_research_skill_has_budget_examples():
    skill = (_skill_dir("agent-reach-budgeted-research") / "SKILL.md").read_text(encoding="utf-8")
    examples = (_skill_dir("agent-reach-budgeted-research") / "references" / "examples.md").read_text(
        encoding="utf-8"
    )

    assert "bounded execution plan" in skill
    assert "Twitter/X" in examples


def test_maintainer_release_skill_has_shipping_guardrails():
    skill = (_skill_dir("agent-reach-maintain-release") / "SKILL.md").read_text(encoding="utf-8")
    boundaries = (_skill_dir("agent-reach-maintain-release") / "references" / "change-boundaries.md").read_text(
        encoding="utf-8"
    )
    flow = (_skill_dir("agent-reach-maintain-release") / "references" / "release-flow.md").read_text(
        encoding="utf-8"
    )

    assert "commit, push, or reinstall" in skill
    assert "Must-Stay-True Rules" in boundaries
    assert "twitter-reach.git" in flow
