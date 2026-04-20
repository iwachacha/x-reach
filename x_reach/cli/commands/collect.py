# -*- coding: utf-8 -*-
"""Collection and collection-shortcut command handlers."""

from __future__ import annotations

import argparse
import sys

from x_reach.candidates import CandidatePlanError
from x_reach.cli.common import print_json
from x_reach.cli.options import (
    add_collect_persistence_args,
    add_collect_render_args,
    add_quality_profile_arg,
    add_search_filter_args,
    add_user_posts_filter_args,
)
from x_reach.cli.renderers.collect import render_collect_text
from x_reach.cli.topic_fit import load_topic_fit_arg
from x_reach.client import AgentReachClient
from x_reach.ledger import (
    default_run_id,
    save_collection_result,
    save_collection_result_execution_shard,
)
from x_reach.mission import MissionSpecError, render_mission_text, run_mission_spec
from x_reach.results import apply_item_text_mode, apply_raw_mode


def register_collect_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p_collect = subparsers.add_parser("collect", help="Run a read-only collection operation")
    p_collect.add_argument(
        "--channel",
        default="twitter",
        help="Stable channel name. Defaults to twitter.",
    )
    p_collect.add_argument("--operation", help="Supported operation for the channel")
    p_collect.add_argument(
        "--input",
        help="Input value such as a search query, profile handle, or tweet URL",
    )
    p_collect.add_argument(
        "--spec",
        help="Mission spec JSON for deterministic multi-query collection",
    )
    p_collect.add_argument(
        "--output-dir",
        help="Mission output directory used with --spec",
    )
    p_collect.add_argument(
        "--resume",
        action="store_true",
        help="Resume a mission spec by skipping already saved query results",
    )
    p_collect.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and render the mission plan without collecting. Only supported with --spec",
    )
    p_collect.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Mission query concurrency used with --spec",
    )
    p_collect.add_argument(
        "--checkpoint-every",
        type=int,
        default=25,
        help="Mission checkpoint interval used with --spec",
    )
    p_collect.add_argument(
        "--query-delay",
        dest="query_delay_seconds",
        type=float,
        help="Minimum seconds between mission query starts used with --spec",
    )
    p_collect.add_argument(
        "--query-jitter",
        dest="query_jitter_seconds",
        type=float,
        help="Maximum random extra seconds before each mission query start used with --spec",
    )
    p_collect.add_argument(
        "--throttle-cooldown",
        dest="throttle_cooldown_seconds",
        type=float,
        help="Cooldown seconds after a throttle-sensitive mission query error",
    )
    p_collect.add_argument(
        "--throttle-error-limit",
        type=int,
        help="Skip remaining mission queries after this many throttle-sensitive errors; 0 disables the stop guard",
    )
    p_collect.add_argument("--limit", type=int, help="Optional item limit for returned tweets or replies")
    add_search_filter_args(p_collect)
    p_collect.add_argument(
        "--topic-fit",
        help="JSON file containing caller-declared topic-fit rules for supported operations",
    )
    p_collect.add_argument(
        "--originals-only",
        action="store_true",
        help="Only keep authored posts for user_posts by filtering out retweets client-side",
    )
    add_quality_profile_arg(p_collect)
    add_collect_render_args(p_collect)
    add_collect_persistence_args(p_collect)
    p_collect.set_defaults(handler=handle_collect)

    p_search = subparsers.add_parser("search", help="Shortcut for twitter search")
    p_search.add_argument("query", help="Search query text")
    p_search.add_argument("--limit", type=int, help="Optional item limit for returned tweets")
    add_search_filter_args(p_search)
    add_quality_profile_arg(p_search)
    add_collect_render_args(p_search)
    add_collect_persistence_args(p_search)
    p_search.set_defaults(
        handler=handle_shortcut_collect,
        shortcut_operation="search",
        shortcut_input_attr="query",
    )

    p_hashtag = subparsers.add_parser("hashtag", help="Shortcut for twitter hashtag collection")
    p_hashtag.add_argument("tag", help='Hashtag value with or without "#"')
    p_hashtag.add_argument("--limit", type=int, help="Optional item limit for returned tweets")
    add_search_filter_args(p_hashtag)
    add_quality_profile_arg(p_hashtag)
    add_collect_render_args(p_hashtag)
    add_collect_persistence_args(p_hashtag)
    p_hashtag.set_defaults(
        handler=handle_shortcut_collect,
        shortcut_operation="hashtag",
        shortcut_input_attr="tag",
    )

    p_user = subparsers.add_parser("user", help="Shortcut for twitter profile lookup")
    p_user.add_argument("handle", help="Profile handle or URL")
    add_collect_render_args(p_user)
    add_collect_persistence_args(p_user)
    p_user.set_defaults(
        handler=handle_shortcut_collect,
        shortcut_operation="user",
        shortcut_input_attr="handle",
    )

    p_posts = subparsers.add_parser("posts", help="Shortcut for twitter timeline lookup")
    p_posts.add_argument("handle", help="Profile handle or URL")
    p_posts.add_argument("--limit", type=int, help="Optional item limit for returned tweets")
    p_posts.add_argument(
        "--originals-only",
        action="store_true",
        help="Only keep authored posts by filtering out retweets client-side",
    )
    add_user_posts_filter_args(p_posts)
    add_quality_profile_arg(p_posts)
    add_collect_render_args(p_posts)
    add_collect_persistence_args(p_posts)
    p_posts.set_defaults(
        handler=handle_shortcut_collect,
        shortcut_operation="user_posts",
        shortcut_input_attr="handle",
    )

    p_tweet = subparsers.add_parser("tweet", help="Shortcut for one tweet or thread lookup")
    p_tweet.add_argument("value", help="Tweet URL or tweet ID")
    p_tweet.add_argument("--limit", type=int, help="Optional item limit for returned tweets or replies")
    add_collect_render_args(p_tweet)
    add_collect_persistence_args(p_tweet)
    p_tweet.set_defaults(
        handler=handle_shortcut_collect,
        shortcut_operation="tweet",
        shortcut_input_attr="value",
    )


