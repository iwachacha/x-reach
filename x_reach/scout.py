# -*- coding: utf-8 -*-
"""Capability-only scout helpers for the Twitter-only fork."""

from __future__ import annotations

from typing import Any

from x_reach.channels import get_all_channel_contracts
from x_reach.config import Config
from x_reach.doctor import check_all
from x_reach.high_signal import (
    DEFAULT_BROAD_ITEM_TEXT_MAX_CHARS,
    DEFAULT_BROAD_ITEM_TEXT_MODE,
    DEFAULT_BROAD_RAW_MODE,
)
from x_reach.schemas import SCHEMA_VERSION, utc_timestamp

BUDGETS = ("auto", "small", "medium", "large", "xlarge")
QUALITY_PROFILES = ("precision", "balanced", "recall")
PRESETS = ("social-pulse", "timeline-check")

_PRESET_CHANNELS = {
    "social-pulse": ("twitter",),
    "timeline-check": ("twitter",),
}


class ScoutPlanError(Exception):
    """Raised when scout plan input is invalid."""


def build_scout_plan(
    topic: str,
    *,
    budget: str = "auto",
    quality: str = "precision",
    preset: str | None = None,
    config: Config | None = None,
) -> dict[str, Any]:
    """Build a network-free capability snapshot for external callers."""

    text = topic.strip()
    if not text:
        raise ScoutPlanError("topic must not be empty")
    if budget not in BUDGETS:
        raise ScoutPlanError(f"Unsupported budget: {budget}")
    if quality not in QUALITY_PROFILES:
        raise ScoutPlanError(f"Unsupported quality profile: {quality}")
    if preset is not None and preset not in PRESETS:
        raise ScoutPlanError(f"Unsupported preset: {preset}")

    config = config or Config()
    contracts = get_all_channel_contracts()
    readiness = check_all(config, probe=False)

    available_channels: list[dict[str, Any]] = []
    ready_channels: list[str] = []
    not_ready_channels: list[dict[str, str]] = []
    for contract in contracts:
        channel_payload = readiness.get(contract["name"], {})
        available_channels.append(
            {
                "channel": contract["name"],
                "description": contract["description"],
                "operations": contract.get("operations", []),
                "operation_contracts": contract.get("operation_contracts", {}),
                "supports_probe": contract.get("supports_probe", False),
                "probe_operations": contract.get("probe_operations", []),
                "probe_coverage": contract.get("probe_coverage", "none"),
                "status": channel_payload.get("status", "unknown"),
                "message": channel_payload.get("message", ""),
                "probed_operations": channel_payload.get("probed_operations", []),
                "unprobed_operations": channel_payload.get("unprobed_operations", []),
                "probe_run_coverage": channel_payload.get("probe_run_coverage", "not_run"),
            }
        )
        if channel_payload.get("status") == "ok":
            ready_channels.append(contract["name"])
        else:
            not_ready_channels.append(
                {
                    "channel": contract["name"],
                    "status": channel_payload.get("status", "unknown"),
                    "message": channel_payload.get("message", ""),
                }
            )

    known_channels = {contract["name"] for contract in contracts}
    preset_channels = _PRESET_CHANNELS[preset] if preset is not None else ()
    unknown_seed_channels = [channel for channel in preset_channels if channel not in known_channels]
    if unknown_seed_channels:
        raise ScoutPlanError(
            "Preset references unknown channel(s): "
            + ", ".join(unknown_seed_channels)
        )
    seed_channels = list(preset_channels)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "command": "scout",
        "plan_only": True,
        "topic": text,
        "budget": budget,
        "budget_requested": budget,
        "quality_profile": quality,
        "preset": preset,
        "available_channels": available_channels,
        "ready_channels": ready_channels,
        "not_ready_channels": not_ready_channels,
        "seed_channels": seed_channels,
        "required_readiness_checks": _readiness_checks(available_channels),
        "recommended_collection_settings": _recommended_collection_settings(quality),
    }


def render_scout_text(payload: dict[str, Any]) -> str:
    """Render a capability snapshot for humans."""

    lines = [
        "X Reach Scout Capability Snapshot",
        "========================================",
        f"Topic: {payload['topic']}",
        f"Budget hint: {payload['budget']}",
        f"Quality: {payload['quality_profile']}",
        f"Ready channels: {', '.join(payload['ready_channels']) or 'none'}",
    ]
    if payload["seed_channels"]:
        lines.append(f"Seed channels: {', '.join(payload['seed_channels'])}")
    recommended = payload.get("recommended_collection_settings") or {}
    if recommended:
        lines.append(
            "Discovery defaults: "
            f"quality_profile={recommended.get('quality_profile')} "
            f"raw_mode={recommended.get('raw_mode')} "
            f"item_text_mode={recommended.get('item_text_mode')} "
            f"item_text_max_chars={recommended.get('item_text_max_chars')}"
        )
    if payload["not_ready_channels"]:
        lines.append("Not ready:")
        for channel in payload["not_ready_channels"]:
            lines.append(f"  - {channel['channel']}: {channel['status']} - {channel['message']}")
    return "\n".join(lines)


def _readiness_checks(channels: list[dict[str, Any]]) -> list[str]:
    checks = ["x-reach channels --json", "x-reach doctor --json"]
    if any(channel.get("supports_probe") for channel in channels):
        checks.append("x-reach doctor --json --probe")
    return checks


def _recommended_collection_settings(quality: str) -> dict[str, Any]:
    deep_read_defaults = {
        "raw_mode": "full",
        "item_text_mode": "full",
        "candidate_limit": 10 if quality == "precision" else 20,
    }
    return {
        "quality_profile": quality,
        "raw_mode": DEFAULT_BROAD_RAW_MODE,
        "item_text_mode": DEFAULT_BROAD_ITEM_TEXT_MODE,
        "item_text_max_chars": DEFAULT_BROAD_ITEM_TEXT_MAX_CHARS,
        "deep_read_defaults": deep_read_defaults,
    }


