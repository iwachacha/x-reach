# -*- coding: utf-8 -*-
"""Shared schema helpers for machine-readable X Reach output."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib.resources import files

SCHEMA_VERSION = "2026-04-10"


def utc_timestamp() -> str:
    """Return an RFC3339 UTC timestamp for JSON payloads."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def collection_result_schema() -> dict:
    """Return the packaged JSON Schema for CollectionResult envelopes."""

    return _read_schema("collection_result.schema.json")


def mission_spec_schema() -> dict:
    """Return the packaged JSON Schema for mission specs."""

    return _read_schema("mission_spec.schema.json")


def judge_result_schema() -> dict:
    """Return the packaged JSON Schema for judge result records."""

    return _read_schema("judge_result.schema.json")


def _read_schema(name: str) -> dict:
    text = files("x_reach.schema_files").joinpath(name).read_text(encoding="utf-8-sig")
    return json.loads(text)