def _shortcut_collect_namespace(args, *, operation: str, input_value: str) -> argparse.Namespace:
    return argparse.Namespace(
        channel="twitter",
        operation=operation,
        input=input_value,
        spec=None,
        output_dir=None,
        resume=False,
        dry_run=False,
        concurrency=1,
        checkpoint_every=25,
        limit=getattr(args, "limit", None),
        since=getattr(args, "since", None),
        until=getattr(args, "until", None),
        from_user=getattr(args, "from_user", None),
        to_user=getattr(args, "to_user", None),
        lang=getattr(args, "lang", None),
        search_type=getattr(args, "search_type", None),
        has=getattr(args, "has", None),
        exclude=getattr(args, "exclude", None),
        min_likes=getattr(args, "min_likes", None),
        min_retweets=getattr(args, "min_retweets", None),
        min_views=getattr(args, "min_views", None),
        originals_only=getattr(args, "originals_only", False),
        topic_fit=getattr(args, "topic_fit", None),
        quality_profile=getattr(args, "quality_profile", None),
        json=getattr(args, "json", False),
        max_text_chars=getattr(args, "max_text_chars", None),
        item_text_mode=getattr(args, "item_text_mode", None),
        item_text_max_chars=getattr(args, "item_text_max_chars", None),
        raw_mode=getattr(args, "raw_mode", None),
        raw_max_bytes=getattr(args, "raw_max_bytes", None),
        save=getattr(args, "save", None),
        save_dir=getattr(args, "save_dir", None),
        run_id=getattr(args, "run_id", None),
        intent=getattr(args, "intent", None),
        query_id=getattr(args, "query_id", None),
        source_role=getattr(args, "source_role", None),
        warn_missing_evidence_metadata=getattr(args, "warn_missing_evidence_metadata", False),
    )


