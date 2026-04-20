# -*- coding: utf-8 -*-
"""Ledger command handlers."""

from __future__ import annotations

import argparse
import sys

from x_reach.cli.common import print_json
from x_reach.cli.options import (
    add_ledger_append_args,
    add_ledger_merge_args,
    add_ledger_query_args,
    add_ledger_summarize_args,
    add_ledger_validate_args,
)
from x_reach.cli.renderers.ledger import (
    render_ledger_append_text,
    render_ledger_merge_text,
    render_ledger_query_text,
    render_ledger_summarize_text,
    render_ledger_validate_text,
)
from x_reach.ledger import (
    append_result_json,
    default_run_id,
    merge_ledger_inputs,
    query_ledger_input,
    summarize_ledger_input,
    validate_ledger_input,
)


def register_ledger_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("ledger", help="Manage evidence ledger files")
    parser.set_defaults(handler=_handle_missing_ledger_subcommand)
    ledger_sub = parser.add_subparsers(dest="ledger_command", help="Ledger commands")

    p_merge = ledger_sub.add_parser("merge", help="Merge a ledger file or shard directory into one JSONL file")
    add_ledger_merge_args(p_merge)
    p_merge.set_defaults(handler=handle_ledger_merge)

    p_validate = ledger_sub.add_parser("validate", help="Validate a ledger file or shard directory")
    add_ledger_validate_args(p_validate)
    p_validate.set_defaults(handler=handle_ledger_validate)

    p_summarize = ledger_sub.add_parser("summarize", help="Summarize evidence ledger health counts")
    add_ledger_summarize_args(p_summarize)
    p_summarize.set_defaults(handler=handle_ledger_summarize)

    p_query = ledger_sub.add_parser("query", help="Filter evidence ledger records")
    add_ledger_query_args(p_query)
    p_query.set_defaults(handler=handle_ledger_query)

    p_append = ledger_sub.add_parser("append", help="Append a CollectionResult JSON file to a ledger")
    add_ledger_append_args(p_append)
    p_append.set_defaults(handler=handle_ledger_append)


def _handle_missing_ledger_subcommand(_args) -> int:
    print("ledger requires a subcommand", file=sys.stderr)
    return 2


def handle_ledger_merge(args) -> int:
    try:
        payload = merge_ledger_inputs(args.input, args.output)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Could not merge ledgers: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print_json(payload)
    else:
        print(render_ledger_merge_text(payload))
    return 0


def handle_ledger_validate(args) -> int:
    try:
        payload = validate_ledger_input(args.input, require_metadata=args.require_metadata)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Could not validate ledger: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print_json(payload)
    else:
        print(render_ledger_validate_text(payload))
    return 0 if payload["valid"] else 1


def handle_ledger_summarize(args) -> int:
    try:
        payload = summarize_ledger_input(args.input, filters=list(args.filter or []))
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Could not summarize ledger: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print_json(payload)
    else:
        print(render_ledger_summarize_text(payload))
    return 0 if payload["valid"] else 1


def handle_ledger_query(args) -> int:
    if args.limit is not None and args.limit < 1:
        print("limit must be greater than or equal to 1", file=sys.stderr)
        return 2
    fields = None
    if args.fields is not None:
        fields = [item.strip() for item in args.fields.split(",") if item.strip()]
    try:
        payload = query_ledger_input(
            args.input,
            filters=list(args.filter or []),
            limit=args.limit,
            fields=fields,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Could not query ledger: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print_json(payload)
    else:
        print(render_ledger_query_text(payload))
    return 0


def handle_ledger_append(args) -> int:
    try:
        payload = append_result_json(
            args.input,
            args.output,
            run_id=args.run_id or default_run_id(),
            intent=args.intent,
            query_id=args.query_id,
            source_role=args.source_role,
        )
    except FileNotFoundError as exc:
        print(f"Could not append ledger: {exc}", file=sys.stderr)
        return 2
    except (OSError, TypeError, ValueError) as exc:
        print(f"Could not append ledger: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print_json(payload)
    else:
        print(render_ledger_append_text(payload))
    return 0
