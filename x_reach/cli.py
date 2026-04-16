# -*- coding: utf-8 -*-
"""CLI for the Windows/Codex X Reach fork."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from x_reach import __version__
from x_reach.batch import BatchPlanError, render_batch_text, run_batch_plan, validate_batch_plan
from x_reach.candidates import (
    CandidatePlanError,
    build_candidates_payload,
    render_candidates_text,
)
from x_reach.client import AgentReachClient
from x_reach.integrations.codex import (
    LEGACY_PACKAGED_SKILL_NAMES,
    PACKAGED_SKILL_NAMES,
    packaged_skill_source,
)
from x_reach.ledger import (
    append_result_json,
    default_run_id,
    merge_ledger_inputs,
    query_ledger_input,
    save_collection_result,
    save_collection_result_execution_shard,
    summarize_ledger_input,
    validate_ledger_input,
)
from x_reach.mission import MissionSpecError, render_mission_text, run_mission_spec
from x_reach.results import CollectionResult, apply_item_text_mode, apply_raw_mode
from x_reach.schemas import (
    SCHEMA_VERSION,
    collection_result_schema,
    judge_result_schema,
    mission_spec_schema,
    utc_timestamp,
)
from x_reach.scout import (
    BUDGETS,
    PRESETS,
    QUALITY_PROFILES,
    ScoutPlanError,
    build_scout_plan,
    render_scout_text,
)
from x_reach.utils.commands import find_command

CHANNEL_SPECIFIC_INSTALL_CHANNELS = ("twitter",)

UPSTREAM_REPO = "Panniantong/Agent-Reach"


def _ensure_utf8_console() -> None:
    """Best-effort UTF-8 stdout/stderr on Windows terminals."""

    if sys.platform != "win32" or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    try:
        import io

        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


def _configure_logging(verbose: bool = False) -> None:
    """Keep loguru quiet unless verbose output is explicitly requested."""

    from loguru import logger

    logger.remove()
    if verbose:
        logger.add(sys.stderr, level="INFO")


def _print_json(payload: object) -> None:
    """Render a stable JSON payload."""

    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _add_collect_render_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Print machine-readable collection output")
    parser.add_argument(
        "--max-text-chars",
        type=int,
        help="Show text snippets up to N characters in text mode only",
    )
    parser.add_argument(
        "--item-text-mode",
        choices=["full", "snippet", "none"],
        help="Control normalized item text retention in CollectionResult output. Broad operations default to snippet",
    )
    parser.add_argument(
        "--item-text-max-chars",
        type=int,
        help="When item-text-mode is snippet, keep at most N characters per item text. Broad operations default to 280",
    )
    parser.add_argument(
        "--raw-mode",
        choices=["full", "minimal", "none"],
        help="Control raw payload retention in printed and saved CollectionResult JSON. Broad operations default to none",
    )
    parser.add_argument(
        "--raw-max-bytes",
        type=int,
        help="Replace raw with a preview summary when its UTF-8 JSON size exceeds N bytes",
    )


def _add_quality_profile_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--quality-profile",
        choices=QUALITY_PROFILES,
        help="High-signal collection profile. Broad operations default to balanced",
    )


def _add_collect_persistence_args(parser: argparse.ArgumentParser) -> None:
    collect_save_group = parser.add_mutually_exclusive_group()
    collect_save_group.add_argument(
        "--save",
        help="Append the raw CollectionResult envelope to an evidence ledger JSONL file",
    )
    collect_save_group.add_argument(
        "--save-dir",
        help="Write one JSONL shard per collect execution; merge later with ledger merge",
    )
    parser.add_argument(
        "--run-id",
        help="Evidence ledger run ID. Defaults to X_REACH_RUN_ID (or legacy AGENT_REACH_RUN_ID) or a UTC timestamp",
    )
    parser.add_argument(
        "--intent",
        help="Optional evidence ledger intent label. Requires --save or --save-dir",
    )
    parser.add_argument(
        "--query-id",
        help="Optional evidence ledger query ID. Requires --save or --save-dir",
    )
    parser.add_argument(
        "--source-role",
        help="Optional evidence ledger source role label. Requires --save or --save-dir",
    )
    parser.add_argument(
        "--warn-missing-evidence-metadata",
        action="store_true",
        help="Warn on stderr when saving without --intent, --query-id, or --source-role",
    )


def _add_search_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--since", help="Optional lower time boundary for operations that support it")
    parser.add_argument("--until", help="Optional upper time boundary for operations that support it")
    parser.add_argument("--from", dest="from_user", help="Restrict search results to one author")
    parser.add_argument("--to", dest="to_user", help="Restrict search results to one mentioned recipient")
    parser.add_argument("--lang", help="Restrict search results to one language code")
    parser.add_argument(
        "--type",
        dest="search_type",
        choices=["top", "latest", "photos", "videos"],
        help="Choose the search tab for twitter-cli backed searches",
    )
    parser.add_argument(
        "--has",
        action="append",
        choices=["links", "images", "videos", "media"],
        help="Require a content type. Repeat to require multiple.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        choices=["retweets", "replies", "links"],
        help="Exclude a content type. Repeat to exclude multiple.",
    )
    parser.add_argument("--min-likes", type=int, help="Minimum likes threshold for search")
    parser.add_argument("--min-retweets", type=int, help="Minimum retweets threshold for search")
    parser.add_argument("--min-views", type=int, help="Minimum views threshold applied after search")


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


def _cmd_shortcut_collect(args, *, operation: str, input_value: str) -> int:
    return _cmd_collect(_shortcut_collect_namespace(args, operation=operation, input_value=input_value))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="x-reach",
        description="Windows-first X/Twitter research tooling for Codex and compatible agents",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show debug logs")
    parser.add_argument("--version", action="version", version=f"X Reach v{__version__}")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    p_install = sub.add_parser("install", help="Install and configure the supported research stack")
    p_install.add_argument(
        "--env",
        choices=["local", "server", "auto"],
        default="auto",
        help="Environment classification for messaging only",
    )
    p_install.add_argument(
        "--safe",
        action="store_true",
        help="Show the Windows commands that would be run without changing anything",
    )
    p_install.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the install plan without changing anything",
    )
    p_install.add_argument(
        "--channels",
        default="",
        help="Comma-separated channel names to prepare for this environment, or all",
    )
    p_install.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable install plan. Requires --dry-run or --safe",
    )

    p_configure = sub.add_parser("configure", help="Save credentials or import them from a browser")
    p_configure.add_argument(
        "key",
        nargs="?",
        choices=[
            "twitter-cookies",
        ],
        help="Configuration key to set",
    )
    p_configure.add_argument("value", nargs="*", help="Value to store")
    p_configure.add_argument(
        "--from-browser",
        metavar="BROWSER",
        choices=["chrome", "firefox", "edge", "brave", "opera"],
        help="Import Twitter cookies from a local browser",
    )

    p_doctor = sub.add_parser("doctor", help="Check supported channel availability")
    p_doctor.add_argument("--json", action="store_true", help="Print machine-readable diagnostics")
    p_doctor.add_argument(
        "--probe",
        action="store_true",
        help="Run lightweight live probes after readiness checks",
    )
    p_doctor.add_argument(
        "--require-channel",
        action="append",
        default=[],
        help="Require this channel to be ready for exit-code purposes. Repeatable.",
    )
    p_doctor.add_argument(
        "--require-channels",
        help="Comma-separated channel names to require ready for exit-code purposes",
    )
    p_doctor.add_argument(
        "--require-all",
        action="store_true",
        help="Require every registered channel to be ready for exit-code purposes",
    )

    p_collect = sub.add_parser("collect", help="Run a read-only collection operation")
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
    p_collect.add_argument("--limit", type=int, help="Optional item limit for returned tweets or replies")
    p_collect.add_argument("--since", help="Optional lower time boundary for operations that support it")
    p_collect.add_argument("--until", help="Optional upper time boundary for operations that support it")
    p_collect.add_argument("--from", dest="from_user", help="Restrict search results to one author")
    p_collect.add_argument("--to", dest="to_user", help="Restrict search results to one mentioned recipient")
    p_collect.add_argument("--lang", help="Restrict search results to one language code")
    p_collect.add_argument(
        "--type",
        dest="search_type",
        choices=["top", "latest", "photos", "videos"],
        help="Choose the search tab for twitter-cli backed searches",
    )
    p_collect.add_argument(
        "--has",
        action="append",
        choices=["links", "images", "videos", "media"],
        help="Require a content type. Repeat to require multiple.",
    )
    p_collect.add_argument(
        "--exclude",
        action="append",
        choices=["retweets", "replies", "links"],
        help="Exclude a content type. Repeat to exclude multiple.",
    )
    p_collect.add_argument("--min-likes", type=int, help="Minimum likes threshold for search")
    p_collect.add_argument("--min-retweets", type=int, help="Minimum retweets threshold for search")
    p_collect.add_argument("--min-views", type=int, help="Minimum views threshold applied after search")
    p_collect.add_argument(
        "--originals-only",
        action="store_true",
        help="Only keep authored posts for user_posts by filtering out retweets client-side",
    )
    _add_quality_profile_arg(p_collect)
    p_collect.add_argument("--json", action="store_true", help="Print machine-readable collection output")
    p_collect.add_argument(
        "--max-text-chars",
        type=int,
        help="Show text snippets up to N characters in text mode only",
    )
    p_collect.add_argument(
        "--item-text-mode",
        choices=["full", "snippet", "none"],
        help="Control normalized item text retention in CollectionResult output. Broad operations default to snippet",
    )
    p_collect.add_argument(
        "--item-text-max-chars",
        type=int,
        help="When item-text-mode is snippet, keep at most N characters per item text. Broad operations default to 280",
    )
    p_collect.add_argument(
        "--raw-mode",
        choices=["full", "minimal", "none"],
        help="Control raw payload retention in printed and saved CollectionResult JSON. Broad operations default to none",
    )
    p_collect.add_argument(
        "--raw-max-bytes",
        type=int,
        help="Replace raw with a preview summary when its UTF-8 JSON size exceeds N bytes",
    )
    collect_save_group = p_collect.add_mutually_exclusive_group()
    collect_save_group.add_argument(
        "--save",
        help="Append the raw CollectionResult envelope to an evidence ledger JSONL file",
    )
    collect_save_group.add_argument(
        "--save-dir",
        help="Write one JSONL shard per collect execution; merge later with ledger merge",
    )
    p_collect.add_argument(
        "--run-id",
        help="Evidence ledger run ID. Defaults to X_REACH_RUN_ID (or legacy AGENT_REACH_RUN_ID) or a UTC timestamp",
    )
    p_collect.add_argument(
        "--intent",
        help="Optional evidence ledger intent label. Requires --save or --save-dir",
    )
    p_collect.add_argument(
        "--query-id",
        help="Optional evidence ledger query ID. Requires --save or --save-dir",
    )
    p_collect.add_argument(
        "--source-role",
        help="Optional evidence ledger source role label. Requires --save or --save-dir",
    )
    p_collect.add_argument(
        "--warn-missing-evidence-metadata",
        action="store_true",
        help="Warn on stderr when saving without --intent, --query-id, or --source-role",
    )

    p_search = sub.add_parser("search", help="Shortcut for twitter search")
    p_search.add_argument("query", help="Search query text")
    p_search.add_argument("--limit", type=int, help="Optional item limit for returned tweets")
    _add_search_filter_args(p_search)
    _add_quality_profile_arg(p_search)
    _add_collect_render_args(p_search)
    _add_collect_persistence_args(p_search)

    p_hashtag = sub.add_parser("hashtag", help="Shortcut for twitter hashtag collection")
    p_hashtag.add_argument("tag", help='Hashtag value with or without "#"')
    p_hashtag.add_argument("--limit", type=int, help="Optional item limit for returned tweets")
    _add_search_filter_args(p_hashtag)
    _add_quality_profile_arg(p_hashtag)
    _add_collect_render_args(p_hashtag)
    _add_collect_persistence_args(p_hashtag)

    p_user = sub.add_parser("user", help="Shortcut for twitter profile lookup")
    p_user.add_argument("handle", help="Profile handle or URL")
    _add_collect_render_args(p_user)
    _add_collect_persistence_args(p_user)

    p_posts = sub.add_parser("posts", help="Shortcut for twitter timeline lookup")
    p_posts.add_argument("handle", help="Profile handle or URL")
    p_posts.add_argument("--limit", type=int, help="Optional item limit for returned tweets")
    p_posts.add_argument(
        "--originals-only",
        action="store_true",
        help="Only keep authored posts by filtering out retweets client-side",
    )
    _add_quality_profile_arg(p_posts)
    _add_collect_render_args(p_posts)
    _add_collect_persistence_args(p_posts)

    p_tweet = sub.add_parser("tweet", help="Shortcut for one tweet or thread lookup")
    p_tweet.add_argument("value", help="Tweet URL or tweet ID")
    p_tweet.add_argument("--limit", type=int, help="Optional item limit for returned tweets or replies")
    _add_collect_render_args(p_tweet)
    _add_collect_persistence_args(p_tweet)

    p_plan = sub.add_parser("plan", help="Build lightweight plans from evidence ledgers")
    plan_sub = p_plan.add_subparsers(dest="plan_command", help="Planning commands")
    p_candidates = plan_sub.add_parser(
        "candidates",
        help="Return deduped candidates for follow-up reads",
    )
    p_candidates.add_argument("--input", required=True, help="Evidence ledger JSONL input path")
    p_candidates.add_argument(
        "--by",
        choices=["url", "normalized_url", "id", "source_item_id", "domain", "author", "post"],
        default="url",
        help="Dedupe mode. Defaults to URL, then falls back to source + id",
    )
    p_candidates.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum candidates to return",
    )
    p_candidates.add_argument("--json", action="store_true", help="Print machine-readable output")
    p_candidates.add_argument(
        "--summary-only",
        action="store_true",
        help="Return summary counts without candidate bodies",
    )
    p_candidates.add_argument(
        "--fields",
        help="Comma-separated candidate fields to include in output",
    )
    p_candidates.add_argument(
        "--max-per-author",
        type=int,
        help="Optional maximum number of returned candidates per author",
    )
    p_candidates.add_argument(
        "--prefer-originals",
        action="store_true",
        help="Prefer original posts when duplicate candidates share the same dedupe key",
    )
    p_candidates.add_argument(
        "--drop-noise",
        action="store_true",
        help="Drop candidates that match the deterministic X noise rules",
    )
    p_candidates.add_argument(
        "--drop-title-duplicates",
        action="store_true",
        help="Drop later candidates whose normalized titles exactly match an earlier candidate",
    )
    p_candidates.add_argument(
        "--require-query-match",
        action="store_true",
        help="Keep only candidates that still match stored query tokens",
    )
    p_candidates.add_argument(
        "--min-seen-in",
        type=int,
        help="Keep only candidates observed in at least N ledger sightings",
    )

    p_scout = sub.add_parser("scout", help="Build an opt-in plan-only capability snapshot")
    p_scout.add_argument("--topic", required=True, help="Topic echo for the calling workflow")
    p_scout.add_argument("--budget", choices=BUDGETS, default="auto", help="Research budget hint")
    p_scout.add_argument(
        "--quality",
        choices=QUALITY_PROFILES,
        default="precision",
        help="Quality profile hint",
    )
    p_scout.add_argument("--preset", choices=PRESETS, help="Optional source-pack seed")
    p_scout.add_argument(
        "--plan-only",
        action="store_true",
        help="Build the plan without running network collection",
    )
    p_scout.add_argument("--json", action="store_true", help="Print machine-readable scout output")

    p_batch = sub.add_parser("batch", help="Run or validate a bounded batch collection plan")
    p_batch.add_argument("--plan", required=True, help="Research plan JSON path")
    batch_save_group = p_batch.add_mutually_exclusive_group()
    batch_save_group.add_argument("--save", help="Evidence ledger JSONL output path")
    batch_save_group.add_argument("--save-dir", help="Directory for sharded evidence ledger JSONL outputs")
    p_batch.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the plan and print a non-mutating summary without collecting or writing ledger data",
    )
    p_batch.add_argument(
        "--shard-by",
        choices=["channel", "operation", "channel-operation"],
        help="Shard key for --save-dir outputs. Defaults to channel",
    )
    p_batch.add_argument("--concurrency", type=int, default=1, help="Maximum concurrent collections")
    p_batch.add_argument("--resume", action="store_true", help="Skip queries already saved in the ledger")
    p_batch.add_argument(
        "--checkpoint-every",
        type=int,
        default=100,
        help="Emit checkpoint summaries after this many completed queries",
    )
    p_batch.add_argument(
        "--quality",
        choices=QUALITY_PROFILES,
        help="Override the plan quality profile hint",
    )
    p_batch.add_argument("--json", action="store_true", help="Print machine-readable batch output")

    p_channels = sub.add_parser("channels", help="Show the stable channel registry")
    p_channels.add_argument("name", nargs="?", help="Optional stable channel name to inspect")
    p_channels.add_argument("--json", action="store_true", help="Print machine-readable channel data")

    p_schema = sub.add_parser("schema", help="Print packaged JSON Schemas for stable contracts")
    p_schema.add_argument(
        "name",
        choices=["collection-result", "mission-spec", "judge-result"],
        help="Schema name to print",
    )
    p_schema.add_argument("--json", action="store_true", help="Print the JSON Schema payload")

    p_export = sub.add_parser(
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

    p_ledger = sub.add_parser("ledger", help="Manage evidence ledger files")
    ledger_sub = p_ledger.add_subparsers(dest="ledger_command", help="Ledger commands")
    p_ledger_merge = ledger_sub.add_parser("merge", help="Merge a ledger file or shard directory into one JSONL file")
    p_ledger_merge.add_argument("--input", required=True, help="Ledger input file or directory")
    p_ledger_merge.add_argument("--output", required=True, help="Merged ledger JSONL output path")
    p_ledger_merge.add_argument("--json", action="store_true", help="Print machine-readable merge output")
    p_ledger_validate = ledger_sub.add_parser("validate", help="Validate a ledger file or shard directory")
    p_ledger_validate.add_argument("--input", required=True, help="Ledger input file or directory")
    p_ledger_validate.add_argument(
        "--require-metadata",
        action="store_true",
        help="Fail validation when collection records lack intent, query_id, or source_role",
    )
    p_ledger_validate.add_argument("--json", action="store_true", help="Print machine-readable validation output")
    p_ledger_summarize = ledger_sub.add_parser("summarize", help="Summarize evidence ledger health counts")
    p_ledger_summarize.add_argument("--input", required=True, help="Ledger input file or directory")
    p_ledger_summarize.add_argument(
        "--filter",
        action="append",
        default=[],
        help='Repeatable filter such as "intent == official_docs" or "source_role == social_search"',
    )
    p_ledger_summarize.add_argument("--json", action="store_true", help="Print machine-readable summary output")
    p_ledger_query = ledger_sub.add_parser("query", help="Filter evidence ledger records")
    p_ledger_query.add_argument("--input", required=True, help="Ledger input file or directory")
    p_ledger_query.add_argument(
        "--filter",
        action="append",
        default=[],
        help='Repeatable filter such as "channel == twitter" or "ok == true"',
    )
    p_ledger_query.add_argument(
        "--limit",
        type=int,
        help="Optional maximum number of matching records to return",
    )
    p_ledger_query.add_argument(
        "--fields",
        help="Comma-separated projection fields such as channel,source.file,result.items[*].url",
    )
    p_ledger_query.add_argument("--json", action="store_true", help="Print machine-readable query output")
    p_ledger_append = ledger_sub.add_parser("append", help="Append a CollectionResult JSON file to a ledger")
    p_ledger_append.add_argument("--input", required=True, help="CollectionResult JSON input file")
    p_ledger_append.add_argument("--output", required=True, help="Evidence ledger JSONL output path")
    p_ledger_append.add_argument("--run-id", help="Evidence ledger run ID. Defaults to X_REACH_RUN_ID (or legacy AGENT_REACH_RUN_ID) or a UTC timestamp")
    p_ledger_append.add_argument("--intent", help="Optional evidence ledger intent label")
    p_ledger_append.add_argument("--query-id", help="Optional evidence ledger query ID")
    p_ledger_append.add_argument("--source-role", help="Optional evidence ledger source role label")
    p_ledger_append.add_argument("--json", action="store_true", help="Print machine-readable append output")

    p_uninstall = sub.add_parser("uninstall", help="Remove local X Reach state and skill files")
    p_uninstall.add_argument("--dry-run", action="store_true", help="Preview what would be removed")
    p_uninstall.add_argument(
        "--keep-config",
        action="store_true",
        help="Remove skill files only and keep ~/.x-reach",
    )

    p_skill = sub.add_parser("skill", help="Install or remove the bundled skill suite")
    skill_group = p_skill.add_mutually_exclusive_group(required=True)
    skill_group.add_argument("--install", action="store_true", help="Install the bundled skill")
    skill_group.add_argument("--uninstall", action="store_true", help="Remove the bundled skill")

    p_check_update = sub.add_parser("check-update", help="Check the upstream project for new releases")
    p_check_update.add_argument("--json", action="store_true", help="Print machine-readable update data")

    sub.add_parser("version", help="Show the current X Reach version")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    _ensure_utf8_console()

    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(getattr(args, "verbose", False))

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "version":
        print(f"X Reach v{__version__}")
        return 0
    if args.command == "install":
        return _cmd_install(args)
    if args.command == "configure":
        return _cmd_configure(args)
    if args.command == "doctor":
        return _cmd_doctor(args)
    if args.command == "collect":
        return _cmd_collect(args)
    if args.command == "search":
        return _cmd_shortcut_collect(args, operation="search", input_value=args.query)
    if args.command == "hashtag":
        return _cmd_shortcut_collect(args, operation="hashtag", input_value=args.tag)
    if args.command == "user":
        return _cmd_shortcut_collect(args, operation="user", input_value=args.handle)
    if args.command == "posts":
        return _cmd_shortcut_collect(args, operation="user_posts", input_value=args.handle)
    if args.command == "tweet":
        return _cmd_shortcut_collect(args, operation="tweet", input_value=args.value)
    if args.command == "plan":
        return _cmd_plan(args)
    if args.command == "scout":
        return _cmd_scout(args)
    if args.command == "batch":
        return _cmd_batch(args)
    if args.command == "ledger":
        return _cmd_ledger(args)
    if args.command == "channels":
        return _cmd_channels(args)
    if args.command == "schema":
        return _cmd_schema(args)
    if args.command == "export-integration":
        return _cmd_export_integration(args)
    if args.command == "uninstall":
        return _cmd_uninstall(args)
    if args.command == "skill":
        return _cmd_skill(args)
    if args.command == "check-update":
        return _cmd_check_update(args)
    return 0


def _all_channel_names() -> List[str]:
    from x_reach.channels import get_all_channel_contracts

    return [contract["name"] for contract in get_all_channel_contracts()]


def _parse_channel_names(
    raw: str,
    *,
    supported_channels: Sequence[str],
    allow_all: bool = False,
) -> List[str]:
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
    normalized: List[str] = []
    for item in items:
        if item not in normalized:
            normalized.append(item)
    return normalized


def _parse_requested_channels(raw: str) -> List[str]:
    return _parse_channel_names(
        raw,
        supported_channels=_all_channel_names(),
        allow_all=True,
    )


def _resolve_doctor_requirements(args) -> tuple[List[str], bool]:
    supported_channels = _all_channel_names()
    required: List[str] = []
    for name in args.require_channel or []:
        parsed = _parse_channel_names(name, supported_channels=supported_channels, allow_all=False)
        for item in parsed:
            if item not in required:
                required.append(item)
    if args.require_channels:
        parsed = _parse_channel_names(
            args.require_channels,
            supported_channels=supported_channels,
            allow_all=False,
        )
        for item in parsed:
            if item not in required:
                required.append(item)
    return required, bool(args.require_all)


def _build_install_plan_payload(
    env: str,
    requested_channels: Sequence[str],
    dry_run: bool = False,
    safe: bool = False,
) -> dict:
    from x_reach.integrations.codex import export_codex_integration

    integration = export_codex_integration()
    mode = "dry-run" if dry_run else "safe"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "command": "install",
        "mode": mode,
        "environment": env,
        "platform": sys.platform,
        "selected_channels": list(requested_channels),
        "channel_specific_setup_channels": [
            channel for channel in requested_channels if channel in CHANNEL_SPECIFIC_INSTALL_CHANNELS
        ],
        "commands": _manual_install_commands(requested_channels),
        "skill_targets": [str(root / skill_name) for root in _candidate_skill_roots() for skill_name in PACKAGED_SKILL_NAMES],
        "execution_context": integration["execution_context"],
        "plugin_manifest": integration["plugin_manifest"],
        "plugin_manifest_inline": integration["plugin_manifest_inline"],
        "mcp_config": integration["mcp_config"],
        "mcp_config_inline": integration["mcp_config_inline"],
        "suggested_destinations": integration["suggested_destinations"],
        "safe": safe,
        "dry_run": dry_run,
    }


def _cmd_install(args) -> int:
    from x_reach.config import Config
    from x_reach.doctor import check_all, format_report

    if args.json and not (args.safe or args.dry_run):
        raise SystemExit("install --json is only supported with --dry-run or --safe")

    config = Config()
    requested_channels = _parse_requested_channels(args.channels)
    env = args.env if args.env != "auto" else _detect_environment()

    if args.safe or args.dry_run:
        if args.json:
            _print_json(
                _build_install_plan_payload(
                    env,
                    requested_channels,
                    dry_run=bool(args.dry_run),
                    safe=bool(args.safe),
                )
            )
        else:
            _print_install_plan(requested_channels, dry_run=args.dry_run)
        return 0

    print()
    print("X Reach Installer")
    print("========================================")
    print(f"Environment: {env}")
    print(f"Selected channels: {', '.join(requested_channels) if requested_channels else 'none'}")
    print()

    failures: List[str] = []

    if sys.platform != "win32":
        print("This fork is Windows-first, but only the Twitter/X backend install is automated here.")

    if "twitter" in requested_channels and not _install_twitter_deps():
        failures.append("twitter-cli")

    installed_paths = _install_skill()
    print()
    if installed_paths:
        print("Installed skill targets:")
        for path in installed_paths:
            print(f"  {path}")

    print()
    print("Health check:")
    print(format_report(check_all(config)))

    if "twitter" in requested_channels:
        print()
        print("Next step for Twitter/X:")
        print('  x-reach configure twitter-cookies "auth_token=...; ct0=..."')
        print("  Or: x-reach configure --from-browser chrome")

    if failures:
        print()
        print("Some steps still need attention:")
        for item in failures:
            print(f"  - {item}")
        print("Run `x-reach install --safe` to print the exact Windows commands again.")
        return 1

    print()
    print("Install complete.")
    return 0


def _print_install_plan(requested_channels: Sequence[str], dry_run: bool = False) -> None:
    prefix = "[dry-run] Would run:" if dry_run else "Manual Windows commands:"
    commands = _manual_install_commands(requested_channels)
    print(prefix)
    for command in commands:
        print(f"  {command}")
    if dry_run:
        print()
        print("Dry run complete. No changes were made.")


def _manual_install_commands(requested_channels: Sequence[str]) -> List[str]:
    commands: List[str] = []
    if "twitter" in requested_channels and not find_command("twitter"):
        commands.append("uv tool install twitter-cli")
    commands.append("x-reach skill --install")
    return commands


def _detect_environment() -> str:
    if sys.platform == "win32":
        return "local"
    indicators = [
        os.environ.get("CI"),
        os.environ.get("GITHUB_ACTIONS"),
        os.environ.get("SSH_CONNECTION"),
    ]
    return "server" if any(indicators) else "local"


def _run(
    command: Sequence[str],
    timeout: int = 120,
    check: bool = False,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(command),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=check,
    )


def _install_twitter_deps() -> bool:
    if find_command("twitter"):
        print("  [OK] twitter-cli already installed")
        return True
    uv = shutil.which("uv")
    if not uv:
        print("  [WARN] uv is missing, so twitter-cli cannot be installed automatically")
        return False
    print("  Installing twitter-cli with uv tool...")
    try:
        _run([uv, "tool", "install", "twitter-cli"], timeout=600)
    except Exception as exc:
        print(f"  [WARN] twitter-cli install failed: {exc}")
        return False
    if find_command("twitter"):
        print("  [OK] twitter-cli is ready")
        return True
    print("  [WARN] twitter-cli is still missing after uv tool install")
    return False


def _candidate_skill_roots() -> List[Path]:
    roots: List[Path] = []
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        roots.append(Path(codex_home) / "skills")
    roots.append(Path.home() / ".codex" / "skills")
    roots.append(Path.home() / ".agents" / "skills")

    deduped: List[Path] = []
    seen = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            deduped.append(root)
            seen.add(key)
    return deduped


def _install_skill() -> List[Path]:
    source_dir = packaged_skill_source()
    installed_paths: List[Path] = []
    known_skill_names = [*LEGACY_PACKAGED_SKILL_NAMES, *PACKAGED_SKILL_NAMES]

    existing_roots = [root for root in _candidate_skill_roots() if root.exists()]
    if not existing_roots:
        existing_roots = [_candidate_skill_roots()[0]]

    for root in existing_roots:
        root.mkdir(parents=True, exist_ok=True)
        for skill_name in known_skill_names:
            target = root / skill_name
            if target.exists():
                shutil.rmtree(target)
        for skill_name in PACKAGED_SKILL_NAMES:
            target = root / skill_name
            shutil.copytree(source_dir / skill_name, target)
            installed_paths.append(target)

    return installed_paths


def _uninstall_skill() -> List[Path]:
    removed: List[Path] = []
    known_skill_names = [*LEGACY_PACKAGED_SKILL_NAMES, *PACKAGED_SKILL_NAMES]
    for root in _candidate_skill_roots():
        for skill_name in known_skill_names:
            target = root / skill_name
            if target.exists():
                shutil.rmtree(target)
                removed.append(target)
    return removed


def _cmd_skill(args) -> int:
    if args.install:
        installed = _install_skill()
        if installed:
            for path in installed:
                print(f"Installed skill: {path}")
        else:
            print("No skill targets were written.")
    elif args.uninstall:
        removed = _uninstall_skill()
        if removed:
            for path in removed:
                print(f"Removed skill: {path}")
        else:
            print("No skill installations found.")
    return 0


def _cmd_configure(args) -> int:
    from x_reach.config import Config

    config = Config()

    if args.from_browser:
        _configure_from_browser(args.from_browser, config)
        return 0

    if not args.key:
        raise SystemExit("configure requires either a key or --from-browser")

    value = " ".join(args.value).strip()
    if args.key == "twitter-cookies":
        if not value:
            raise SystemExit("twitter-cookies requires a cookie header string or two values")
        auth_token, ct0 = _parse_twitter_cookie_input(value)
        config.set("twitter_auth_token", auth_token)
        config.set("twitter_ct0", ct0)
        _persist_twitter_env(auth_token, ct0)
        print("Saved Twitter/X cookies to config.")
        print("Verify with: twitter status")
        return 0

    raise SystemExit(f"Unsupported configure key: {args.key}")


def _parse_twitter_cookie_input(raw: str) -> Tuple[str, str]:
    raw = raw.strip()
    if not raw:
        raise SystemExit("Twitter cookie input is empty")

    if "auth_token=" in raw or "ct0=" in raw:
        parts = {}
        for item in raw.split(";"):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            parts[key.strip()] = value.strip()
        auth_token = parts.get("auth_token")
        ct0 = parts.get("ct0")
        if auth_token and ct0:
            return auth_token, ct0
        raise SystemExit("Twitter cookie header must include both auth_token and ct0")

    values = raw.split()
    if len(values) == 2:
        return values[0], values[1]
    raise SystemExit("Provide either `auth_token=...; ct0=...` or `AUTH_TOKEN CT0`")


def _configure_from_browser(browser: str, config) -> None:
    try:
        from x_reach.cookie_extract import extract_all
    except Exception as exc:
        raise SystemExit(f"Browser import support is unavailable: {exc}")

    try:
        extracted = extract_all(browser)
    except Exception as exc:
        raise SystemExit(str(exc))

    twitter = extracted.get("twitter") or {}
    auth_token = twitter.get("auth_token")
    ct0 = twitter.get("ct0")
    if not auth_token or not ct0:
        raise SystemExit(f"No Twitter/X cookies were found in {browser}")

    config.set("twitter_auth_token", auth_token)
    config.set("twitter_ct0", ct0)
    _persist_twitter_env(auth_token, ct0)
    print(f"Imported Twitter/X cookies from {browser}.")
    print("Verify with: twitter status")


def _persist_twitter_env(auth_token: str, ct0: str) -> None:
    """Persist Twitter credentials for twitter-cli across future shells."""

    os.environ["TWITTER_AUTH_TOKEN"] = auth_token
    os.environ["TWITTER_CT0"] = ct0
    os.environ["AUTH_TOKEN"] = auth_token
    os.environ["CT0"] = ct0

    if sys.platform != "win32":
        return

    for key, value in (
        ("TWITTER_AUTH_TOKEN", auth_token),
        ("TWITTER_CT0", ct0),
        ("AUTH_TOKEN", auth_token),
        ("CT0", ct0),
    ):
        try:
            subprocess.run(
                ["setx", key, value],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except Exception:
            pass


def _cmd_doctor(args) -> int:
    from x_reach.config import Config
    from x_reach.doctor import check_all, doctor_exit_code, format_report, make_doctor_payload

    config = Config()
    required_channels, require_all = _resolve_doctor_requirements(args)
    results = check_all(config, probe=args.probe)
    if args.json:
        _print_json(
            make_doctor_payload(
                results,
                probe=args.probe,
                required_channels=required_channels,
                require_all=require_all,
            )
        )
    else:
        print(
            format_report(
                results,
                probe=args.probe,
                required_channels=required_channels,
                require_all=require_all,
            )
        )
    return doctor_exit_code(
        results,
        required_channels=required_channels,
        require_all=require_all,
    )


def _compact_text_snippet(text: str | None, max_chars: int | None) -> str | None:
    if max_chars is None or not text:
        return None
    snippet = " ".join(text.split())
    if not snippet:
        return None
    if len(snippet) > max_chars:
        return f"{snippet[:max_chars]}..."
    return snippet


def _render_collect_text(payload: CollectionResult, max_text_chars: int | None = None) -> str:
    lines = [
        "X Reach Collection",
        "========================================",
        f"Channel: {payload['channel']}",
        f"Operation: {payload['operation']}",
        f"OK: {'yes' if payload['ok'] else 'no'}",
    ]
    if payload["ok"]:
        lines.append(f"Items: {len(payload['items'])}")
        for item in payload["items"][:5]:
            title = item.get("title") or item.get("id")
            url = item.get("url") or ""
            lines.append(f"  - {title} {url}".rstrip())
            snippet = _compact_text_snippet(item.get("text"), max_text_chars)
            if snippet:
                lines.append(f"    {snippet}")
    else:
        error = payload["error"]
        code = error["code"] if error else "unknown"
        message = error["message"] if error else ""
        lines.append(f"Error: {code} - {message}".rstrip())
    return "\n".join(lines)


def _cmd_collect(args) -> int:
    if getattr(args, "spec", None):
        return _cmd_collect_spec(args)
    if not args.operation or not args.input:
        print("collect requires --operation and --input unless --spec is used", file=sys.stderr)
        return 2
    if getattr(args, "dry_run", False) or getattr(args, "output_dir", None) or getattr(args, "resume", False):
        print("dry-run, output-dir, and resume are only supported with --spec", file=sys.stderr)
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
        _print_json(payload)
    else:
        print(_render_collect_text(payload, max_text_chars=args.max_text_chars))

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


def _cmd_collect_spec(args) -> int:
    if args.operation or args.input:
        print("collect --spec cannot be combined with --operation or --input", file=sys.stderr)
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
        )
    except MissionSpecError as exc:
        print(f"Could not run mission spec: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _print_json(payload)
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


def _cmd_plan(args) -> int:
    if args.plan_command == "candidates":
        return _cmd_plan_candidates(args)
    print("plan requires a subcommand", file=sys.stderr)
    return 2


def _cmd_plan_candidates(args) -> int:
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
        )
    except CandidatePlanError as exc:
        if args.json:
            _print_json(_candidate_error_payload(args, str(exc)))
            return 2
        print(f"Could not plan candidates: {exc}", file=sys.stderr)
        return 2

    if args.json:
        _print_json(payload)
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
        "limit": args.limit,
        "summary_only": bool(args.summary_only),
        "fields": fields,
        "max_per_author": args.max_per_author,
        "prefer_originals": bool(args.prefer_originals),
        "drop_noise": bool(args.drop_noise),
        "drop_title_duplicates": bool(args.drop_title_duplicates),
        "require_query_match": bool(args.require_query_match),
        "min_seen_in": args.min_seen_in,
        "candidates": [],
        "error": {
            "code": "candidate_plan_error",
            "message": message,
        },
    }


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
        "summary": None,
        "error": {
            "code": "batch_plan_error",
            "message": message,
        },
    }


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


def _cmd_scout(args) -> int:
    if not args.plan_only:
        message = "scout currently requires --plan-only"
        if args.json:
            _print_json(_scout_error_payload(args, message))
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
            _print_json(_scout_error_payload(args, message))
        else:
            print(message, file=sys.stderr)
        return 2
    if args.json:
        _print_json(payload)
    else:
        print(render_scout_text(payload))
    return 0


def _cmd_batch(args) -> int:
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
            )
        except BatchPlanError as exc:
            if args.json:
                _print_json(_batch_error_payload(args, str(exc)))
            else:
                print(f"Could not validate batch plan: {exc}", file=sys.stderr)
            return 2
        if args.json:
            _print_json(payload)
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
        )
    except BatchPlanError as exc:
        print(f"Could not run batch plan: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _print_json(payload)
    else:
        print(render_batch_text(payload))
    return exit_code


def _cmd_ledger(args) -> int:
    if args.ledger_command == "merge":
        return _cmd_ledger_merge(args)
    if args.ledger_command == "validate":
        return _cmd_ledger_validate(args)
    if args.ledger_command == "summarize":
        return _cmd_ledger_summarize(args)
    if args.ledger_command == "query":
        return _cmd_ledger_query(args)
    if args.ledger_command == "append":
        return _cmd_ledger_append(args)
    print("ledger requires a subcommand", file=sys.stderr)
    return 2


def _cmd_ledger_merge(args) -> int:
    try:
        payload = merge_ledger_inputs(args.input, args.output)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Could not merge ledgers: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _print_json(payload)
    else:
        print(
            "\n".join(
                [
                    "X Reach Ledger Merge",
                    "========================================",
                    f"Input: {payload['input']}",
                    f"Output: {payload['output']}",
                    f"Files merged: {payload['files_merged']}",
                    f"Records written: {payload['records_written']}",
                ]
            )
        )
    return 0


def _cmd_ledger_validate(args) -> int:
    try:
        payload = validate_ledger_input(args.input, require_metadata=args.require_metadata)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Could not validate ledger: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _print_json(payload)
    else:
        print(
            "\n".join(
                [
                    "X Reach Ledger Validate",
                    "========================================",
                    f"Input: {payload['input']}",
                    f"Valid: {'yes' if payload['valid'] else 'no'}",
                    f"Require metadata: {'yes' if payload['require_metadata'] else 'no'}",
                    f"Files checked: {payload['files_checked']}",
                    f"Records: {payload['records']}",
                    f"Collection results: {payload['collection_results']}",
                    f"Items seen: {payload['items_seen']}",
                    f"Invalid lines: {payload['invalid_lines']}",
                    f"Invalid records: {payload['invalid_records']}",
                    f"Large text fields: {len(payload['large_text_fields'])}",
                ]
            )
        )
    return 0 if payload["valid"] else 1


def _cmd_ledger_summarize(args) -> int:
    try:
        payload = summarize_ledger_input(args.input, filters=list(args.filter or []))
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Could not summarize ledger: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _print_json(payload)
    else:
        print(
            "\n".join(
                [
                    "X Reach Ledger Summary",
                    "========================================",
                    f"Input: {payload['input']}",
                    f"Filters: {', '.join(item['expression'] for item in payload['filters']) if payload['filters'] else 'none'}",
                    f"Records: {payload['records']}",
                    f"Records scanned: {payload['records_scanned']}",
                    f"Collection results: {payload['collection_results']}",
                    f"Items seen: {payload['items_seen']}",
                    f"Errors: {payload['error_records']}",
                    f"Metadata missing records: {payload['missing_metadata']['records']}",
                ]
            )
        )
    return 0 if payload["valid"] else 1


def _cmd_ledger_query(args) -> int:
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
        _print_json(payload)
    else:
        print(_render_ledger_query_text(payload))
    return 0


def _cmd_ledger_append(args) -> int:
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
        _print_json(payload)
    else:
        print(
            "\n".join(
                [
                    "X Reach Ledger Append",
                    "========================================",
                    f"Input: {payload['input']}",
                    f"Output: {payload['output']}",
                    f"Channel: {payload['channel']}",
                    f"Operation: {payload['operation']}",
                    f"OK: {'yes' if payload['ok'] else 'no'}",
                    f"Items: {payload['count']}",
                ]
            )
        )
    return 0


def _render_ledger_query_text(payload: dict[str, object]) -> str:
    lines = [
        "X Reach Ledger Query",
        "========================================",
        f"Input: {payload['input']}",
        f"Files checked: {payload['files_checked']}",
        f"Records scanned: {payload['records_scanned']}",
        f"Matched: {payload['matched_records']}",
        f"Returned: {payload['returned_records']}",
    ]
    raw_filters = payload.get("filters")
    filters = raw_filters if isinstance(raw_filters, list) else []
    if filters:
        lines.append(
            "Filters: " + "; ".join(
                str(filter_payload.get("expression"))
                for filter_payload in filters
                if isinstance(filter_payload, dict) and filter_payload.get("expression")
            )
        )
    raw_fields = payload.get("fields")
    fields = raw_fields if isinstance(raw_fields, list) else None
    if fields:
        lines.append(f"Fields: {', '.join(str(field) for field in fields)}")
    raw_matches = payload.get("matches")
    matches = raw_matches if isinstance(raw_matches, list) else []
    for match in matches[:5]:
        lines.append(json.dumps(match, ensure_ascii=False))
    return "\n".join(lines)


def _render_channels_text(contracts: Sequence[dict]) -> str:
    lines = [
        "X Reach Channels",
        "========================================",
        "",
    ]
    for contract in contracts:
        lines.append(contract["name"])
        lines.append(f"  {contract['description']}")
        lines.append(f"  backends: {', '.join(contract['backends']) or 'none'}")
        lines.append(
            f"  auth: {contract['auth_kind']} | entrypoint: {contract['entrypoint_kind']}"
        )
        if contract.get("operations"):
            lines.append(f"  operations: {', '.join(contract['operations'])}")
        operation_contracts = contract.get("operation_contracts") or {}
        for operation in contract.get("operations") or []:
            details = operation_contracts.get(operation) or {}
            option_names = [option.get("name") for option in details.get("options", []) if option.get("name")]
            option_suffix = f" | options: {', '.join(option_names)}" if option_names else ""
            lines.append(
                "  "
                f"- {operation}: input={details.get('input_kind', 'text')} "
                f"| limit={'yes' if details.get('accepts_limit', False) else 'no'}"
                f"{option_suffix}"
            )
        probe_line = f"  probe: {'yes' if contract['supports_probe'] else 'no'}"
        if contract.get("supports_probe"):
            coverage = contract.get("probe_coverage") or "full"
            probe_operations = contract.get("probe_operations") or []
            probe_line += f" | coverage: {coverage}"
            if probe_operations:
                probe_line += f" | probe ops: {', '.join(probe_operations)}"
        lines.append(probe_line)
        if contract["required_commands"]:
            lines.append(f"  commands: {', '.join(contract['required_commands'])}")
        if contract["host_patterns"]:
            lines.append(f"  hosts: {', '.join(contract['host_patterns'])}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _cmd_channels(args) -> int:
    from x_reach.channels import get_all_channel_contracts, get_channel_contract

    if args.name:
        contract = get_channel_contract(args.name)
        if contract is None:
            print(f"Unknown channel: {args.name}", file=sys.stderr)
            return 2
        if args.json:
            _print_json(
                {
                    "schema_version": SCHEMA_VERSION,
                    "generated_at": utc_timestamp(),
                    "channel": contract,
                }
            )
        else:
            print(_render_channels_text([contract]))
        return 0

    contracts = get_all_channel_contracts()
    if args.json:
        _print_json(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": utc_timestamp(),
                "channels": contracts,
            }
        )
    else:
        print(_render_channels_text(contracts))
    return 0


def _cmd_schema(args) -> int:
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
        _print_json(payload)
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _cmd_export_integration(args) -> int:
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
        _print_json(payload)
    elif args.format == "powershell":
        print(render_codex_integration_powershell(payload))
    else:
        print(render_codex_integration_text(payload))
    return 0


def _cmd_uninstall(args) -> int:
    from x_reach.config import Config

    config_path = Config.CONFIG_FILE
    config_dir = Config.CONFIG_DIR
    legacy_config_path = Config.LEGACY_CONFIG_FILE
    legacy_config_dir = Config.LEGACY_CONFIG_DIR
    skill_names = [*LEGACY_PACKAGED_SKILL_NAMES, *PACKAGED_SKILL_NAMES]
    skill_paths = [root / skill_name for root in _candidate_skill_roots() for skill_name in skill_names]

    if args.dry_run:
        print("Dry-run uninstall plan:")
        if not args.keep_config:
            print(f"  Remove config dir: {config_dir}")
            if legacy_config_dir != config_dir:
                print(f"  Remove legacy config dir: {legacy_config_dir}")
        for path in skill_paths:
            if path.exists():
                print(f"  Remove skill: {path}")
        print("  Optional tool cleanup: uv tool uninstall twitter-cli")
        return 0

    removed_any = False
    if not args.keep_config and config_dir.exists():
        shutil.rmtree(config_dir)
        print(f"Removed config dir: {config_dir}")
        removed_any = True
    elif not args.keep_config and config_path.exists():
        config_path.unlink(missing_ok=True)

    if not args.keep_config and legacy_config_dir != config_dir and legacy_config_dir.exists():
        shutil.rmtree(legacy_config_dir)
        print(f"Removed legacy config dir: {legacy_config_dir}")
        removed_any = True
    elif not args.keep_config and legacy_config_path != config_path and legacy_config_path.exists():
        legacy_config_path.unlink(missing_ok=True)

    for path in skill_paths:
        if path.exists():
            shutil.rmtree(path)
            print(f"Removed skill: {path}")
            removed_any = True

    if not removed_any:
        print("Nothing to remove.")
        return 0

    print()
    print("Optional tool cleanup:")
    print("  uv tool uninstall twitter-cli")
    return 0


def _import_requests():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"urllib3 .* doesn't match a supported version!",
        )
        import requests

    return requests


def _classify_update_error(exc) -> str:
    requests = _import_requests()

    if isinstance(exc, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(exc, requests.exceptions.ConnectionError):
        text = str(exc).lower()
        markers = [
            "name or service not known",
            "temporary failure in name resolution",
            "nodename nor servname",
            "getaddrinfo failed",
            "dns",
        ]
        if any(marker in text for marker in markers):
            return "dns"
        return "connection"
    if isinstance(exc, requests.exceptions.HTTPError):
        return "http"
    return "unknown"


def _classify_github_response_error(resp) -> Optional[str]:
    if resp is None:
        return "unknown"
    if resp.status_code == 429:
        return "rate_limit"
    if resp.status_code == 403:
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining == "0":
            return "rate_limit"
        try:
            message = resp.json().get("message", "").lower()
        except Exception:
            message = ""
        if "rate limit" in message:
            return "rate_limit"
    if 500 <= resp.status_code < 600:
        return "server_error"
    return None


def _update_error_text(kind: str) -> str:
    mapping = {
        "timeout": "request timed out",
        "dns": "DNS resolution failed",
        "rate_limit": "GitHub API rate limit reached",
        "connection": "connection failed",
        "server_error": "GitHub returned a server error",
        "http": "HTTP request failed",
        "unknown": "unknown error",
    }
    return mapping.get(kind, "unknown error")


def _github_get_with_retry(url: str, timeout: int = 10, retries: int = 3, sleeper=time.sleep):
    requests = _import_requests()

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            if attempt >= retries:
                return None, _classify_update_error(exc), attempt
            sleeper(2 ** (attempt - 1))
            continue

        err = _classify_github_response_error(response)
        if err in {"rate_limit", "server_error"}:
            if attempt >= retries:
                return None, err, attempt
            delay = 2 ** (attempt - 1)
            retry_after = response.headers.get("Retry-After")
            if err == "rate_limit" and retry_after:
                try:
                    delay = max(delay, float(retry_after))
                except Exception:
                    pass
            sleeper(delay)
            continue

        return response, None, attempt

    return None, "unknown", retries


def _build_update_payload() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "command": "check-update",
        "current_version": __version__,
        "upstream_repo": UPSTREAM_REPO,
        "comparison_target": "upstream_release",
        "status": "error",
    }
    release_url = f"https://api.github.com/repos/{UPSTREAM_REPO}/releases/latest"
    commit_url = f"https://api.github.com/repos/{UPSTREAM_REPO}/commits/main"

    response, err, attempts = _github_get_with_retry(release_url, timeout=10, retries=3)
    if err:
        payload.update(
            {
                "status": "error",
                "error": _update_error_text(err),
                "error_kind": err,
                "attempts": attempts,
            }
        )
        return payload

    if response is not None and response.status_code == 200:
        release_payload = response.json()
        latest = release_payload.get("tag_name", "").lstrip("v")
        payload["latest_version"] = latest or __version__
        comparison = _compare_versions(__version__, latest)
        if latest and comparison < 0:
            payload["status"] = "update_available"
            body = release_payload.get("body", "").strip()
            payload["release_notes_preview"] = body.splitlines()[:20] if body else []
        elif latest and comparison > 0:
            payload["status"] = "ahead_of_upstream_release"
        else:
            payload["status"] = "up_to_date"
        return payload

    response, err, attempts = _github_get_with_retry(commit_url, timeout=10, retries=2)
    if err:
        payload.update(
            {
                "status": "error",
                "error": _update_error_text(err),
                "error_kind": err,
                "attempts": attempts,
            }
        )
        return payload

    if response is not None and response.status_code == 200:
        commit_payload = response.json()
        payload.update(
            {
                "status": "unknown",
                "latest_main_commit": {
                    "sha": commit_payload.get("sha", "")[:7],
                    "date": commit_payload.get("commit", {})
                    .get("committer", {})
                    .get("date", "")[:10],
                    "message": commit_payload.get("commit", {}).get("message", "").splitlines()[0],
                },
            }
        )
        return payload

    payload.update(
        {
            "status": "error",
            "error": f"GitHub returned HTTP {response.status_code if response is not None else 'unknown'}",
            "error_kind": "http",
        }
    )
    return payload


def _render_update_payload(payload: dict) -> str:
    lines = [f"Current version: v{payload['current_version']}"]
    status = payload["status"]

    if status == "error":
        attempts = payload.get("attempts")
        detail = payload.get("error", "unknown error")
        if attempts:
            lines.append(f"[WARN] Could not check releases: {detail} after {attempts} attempt(s)")
        else:
            lines.append(f"[WARN] Could not check releases: {detail}")
        return "\n".join(lines)

    if status == "update_available":
        lines.append(f"Update available: v{payload.get('latest_version', 'unknown')}")
        notes = payload.get("release_notes_preview", [])
        if notes:
            lines.append("")
            for line in notes:
                lines.append(f"  {line}")
        return "\n".join(lines)

    if status == "up_to_date":
        lines.append("Already up to date.")
        return "\n".join(lines)

    if status == "ahead_of_upstream_release":
        lines.append(
            "This fork is ahead of the latest upstream release: "
            f"v{payload.get('latest_version', 'unknown')}"
        )
        return "\n".join(lines)

    if status == "unknown":
        commit = payload.get("latest_main_commit", {})
        lines.append(
            "Latest main commit: "
            f"{commit.get('sha', '')} ({commit.get('date', '')}) {commit.get('message', '')}"
        )
        return "\n".join(lines)

    lines.append("[WARN] Unknown update status")
    return "\n".join(lines)


def _parse_version_parts(value: str) -> tuple[int, ...] | None:
    text = (value or "").strip()
    if not text:
        return None
    parts = text.split(".")
    parsed: list[int] = []
    for part in parts:
        if not part.isdigit():
            return None
        parsed.append(int(part))
    return tuple(parsed)


def _compare_versions(current: str, latest: str) -> int:
    current_parts = _parse_version_parts(current)
    latest_parts = _parse_version_parts(latest)
    if current_parts is not None and latest_parts is not None:
        width = max(len(current_parts), len(latest_parts))
        current_parts += (0,) * (width - len(current_parts))
        latest_parts += (0,) * (width - len(latest_parts))
        if current_parts < latest_parts:
            return -1
        if current_parts > latest_parts:
            return 1
        return 0
    if current == latest:
        return 0
    return -1


def _cmd_check_update(args) -> int:
    payload = _build_update_payload()
    if args.json:
        _print_json(payload)
    else:
        print(_render_update_payload(payload))
    return 1 if payload["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())


