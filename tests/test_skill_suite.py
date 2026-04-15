# -*- coding: utf-8 -*-
"""Tests for the bundled X Reach skill suite."""

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _skill_dir(name: str) -> Path:
    return _repo_root() / "x_reach" / "skills" / name


def test_public_x_reach_skills_require_explicit_opt_in():
    base_skill = (_skill_dir("x-reach") / "SKILL.md").read_text(encoding="utf-8")
    base_metadata = (_skill_dir("x-reach") / "agents" / "openai.yaml").read_text(encoding="utf-8")
    budgeted_skill = (_skill_dir("x-reach-budgeted-research") / "SKILL.md").read_text(encoding="utf-8")
    orchestrate_skill = (_skill_dir("x-reach-orchestrate") / "SKILL.md").read_text(encoding="utf-8")

    assert "explicitly asks to use X Reach" in base_skill
    assert "native browsing/search" in base_skill
    assert "`twitter`" in base_skill
    assert "explicitly asks for X Reach" in base_metadata
    assert "explicitly asks to use X Reach" in budgeted_skill
    assert "Do not start collection here." in budgeted_skill
    assert "explicitly asks to use X Reach" in orchestrate_skill


def test_orchestrate_references_cover_collection_start_rules():
    skill = (_skill_dir("x-reach-orchestrate") / "SKILL.md").read_text(encoding="utf-8")
    flow = (_skill_dir("x-reach-orchestrate") / "references" / "orchestration-flow.md").read_text(
        encoding="utf-8"
    )
    routing = (_skill_dir("x-reach-orchestrate") / "references" / "routing-guides.md").read_text(
        encoding="utf-8"
    )
    examples = (_skill_dir("x-reach-orchestrate") / "references" / "examples.md").read_text(
        encoding="utf-8"
    )

    assert "Start actual X Reach checks and collection in-session." in skill
    assert "run `x-reach channels --json`" in flow
    assert "run `x-reach doctor --json`" in flow
    assert "x-reach collect --json" in flow
    assert "`twitter`" in routing
    assert "plan candidates" in examples


def test_budgeted_research_skill_has_budget_examples():
    skill = (_skill_dir("x-reach-budgeted-research") / "SKILL.md").read_text(encoding="utf-8")
    examples = (_skill_dir("x-reach-budgeted-research") / "references" / "examples.md").read_text(
        encoding="utf-8"
    )

    assert "bounded execution plan" in skill
    assert "Twitter/X" in examples


def test_maintainer_release_skill_has_shipping_guardrails():
    skill = (_skill_dir("x-reach-maintain-release") / "SKILL.md").read_text(encoding="utf-8")
    boundaries = (_skill_dir("x-reach-maintain-release") / "references" / "change-boundaries.md").read_text(
        encoding="utf-8"
    )
    flow = (_skill_dir("x-reach-maintain-release") / "references" / "release-flow.md").read_text(
        encoding="utf-8"
    )

    assert "commit, push, or reinstall" in skill
    assert "Must-Stay-True Rules" in boundaries
    assert "x-reach.git" in flow

