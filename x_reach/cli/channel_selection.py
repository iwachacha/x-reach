# -*- coding: utf-8 -*-
"""Helpers for stable channel name parsing and doctor requirements."""

from __future__ import annotations

from collections.abc import Sequence


def all_channel_names() -> list[str]:
    from x_reach.channels import get_all_channel_contracts

    return [contract["name"] for contract in get_all_channel_contracts()]


def parse_channel_names(
    raw: str,
    *,
    supported_channels: Sequence[str],
    allow_all: bool = False,
) -> list[str]:
    items = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not items:
        return []
    normalized_supported = list(supported_channels)
    if allow_all and "all" in items:
        return normalized_supported

    supported_set = set(normalized_supported)
    invalid = [item for item in items if item not in supported_set]
    if invalid:
        supported_values = normalized_supported + (["all"] if allow_all else [])
        supported = ", ".join(supported_values)
        raise SystemExit(f"Unsupported channel(s): {', '.join(invalid)}. Supported values: {supported}")
    normalized: list[str] = []
    for item in items:
        if item not in normalized:
            normalized.append(item)
    return normalized


def parse_requested_channels(raw: str) -> list[str]:
    return parse_channel_names(
        raw,
        supported_channels=all_channel_names(),
        allow_all=True,
    )


def resolve_doctor_requirements(args) -> tuple[list[str], bool]:
    supported_channels = all_channel_names()
    required: list[str] = []
    for name in args.require_channel or []:
        parsed = parse_channel_names(name, supported_channels=supported_channels, allow_all=False)
        for item in parsed:
            if item not in required:
                required.append(item)
    if args.require_channels:
        parsed = parse_channel_names(
            args.require_channels,
            supported_channels=supported_channels,
            allow_all=False,
        )
        for item in parsed:
            if item not in required:
                required.append(item)
    return required, bool(args.require_all)
