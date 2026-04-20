# -*- coding: utf-8 -*-
"""Batch command handler."""

from __future__ import annotations

import argparse
import sys

from x_reach.batch import BatchPlanError, render_batch_text, run_batch_plan, validate_batch_plan
from x_reach.cli.common import print_json
from x_reach.cli.options import add_batch_args
from x_reach.schemas import SCHEMA_VERSION, utc_timestamp


def register_batch_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("batch", help="Run or validate a bounded batch collection plan")
    add_batch_args(parser)
    parser.set_defaults(handler=handle_batch)


def _batch_error_payload(args, message: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "command": "batch",
        "validate_only": bool(args.validate_only),
        "valid": False,
        "plan": args.plan,
        "save": args.save,
        "save_dir": args.save_dir,
        "failure_policy": None,
        "quality_profile": args.quality,
        "pacing": {
            "query_delay_seconds": args.query_delay_seconds,
            "query_jitter_seconds": args.query_jitter_seconds,
            "throttle_cooldown_seconds": args.throttle_cooldown_seconds,
            "throttle_error_limit": args.throttle_error_limit,
        },
        "summary": None,
        "error": {
            "code": "batch_plan_error",
            "message": message,
        },
    }


def handle_batch(args) -> int:
    if args.shard_by and not args.save_dir:
        print("shard-by is only supported with --save-dir", file=sys.stderr)
        return 2
    if args.validate_only:
        if args.resume:
            print("resume is not supported with --validate-only", file=sys.stderr)
            return 2
        try:
            payload = validate_batch_plan(
                args.plan,
                quality=args.quality,
                query_delay_seconds=args.query_delay_seconds,
                query_jitter_seconds=args.query_jitter_seconds,
                throttle_cooldown_seconds=args.throttle_cooldown_seconds,
                throttle_error_limit=args.throttle_error_limit,
            )
        except BatchPlanError as exc:
            if args.json:
                print_json(_batch_error_payload(args, str(exc)))
            else:
                print(f"Could not validate batch plan: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print_json(payload)
        else:
            print(render_batch_text(payload))
        return 0
    if not args.save and not args.save_dir:
        print("batch requires --save or --save-dir unless --validate-only is set", file=sys.stderr)
        return 2
    try:
        payload, exit_code = run_batch_plan(
            args.plan,
            save_path=args.save,
            save_dir=args.save_dir,
            shard_by=args.shard_by or "channel",
            concurrency=args.concurrency,
            resume=args.resume,
            checkpoint_every=args.checkpoint_every,
            quality=args.quality,
            query_delay_seconds=args.query_delay_seconds,
            query_jitter_seconds=args.query_jitter_seconds,
            throttle_cooldown_seconds=args.throttle_cooldown_seconds,
            throttle_error_limit=args.throttle_error_limit,
        )
    except BatchPlanError as exc:
        print(f"Could not run batch plan: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print_json(payload)
    else:
        print(render_batch_text(payload))
    return exit_code
