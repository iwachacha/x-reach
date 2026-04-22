# -*- coding: utf-8 -*-
"""Pytest test-path bootstrap and shared contract assertions."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
ROOT_TEXT = str(ROOT)
if ROOT_TEXT in sys.path:
    sys.path.remove(ROOT_TEXT)
sys.path.insert(0, ROOT_TEXT)

_MISSION_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "generated_at",
    "command",
    "cli_version",
    "dry_run",
    "spec",
    "output_dir",
    "run_id",
    "objective",
    "quality_profile",
    "target_posts",
    "topic_fit",
    "pacing",
    "judge",
    "query_count",
    "normalized_spec",
    "batch_plan",
    "outputs",
}
_MISSION_PLAN_REQUIRED_OUTPUTS = {
    "raw_jsonl",
    "canonical_jsonl",
    "ranked_jsonl",
    "manifest",
}
_CANDIDATE_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "generated_at",
    "command",
    "input",
    "by",
    "sort_by",
    "summary",
    "topic_fit",
    "candidates",
}


def assert_mission_plan_envelope_payload(
    payload: dict[str, Any],
    *,
    spec_path: Path,
    output_dir: Path,
    objective: str | None = None,
    quality_profile: str | None = None,
    target_posts: int | None = None,
) -> None:
    """Assert the public dry-run mission plan envelope without freezing additive fields."""

    assert _MISSION_PLAN_REQUIRED_KEYS.issubset(payload)
    assert payload["schema_version"]
    assert payload["generated_at"]
    assert payload["command"] == "collect spec"
    assert payload["cli_version"]
    assert payload["dry_run"] is True
    assert payload["spec"] == str(spec_path)
    assert payload["output_dir"] == str(output_dir)
    assert payload["run_id"]
    if objective is not None:
        assert payload["objective"] == objective
    if quality_profile is not None:
        assert payload["quality_profile"] == quality_profile
    if target_posts is not None:
        assert payload["target_posts"] == target_posts
    assert isinstance(payload["topic_fit"], dict)
    assert isinstance(payload["pacing"], dict)
    assert isinstance(payload["judge"], dict)
    assert isinstance(payload["query_count"], int)
    assert isinstance(payload["normalized_spec"], dict)
    assert isinstance(payload["batch_plan"], dict)
    assert isinstance(payload["outputs"], dict)
    assert _MISSION_PLAN_REQUIRED_OUTPUTS.issubset(payload["outputs"])


def assert_candidate_plan_quality_contract_payload(payload: dict[str, Any]) -> None:
    """Assert candidate planning quality diagnostics without freezing additive fields."""

    assert _CANDIDATE_PLAN_REQUIRED_KEYS.issubset(payload)
    assert payload["command"] == "plan candidates"
    assert isinstance(payload["summary"], dict)
    assert isinstance(payload["topic_fit"], dict)
    assert isinstance(payload["candidates"], list)

    summary = payload["summary"]
    assert isinstance(summary.get("quality_reason_counts"), dict)
    quality_diagnostics = summary.get("quality_diagnostics")
    assert isinstance(quality_diagnostics, dict)
    assert quality_diagnostics["scoring_version"] == "deterministic_evidence_v2"
    assert isinstance(quality_diagnostics["scored_candidates"], int)
    assert quality_diagnostics["reason_counts"] == summary["quality_reason_counts"]

    for candidate in payload["candidates"]:
        assert isinstance(candidate.get("quality_score"), (int, float))
        assert isinstance(candidate.get("quality_reasons"), list)
        assert all(isinstance(reason, str) for reason in candidate["quality_reasons"])


@pytest.fixture()
def assert_mission_plan_envelope() -> Callable[..., None]:
    return assert_mission_plan_envelope_payload


@pytest.fixture()
def assert_candidate_plan_quality_contract() -> Callable[[dict[str, Any]], None]:
    return assert_candidate_plan_quality_contract_payload
