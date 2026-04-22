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


@pytest.fixture()
def assert_mission_plan_envelope() -> Callable[..., None]:
    return assert_mission_plan_envelope_payload
