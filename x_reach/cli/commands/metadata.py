# -*- coding: utf-8 -*-
"""Metadata-oriented CLI commands such as channels, schema, export, and version."""

from __future__ import annotations

import argparse
import json
import sys

from x_reach import __version__
from x_reach.cli.common import print_json
from x_reach.cli.renderers.channels import render_channels_text
from x_reach.schemas import (
    SCHEMA_VERSION,
    collection_result_schema,
    judge_result_schema,
    mission_spec_schema,
    utc_timestamp,
)


def register_metadata_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p_channels = subparsers.add_parser("channels", help="Show the stable channel registry")
    p_channels.add_argument("name", nargs="?", help="Optional stable channel name to inspect")
    p_channels.add_argument("--json", action="store_true", help="Print machine-readable channel data")
    p_channels.set_defaults(handler=handle_channels)

    p_schema = subparsers.add_parser("schema", help="Print packaged JSON Schemas for stable contracts")
    p_schema.add_argument(
        "name",
        choices=["collection-result", "mission-spec", "judge-result"],
        help="Schema name to print",
    )
    p_schema.add_argument("--json", action="store_true", help="Print the JSON Schema payload")
    p_schema.set_defaults(handler=handle_schema)

    p_export = subparsers.add_parser(
        "export-integration",
        help="Export non-mutating integration data for downstream clients",
    )
    p_export.add_argument("--client", choices=["codex"], required=True, help="Target client")
    p_export.add_argument(
        "--format",
        choices=["text", "json", "powershell"],
        default="text",
        help="Output format for the integration export",
    )
    p_export.add_argument(
        "--profile",
        choices=["full", "runtime-minimal"],
        default="full",
        help="Export profile. runtime-minimal is only supported with --format json",
    )
    p_export.set_defaults(handler=handle_export_integration)

    p_version = subparsers.add_parser("version", help="Show the current X Reach version")
    p_version.set_defaults(handler=handle_version)


def handle_version(_args) -> int:
    print(f"X Reach v{__version__}")
    return 0


def handle_channels(args) -> int:
    from x_reach.channels import get_all_channel_contracts, get_channel_contract

    if args.name:
        contract = get_channel_contract(args.name)
        if contract is None:
            print(f"Unknown channel: {args.name}", file=sys.stderr)
            return 2
        if args.json:
            print_json(
                {
                    "schema_version": SCHEMA_VERSION,
                    "generated_at": utc_timestamp(),
                    "channel": contract,
                }
            )
        else:
            print(render_channels_text([contract]))
        return 0

    contracts = get_all_channel_contracts()
    if args.json:
        print_json(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": utc_timestamp(),
                "channels": contracts,
            }
        )
    else:
        print(render_channels_text(contracts))
    return 0


def handle_schema(args) -> int:
    if args.name == "collection-result":
        payload = collection_result_schema()
    elif args.name == "mission-spec":
        payload = mission_spec_schema()
    elif args.name == "judge-result":
        payload = judge_result_schema()
    else:
        print(f"Unknown schema: {args.name}", file=sys.stderr)
        return 2
    if args.json:
        print_json(payload)
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def handle_export_integration(args) -> int:
    from x_reach.integrations.codex import (
        export_codex_integration,
        render_codex_integration_powershell,
        render_codex_integration_text,
    )

    if args.profile != "full" and args.format != "json":
        print("export-integration profiles other than full are only supported with --format json", file=sys.stderr)
        return 2

    payload = export_codex_integration(profile=args.profile)
    if args.format == "json":
        print_json(payload)
    elif args.format == "powershell":
        print(render_codex_integration_powershell(payload))
    else:
        print(render_codex_integration_text(payload))
    return 0