def handle_shortcut_collect(args) -> int:
    input_value = getattr(args, args.shortcut_input_attr)
    return handle_collect(
        _shortcut_collect_namespace(
            args,
            operation=args.shortcut_operation,
            input_value=input_value,
        )
    )


def handle_collect(args) -> int:
    if getattr(args, "spec", None):
        return handle_collect_spec(args)
    if not args.operation or not args.input:
        print("collect requires --operation and --input unless --spec is used", file=sys.stderr)
        return 2
    spec_only_options = (
        getattr(args, "dry_run", False),
        getattr(args, "output_dir", None),
        getattr(args, "resume", False),
        getattr(args, "query_delay_seconds", None),
        getattr(args, "query_jitter_seconds", None),
        getattr(args, "throttle_cooldown_seconds", None),
        getattr(args, "throttle_error_limit", None),
    )
    if any(value is not None and value is not False for value in spec_only_options):
        print(
            "dry-run, output-dir, resume, and pacing options are only supported with --spec",
            file=sys.stderr,
        )
        return 2
    if args.max_text_chars is not None and args.max_text_chars < 1:
        print("max-text-chars must be greater than or equal to 1", file=sys.stderr)
        return 2
    if args.item_text_max_chars is not None and args.item_text_max_chars < 1:
        print("item-text-max-chars must be greater than or equal to 1", file=sys.stderr)
        return 2
    if args.item_text_max_chars is not None and args.item_text_mode not in (None, "snippet"):
        print("item-text-max-chars is only supported with item-text-mode snippet", file=sys.stderr)
        return 2
    if args.raw_max_bytes is not None and args.raw_max_bytes < 1:
        print("raw-max-bytes must be greater than or equal to 1", file=sys.stderr)
        return 2
    annotations = [args.intent, args.query_id, args.source_role]
    if any(value is not None for value in annotations) and not (args.save or args.save_dir):
        print("intent, query-id, and source-role require --save or --save-dir", file=sys.stderr)
        return 2

    client = AgentReachClient()
    collect_kwargs = {}
    if args.limit is not None:
        collect_kwargs["limit"] = args.limit
    if args.since is not None:
        collect_kwargs["since"] = args.since
    if args.until is not None:
        collect_kwargs["until"] = args.until
    if args.from_user is not None:
        collect_kwargs["from_user"] = args.from_user
    if args.to_user is not None:
        collect_kwargs["to_user"] = args.to_user
    if args.lang is not None:
        collect_kwargs["lang"] = args.lang
    if args.search_type is not None:
        collect_kwargs["search_type"] = args.search_type
    if args.has is not None:
        collect_kwargs["has"] = args.has
    if args.exclude is not None:
        collect_kwargs["exclude"] = args.exclude
    if args.min_likes is not None:
        collect_kwargs["min_likes"] = args.min_likes
    if args.min_retweets is not None:
        collect_kwargs["min_retweets"] = args.min_retweets
    if args.min_views is not None:
        collect_kwargs["min_views"] = args.min_views
    if getattr(args, "originals_only", False):
        collect_kwargs["originals_only"] = True
    if getattr(args, "topic_fit", None) is not None:
        try:
            collect_kwargs["topic_fit"] = load_topic_fit_arg(args.topic_fit)
        except CandidatePlanError as exc:
            print(f"Could not collect: {exc}", file=sys.stderr)
            return 2
    if getattr(args, "quality_profile", None) is not None:
        collect_kwargs["quality_profile"] = args.quality_profile
    if args.raw_mode is not None:
        collect_kwargs["raw_mode"] = args.raw_mode
    if args.raw_max_bytes is not None:
        collect_kwargs["raw_max_bytes"] = args.raw_max_bytes
    if args.item_text_mode is not None:
        collect_kwargs["item_text_mode"] = args.item_text_mode
    if args.item_text_max_chars is not None:
        collect_kwargs["item_text_max_chars"] = args.item_text_max_chars
    payload = client.collect(args.channel, args.operation, args.input, **collect_kwargs)
    explicit_shaping_requested = any(
        value is not None
        for value in (
            args.item_text_mode,
            args.item_text_max_chars,
            args.raw_mode,
            args.raw_max_bytes,
        )
    )
    if explicit_shaping_requested:
        meta = payload.get("meta") or {}
        effective_item_text_mode = args.item_text_mode or (
            "snippet" if args.item_text_max_chars is not None else meta.get("item_text_mode") or "full"
        )
        effective_item_text_max_chars = (
            args.item_text_max_chars if args.item_text_max_chars is not None else meta.get("item_text_max_chars")
        )
        effective_raw_mode = args.raw_mode or ("full" if args.raw_max_bytes is not None else meta.get("raw_mode") or "full")
        try:
            payload = apply_item_text_mode(
                payload,
                item_text_mode=effective_item_text_mode,
                item_text_max_chars=effective_item_text_max_chars,
            )
            payload = apply_raw_mode(
                payload,
                raw_mode=effective_raw_mode,
                raw_max_bytes=args.raw_max_bytes,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if args.json:
        print_json(payload)
    else:
        print(render_collect_text(payload, max_text_chars=args.max_text_chars))

    if args.save or args.save_dir:
        if getattr(args, "warn_missing_evidence_metadata", False):
            _warn_missing_evidence_metadata(args.intent, args.query_id, args.source_role)
        try:
            run_id = args.run_id or default_run_id()
            if args.save:
                save_collection_result(
                    args.save,
                    payload,
                    run_id=run_id,
                    input_value=args.input,
                    intent=args.intent,
                    query_id=args.query_id,
                    source_role=args.source_role,
                )
            else:
                save_collection_result_execution_shard(
                    args.save_dir,
                    payload,
                    run_id=run_id,
                    input_value=args.input,
                    intent=args.intent,
                    query_id=args.query_id,
                    source_role=args.source_role,
                )
        except (OSError, TypeError, ValueError) as exc:
            print(f"Could not save evidence ledger: {exc}", file=sys.stderr)
            return 1

    if payload["ok"]:
        return 0
    error = payload["error"]
    if error and error["code"] in {"unknown_channel", "unsupported_operation", "invalid_input", "unsupported_option"}:
        return 2
    return 1


def handle_collect_spec(args) -> int:
    if args.operation or args.input:
        print("collect --spec cannot be combined with --operation or --input", file=sys.stderr)
        return 2
    if getattr(args, "topic_fit", None):
        print("collect --spec reads topic_fit from the mission spec; --topic-fit is only supported with --operation", file=sys.stderr)
        return 2
    if args.save or args.save_dir:
        print("collect --spec writes its own mission artifacts; use --output-dir instead of --save/--save-dir", file=sys.stderr)
        return 2
    if any(value is not None for value in (args.intent, args.query_id, args.source_role)):
        print("collect --spec derives evidence metadata from the mission spec", file=sys.stderr)
        return 2
    try:
        payload = run_mission_spec(
            args.spec,
            output_dir=args.output_dir,
            run_id=args.run_id,
            resume=args.resume,
            dry_run=args.dry_run,
            concurrency=args.concurrency,
            checkpoint_every=args.checkpoint_every,
            query_delay_seconds=args.query_delay_seconds,
            query_jitter_seconds=args.query_jitter_seconds,
            throttle_cooldown_seconds=args.throttle_cooldown_seconds,
            throttle_error_limit=args.throttle_error_limit,
        )
    except MissionSpecError as exc:
        print(f"Could not run mission spec: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print_json(payload)
    else:
        print(render_mission_text(payload))
    return 0 if payload.get("ok", True) else 1


def _warn_missing_evidence_metadata(
    intent: str | None,
    query_id: str | None,
    source_role: str | None,
) -> None:
    missing = [
        name
        for name, value in (
            ("intent", intent),
            ("query-id", query_id),
            ("source-role", source_role),
        )
        if value is None
    ]
    if missing:
        print(
            "[WARN] evidence ledger save used without evidence metadata: "
            f"{', '.join(missing)}. "
            "Use --intent, --query-id, and --source-role when downstream provenance matters.",
            file=sys.stderr,
        )
