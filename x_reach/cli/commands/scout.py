# -*- coding: utf-8 -*-
"""Scout command handler."""

from __future__ import annotations

import argparse
import sys

from x_reach.cli.common import print_json
from x_reach.cli.options import add_scout_args
from x_reach.schemas import SCHEMA_VERSION, utc_timestamp
from x_reach.scout import ScoutPlanError, build_scout_plan, render_scout_text


def register_scout_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("scout", help="Build an opt-in plan-only capability snapshot")
    add_scout_args(parser)
    parser.set_defaults(handler=handle_scout)


def _scout_error_payload(args, message: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "command": "scout",
        "plan_only": bool(args.plan_only),
        "topic": args.topic,
        "budget": args.budget,
        "budget_requested": args.budget,
        "quality_profile": args.quality,
        "preset": args.preset,
        "available_channels": [],
        "ready_channels": [],
        "not_ready_channels": [],
        "seed_channels": [],
        "required_readiness_checks": [],
        "error": {
            "code": "scout_plan_error",
            "message": message,
        },
    }


def handle_scout(args) -> int:
    if not args.plan_only:
        message = "scout currently requires --plan-only"
        if args.json:
            print_json(_scout_error_payload(args, message))
        else:
            print(message, file=sys.stderr)
        return 2
    try:
        payload = build_scout_plan(
            args.topic,
            budget=args.budget,
            quality=args.quality,
            preset=args.preset,
        )
    except ScoutPlanError as exc:
        message = f"Could not build scout plan: {exc}"
        if args.json:
            print_json(_scout_error_payload(args, message))
        else:
            print(message, file=sys.stderr)
        return 2
    if args.json:
        print_json(payload)
    else:
        print(render_scout_text(payload))
    return 0
