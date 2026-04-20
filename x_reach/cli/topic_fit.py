# -*- coding: utf-8 -*-
"""Shared topic-fit argument loading for CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

from x_reach.candidates import CandidatePlanError


def load_topic_fit_arg(path: str | None) -> dict | None:
    if path is None:
        return None
    topic_fit_path = Path(path)
    try:
        payload = json.loads(topic_fit_path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise CandidatePlanError(f"Could not read topic-fit rules: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CandidatePlanError(f"Invalid topic-fit JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise CandidatePlanError("topic-fit JSON must be an object")
    nested = payload.get("topic_fit")
    if nested is not None:
        if not isinstance(nested, dict):
            raise CandidatePlanError("topic_fit must be an object")
        return nested
    return payload
