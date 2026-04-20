# -*- coding: utf-8 -*-
"""Plan command handlers."""

from __future__ import annotations

import argparse
import sys

from x_reach.candidates import CandidatePlanError, build_candidates_payload, render_candidates_text
from x_reach.cli.common import print_json
from x_reach.cli.options import add_plan_candidates_args
from x_reach.cli.topic_fit import load_topic_fit_arg
from x_reach.schemas import SCHEMA_VERSION, utc_timestamp


def register_plan_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("plan", help="Build lightweight plans from evidence ledgers")
    parser.set_defaults(handler=_handle_missing_plan_subcommand)
    plan_sub = parser.add_subparsers(dest="plan_command", help="Planning commands")
    p_candidates = plan_sub.add_parser(
        "candidates",
        help="Return deduped candidates for follow-up reads",
    )
    add_plan_candidates_args(p_candidates)
    p_candidates.set_defaults(handler=handle_plan_candidates)


def _handle_missing_plan_subcommand(_args) -> int:
    print("plan requires a subcommand", file=sys.stderr)
    return 2


def handle_plan_candidates(args) -> int:
    if args.limit < 1:
        print("limit must be greater than or equal to 1", file=sys.stderr)
        return 2
    if args.max_per_author is not None and args.max_per_author < 1:
        print("max-per-author must be greater than or equal to 1", file=sys.stderr)
        return 2
    if args.min_seen_in is not None and args.min_seen_in < 1:
        print("min-seen-in must be greater than or equal to 1", file=sys.stderr)
        return 2
    try:
        topic_fit = load_topic_fit_arg(args.topic_fit)
    except CandidatePlanError as exc:
        if args.json:
            print_json(_candidate_error_payload(args, str(exc)))
            return 2
        print(f"Could not plan candidates: {exc}", file=sys.stderr)
        return 2
    try:
        payload = build_candidates_payload(
            args.input,
            by=args.by,
            limit=args.limit,
            summary_only=args.summary_only,
            fields=args.fields,
            max_per_author=args.max_per_author,
            prefer_originals=args.prefer_originals,
            drop_noise=args.drop_noise,
            drop_title_duplicates=args.drop_title_duplicates,
            require_query_match=args.require_query_match,
            min_seen_in=args.min_seen_in,
            sort_by=args.sort_by,
            topic_fit=topic_fit,
        )
    except CandidatePlanError as exc:
        if args.json:
            print_json(_candidate_error_payload(args, str(exc)))
            return 2
        print(f"Could not plan candidates: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print_json(payload)
    else:
        print(render_candidates_text(payload))
    return 0


def _candidate_error_payload(args, message: str) -> dict:
    fields = None
    if args.fields is not None:
        fields = [item.strip() for item in args.fields.split(",") if item.strip()]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "command": "plan candidates",
        "ok": False,
        "input": args.input,
        "by": args.by,
        "sort_by": args.sort_by,
        "limit": args.limit,
        "summary_only": bool(args.summary_only),
        "fields": fields,
        "max_per_author": args.max_per_author,
        "prefer_originals": bool(args.prefer_originals),
        "drop_noise": bool(args.drop_noise),
        "drop_title_duplicates": bool(args.drop_title_duplicates),
        "require_query_match": bool(args.require_query_match),
        "topic_fit": args.topic_fit,
        "min_seen_in": args.min_seen_in,
        "candidates": [],
        "error": {
            "code": "candidate_plan_error",
            "message": message,
        },
    }
