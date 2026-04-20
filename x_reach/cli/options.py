# -*- coding: utf-8 -*-
"""Reusable parser option groups for CLI commands."""

from __future__ import annotations

import argparse

from x_reach.candidates import SORT_BY_FIRST_SEEN, SORT_BY_QUALITY_SCORE
from x_reach.scout import BUDGETS, PRESETS, QUALITY_PROFILES


def add_collect_render_args(parser: argparse.ArgumentParser) -> None:
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


def add_quality_profile_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--quality-profile",
        choices=QUALITY_PROFILES,
        help="High-signal collection profile. Broad operations default to balanced",
    )


def add_collect_persistence_args(parser: argparse.ArgumentParser) -> None:
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


def add_search_filter_args(parser: argparse.ArgumentParser) -> None:
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
    parser.add_argument("--min-likes", type=int, help="Minimum likes threshold for supported operations")
    parser.add_argument("--min-retweets", type=int, help="Minimum retweets threshold for supported operations")
    parser.add_argument("--min-views", type=int, help="Minimum views threshold applied after collection")


def add_user_posts_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--min-likes", type=int, help="Minimum likes threshold applied after timeline lookup")
    parser.add_argument("--min-retweets", type=int, help="Minimum retweets threshold applied after timeline lookup")
    parser.add_argument("--min-views", type=int, help="Minimum views threshold applied after timeline lookup")
    parser.add_argument(
        "--topic-fit",
        help="JSON file containing caller-declared topic-fit rules for deterministic timeline filtering",
    )


def add_plan_candidates_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, help="Evidence ledger JSONL input path")
    parser.add_argument(
        "--by",
        choices=["url", "normalized_url", "id", "source_item_id", "domain", "author", "post"],
        default="url",
        help="Dedupe mode. Defaults to URL, then falls back to source + id",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum candidates to return",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Return summary counts without candidate bodies",
    )
    parser.add_argument(
        "--fields",
        help="Comma-separated candidate fields to include in output",
    )
    parser.add_argument(
        "--max-per-author",
        type=int,
        help="Optional maximum number of returned candidates per author",
    )
    parser.add_argument(
        "--prefer-originals",
        action="store_true",
        help="Prefer original posts when duplicate candidates share the same dedupe key",
    )
    parser.add_argument(
        "--drop-noise",
        action="store_true",
        help="Drop candidates that match the deterministic X noise rules",
    )
    parser.add_argument(
        "--drop-title-duplicates",
        action="store_true",
        help="Drop later candidates whose normalized titles exactly match an earlier candidate",
    )
    parser.add_argument(
        "--require-query-match",
        action="store_true",
        help="Keep only candidates that still match stored query tokens",
    )
    parser.add_argument(
        "--topic-fit",
        help="JSON file containing caller-declared topic-fit rules for deterministic candidate filtering",
    )
    parser.add_argument(
        "--min-seen-in",
        type=int,
        help="Keep only candidates observed in at least N ledger sightings",
    )
    parser.add_argument(
        "--sort-by",
        choices=[SORT_BY_FIRST_SEEN, SORT_BY_QUALITY_SCORE],
        default=SORT_BY_FIRST_SEEN,
        help="Candidate order. Defaults to first_seen; quality_score is opt-in evidence-utility sorting",
    )


def add_scout_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--topic", required=True, help="Topic echo for the calling workflow")
    parser.add_argument("--budget", choices=BUDGETS, default="auto", help="Research budget hint")
    parser.add_argument(
        "--quality",
        choices=QUALITY_PROFILES,
        default="precision",
        help="Quality profile hint",
    )
    parser.add_argument("--preset", choices=PRESETS, help="Optional source-pack seed")
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Build the plan without running network collection",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable scout output")


def add_batch_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--plan", required=True, help="Research plan JSON path")
    batch_save_group = parser.add_mutually_exclusive_group()
    batch_save_group.add_argument("--save", help="Evidence ledger JSONL output path")
    batch_save_group.add_argument("--save-dir", help="Directory for sharded evidence ledger JSONL outputs")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the plan and print a non-mutating summary without collecting or writing ledger data",
    )
    parser.add_argument(
        "--shard-by",
        choices=["channel", "operation", "channel-operation"],
        help="Shard key for --save-dir outputs. Defaults to channel",
    )
    parser.add_argument("--concurrency", type=int, default=1, help="Maximum concurrent collections")
    parser.add_argument("--resume", action="store_true", help="Skip queries already saved in the ledger")
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=100,
        help="Emit checkpoint summaries after this many completed queries",
    )
    parser.add_argument(
        "--query-delay",
        dest="query_delay_seconds",
        type=float,
        help="Minimum seconds between collection starts",
    )
    parser.add_argument(
        "--query-jitter",
        dest="query_jitter_seconds",
        type=float,
        help="Maximum random extra seconds before each collection start",
    )
    parser.add_argument(
        "--throttle-cooldown",
        dest="throttle_cooldown_seconds",
        type=float,
        help="Cooldown seconds after a throttle-sensitive collection error",
    )
    parser.add_argument(
        "--throttle-error-limit",
        type=int,
        help="Skip remaining queries after this many throttle-sensitive errors; 0 disables the stop guard",
    )
    parser.add_argument(
        "--quality",
        choices=QUALITY_PROFILES,
        help="Override the plan quality profile hint",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable batch output")


def add_ledger_merge_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, help="Ledger input file or directory")
    parser.add_argument("--output", required=True, help="Merged ledger JSONL output path")
    parser.add_argument("--json", action="store_true", help="Print machine-readable merge output")


def add_ledger_validate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, help="Ledger input file or directory")
    parser.add_argument(
        "--require-metadata",
        action="store_true",
        help="Fail validation when collection records lack intent, query_id, or source_role",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output")


def add_ledger_summarize_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, help="Ledger input file or directory")
    parser.add_argument(
        "--filter",
        action="append",
        default=[],
        help='Repeatable filter such as "intent == official_docs" or "source_role == social_search"',
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary output")


def add_ledger_query_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, help="Ledger input file or directory")
    parser.add_argument(
        "--filter",
        action="append",
        default=[],
        help='Repeatable filter such as "channel == twitter" or "ok == true"',
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional maximum number of matching records to return",
    )
    parser.add_argument(
        "--fields",
        help="Comma-separated projection fields such as channel,source.file,result.items[*].url",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable query output")


def add_ledger_append_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, help="CollectionResult JSON input file")
    parser.add_argument("--output", required=True, help="Evidence ledger JSONL output path")
    parser.add_argument(
        "--run-id",
        help="Evidence ledger run ID. Defaults to X_REACH_RUN_ID (or legacy AGENT_REACH_RUN_ID) or a UTC timestamp",
    )
    parser.add_argument("--intent", help="Optional evidence ledger intent label")
    parser.add_argument("--query-id", help="Optional evidence ledger query ID")
    parser.add_argument("--source-role", help="Optional evidence ledger source role label")
    parser.add_argument("--json", action="store_true", help="Print machine-readable append output")
