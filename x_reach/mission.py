# -*- coding: utf-8 -*-
"""Mission-spec runtime for X-focused collection jobs."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Callable, Sequence

from x_reach._version import __version__
from x_reach.batch import (
    BatchPlanError,
    normalize_pacing_config,
    run_batch_plan,
    validate_batch_plan,
)
from x_reach.candidates import CandidatePlanError, build_candidates_payload
from x_reach.client import XReachClient
from x_reach.evidence_scoring import (
    quality_reason_counts as count_quality_reasons,
)
from x_reach.evidence_scoring import (
    score_candidate,
)
from x_reach.high_signal import QUALITY_PROFILES
from x_reach.ledger import default_run_id, iter_ledger_records, merge_ledger_inputs
from x_reach.schemas import SCHEMA_VERSION, utc_timestamp


class MissionSpecError(Exception):
    """Raised when a mission spec cannot be normalized or executed."""


_QUALITY_ALIASES = {
    "research_high_precision": "precision",
    "high_precision": "precision",
    "high-precision": "precision",
    "precision": "precision",
    "research_balanced": "balanced",
    "balanced": "balanced",
    "broad_recall": "recall",
    "broad-recall": "recall",
    "recall": "recall",
}
_RAW_MODES = {"full", "minimal", "none"}
_ITEM_TEXT_MODES = {"full", "snippet", "none"}
_JUDGE_MODES = {"llm", "vlm", "external"}
_JUDGE_FALLBACK_POLICIES = {"keep_ranked", "mark_unjudged"}
_DEFAULT_JUDGE_LABELS = [
    "primary_evidence",
    "secondary_evidence",
    "chatter",
    "promotion",
    "off_topic",
]
_DEFAULT_TARGET_POSTS = 100
_MISSION_DIR = ".x-reach/missions"
_JUDGE_OUTPUT = "judge.jsonl"
_JSONL_OUTPUTS = {"raw.jsonl", "canonical.jsonl", "ranked.jsonl", _JUDGE_OUTPUT}
_SUMMARY_OUTPUT = "summary.md"
_MANIFEST_OUTPUT = "mission-result.json"


def build_mission_plan_payload(
    spec_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Load a mission spec and return the deterministic execution plan."""

    source_path = Path(spec_path)
    raw_spec = _load_spec(source_path)
    normalized = _normalize_spec(raw_spec, source_path=source_path, run_id=run_id)
    resolved_output_dir = _resolve_output_dir(
        output_dir,
        source_path=source_path,
        run_id=str(normalized["run_id"]),
    )
    plan = _build_batch_plan(normalized)
    paths = _mission_paths(resolved_output_dir)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "command": "collect spec",
        "cli_version": __version__,
        "dry_run": True,
        "spec": str(source_path),
        "output_dir": str(resolved_output_dir),
        "run_id": normalized["run_id"],
        "objective": normalized["objective"],
        "quality_profile": normalized["quality_profile"],
        "target_posts": normalized["target_posts"],
        "pacing": normalized["pacing"],
        "judge": normalized["judge"],
        "query_count": len(plan["queries"]),
        "normalized_spec": normalized,
        "batch_plan": plan,
        "outputs": {name: str(path) for name, path in paths.items()},
    }


def run_mission_spec(
    spec_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    run_id: str | None = None,
    resume: bool = False,
    dry_run: bool = False,
    concurrency: int = 1,
    checkpoint_every: int = 25,
    query_delay_seconds: float | None = None,
    query_jitter_seconds: float | None = None,
    throttle_cooldown_seconds: float | None = None,
    throttle_error_limit: int | None = None,
    client_factory: Callable[[], XReachClient] | None = None,
) -> dict[str, Any]:
    """Execute a mission spec and write raw, canonical, and curated artifacts."""

    plan_payload = build_mission_plan_payload(spec_path, output_dir=output_dir, run_id=run_id)
    _apply_pacing_overrides(
        plan_payload,
        query_delay_seconds=query_delay_seconds,
        query_jitter_seconds=query_jitter_seconds,
        throttle_cooldown_seconds=throttle_cooldown_seconds,
        throttle_error_limit=throttle_error_limit,
    )
    if dry_run:
        return plan_payload

    if concurrency < 1:
        raise MissionSpecError("concurrency must be greater than or equal to 1")
    if checkpoint_every < 1:
        raise MissionSpecError("checkpoint_every must be greater than or equal to 1")

    mission_dir = Path(str(plan_payload["output_dir"]))
    paths = {name: Path(path) for name, path in plan_payload["outputs"].items()}
    raw_dir = paths["raw_dir"]
    mission_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    normalized_spec = plan_payload["normalized_spec"]
    batch_plan = plan_payload["batch_plan"]
    _write_json(paths["normalized_spec"], normalized_spec)
    _write_json(paths["batch_plan"], batch_plan)
    _write_json(
        paths["state"],
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_timestamp(),
            "status": "running",
            "run_id": plan_payload["run_id"],
            "spec": str(plan_payload["spec"]),
            "output_dir": str(mission_dir),
        },
    )

    try:
        validate_batch_plan(paths["batch_plan"])
        batch_payload, batch_exit_code = run_batch_plan(
            paths["batch_plan"],
            save_dir=raw_dir,
            shard_by="channel-operation",
            concurrency=concurrency,
            resume=resume,
            checkpoint_every=checkpoint_every,
            query_delay_seconds=query_delay_seconds,
            query_jitter_seconds=query_jitter_seconds,
            throttle_cooldown_seconds=throttle_cooldown_seconds,
            throttle_error_limit=throttle_error_limit,
            client_factory=client_factory,
        )
        merge_payload = merge_ledger_inputs(raw_dir, paths["raw_jsonl"])
        canonical_summary = _write_canonical_jsonl(paths["raw_jsonl"], paths["canonical_jsonl"])
        curated_payload = _build_curated_payload(paths["raw_jsonl"], normalized_spec)
        coverage_initial = _coverage_analysis(
            curated_payload,
            normalized_spec,
            existing_queries=batch_plan["queries"],
        )
        coverage_plan: dict[str, Any] | None = None
        coverage_batch_payload: dict[str, Any] | None = None
        coverage_exit_code = 0
        if coverage_initial.get("enabled") and coverage_initial.get("gap_count"):
            coverage_plan = _build_coverage_gap_plan(
                normalized_spec,
                coverage_initial,
                existing_queries=batch_plan["queries"],
            )
            if coverage_plan["queries"]:
                _write_json(paths["coverage_batch_plan"], coverage_plan)
                validate_batch_plan(paths["coverage_batch_plan"])
                coverage_batch_payload, coverage_exit_code = run_batch_plan(
                    paths["coverage_batch_plan"],
                    save_dir=raw_dir,
                    shard_by="channel-operation",
                    concurrency=concurrency,
                    resume=resume,
                    checkpoint_every=checkpoint_every,
                    query_delay_seconds=query_delay_seconds,
                    query_jitter_seconds=query_jitter_seconds,
                    throttle_cooldown_seconds=throttle_cooldown_seconds,
                    throttle_error_limit=throttle_error_limit,
                    client_factory=client_factory,
                )
                merge_payload = merge_ledger_inputs(raw_dir, paths["raw_jsonl"])
                canonical_summary = _write_canonical_jsonl(paths["raw_jsonl"], paths["canonical_jsonl"])
                curated_payload = _build_curated_payload(paths["raw_jsonl"], normalized_spec)
        batch_payload = _combine_batch_payloads(batch_payload, coverage_batch_payload)
        batch_exit_code = max(batch_exit_code, coverage_exit_code)
        coverage_payload = _build_coverage_payload(
            initial=coverage_initial,
            final=_coverage_analysis(
                curated_payload,
                normalized_spec,
                existing_queries=[*batch_plan["queries"], *((coverage_plan or {}).get("queries") or [])],
            ),
            coverage_plan=coverage_plan,
            coverage_batch_payload=coverage_batch_payload,
        )
        _write_ranked_jsonl(paths["ranked_jsonl"], curated_payload["ranked_candidates"])
        judge_payload, judge_records = _build_judge_payload(curated_payload, normalized_spec)
        if judge_payload.get("enabled"):
            _write_judge_jsonl(paths["judge_jsonl"], judge_records)
        summary_text = _render_summary_markdown(
            plan_payload=plan_payload,
            batch_payload=batch_payload,
            merge_payload=merge_payload,
            canonical_summary=canonical_summary,
            curated_payload=curated_payload,
            coverage_payload=coverage_payload,
            judge_payload=judge_payload,
            batch_exit_code=batch_exit_code,
        )
        paths["summary_md"].write_text(summary_text, encoding="utf-8", newline="\n")
        result_payload = _build_result_payload(
            plan_payload=plan_payload,
            batch_payload=batch_payload,
            merge_payload=merge_payload,
            canonical_summary=canonical_summary,
            curated_payload=curated_payload,
            coverage_payload=coverage_payload,
            judge_payload=judge_payload,
            batch_exit_code=batch_exit_code,
            outputs=paths,
            resume=resume,
            concurrency=concurrency,
            checkpoint_every=checkpoint_every,
        )
        _write_json(paths["manifest"], result_payload)
        _write_json(
            paths["state"],
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": utc_timestamp(),
                "status": "finished",
                "run_id": plan_payload["run_id"],
                "ok": result_payload["ok"],
                "manifest": str(paths["manifest"]),
            },
        )
        return result_payload
    except (BatchPlanError, CandidatePlanError, OSError, ValueError) as exc:
        _write_json(
            paths["state"],
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": utc_timestamp(),
                "status": "error",
                "run_id": plan_payload["run_id"],
                "error": str(exc),
            },
        )
        raise MissionSpecError(str(exc)) from exc


def render_mission_text(payload: dict[str, Any]) -> str:
    """Render mission runtime output for humans."""

    if payload.get("dry_run"):
        return "\n".join(
            [
                "X Reach Mission Plan",
                "========================================",
                f"Spec: {payload['spec']}",
                f"Output dir: {payload['output_dir']}",
                f"Run ID: {payload['run_id']}",
                f"Objective: {payload.get('objective') or '(none)'}",
                f"Quality: {payload['quality_profile']}",
                f"Target posts: {payload['target_posts']}",
                f"Pacing: {_render_mission_pacing(payload.get('pacing') or {})}",
                f"Queries: {payload['query_count']}",
            ]
        )

    summary = payload.get("summary") or {}
    outputs = payload.get("outputs") or {}
    return "\n".join(
        [
            "X Reach Mission",
            "========================================",
            f"Spec: {payload['spec']}",
            f"Output dir: {payload['output_dir']}",
            f"Run ID: {payload['run_id']}",
            f"OK: {'yes' if payload.get('ok') else 'no'}",
            f"Queries: {summary.get('queries_total', 0)} total, {summary.get('queries_ok', 0)} ok, {summary.get('queries_errors', 0)} errors, {summary.get('queries_skipped', 0)} skipped",
            f"Items: {summary.get('items_seen', 0)} seen, {summary.get('canonical_items', 0)} canonical, {summary.get('ranked_candidates', 0)} ranked",
            f"Pacing: {_render_mission_pacing(payload.get('pacing') or {})}",
            f"Coverage: {summary.get('coverage_gap_queries', 0)} gap queries, {summary.get('coverage_final_gaps', 0)} final gaps",
            f"Raw ledger: {outputs.get('raw_jsonl', '')}",
            f"Ranked posts: {outputs.get('ranked_jsonl', '')}",
            f"Summary: {outputs.get('summary_md', '')}",
        ]
    )


def _render_mission_pacing(pacing: dict[str, Any]) -> str:
    parts = [
        f"delay={pacing.get('query_delay_seconds', 0)}s",
        f"jitter={pacing.get('query_jitter_seconds', 0)}s",
        f"throttle_cooldown={pacing.get('throttle_cooldown_seconds', 0)}s",
        f"throttle_error_limit={pacing.get('throttle_error_limit', 0)}",
    ]
    if pacing.get("waits_applied") or pacing.get("throttle_sensitive_errors"):
        parts.extend(
            [
                f"waits={pacing.get('waits_applied', 0)}",
                f"throttle_sensitive_errors={pacing.get('throttle_sensitive_errors', 0)}",
                f"guard={'yes' if pacing.get('throttle_guard_triggered') else 'no'}",
            ]
        )
    return ", ".join(parts)


def _load_spec(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise MissionSpecError(f"Could not read mission spec: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise MissionSpecError(f"Invalid mission spec JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise MissionSpecError("mission spec must be a JSON object")
    return payload


def _normalize_spec(
    raw_spec: dict[str, Any],
    *,
    source_path: Path,
    run_id: str | None,
) -> dict[str, Any]:
    queries = _normalize_queries(raw_spec.get("queries"))
    if not queries:
        raise MissionSpecError("mission spec requires at least one query")
    target_posts = _positive_int(raw_spec.get("target_posts"), default=_DEFAULT_TARGET_POSTS, name="target_posts")
    quality_profile = _normalize_quality_profile(raw_spec.get("quality_profile"))
    exclude = _mapping(raw_spec.get("exclude"))
    diversity = _mapping(raw_spec.get("diversity"))
    coverage = _mapping(raw_spec.get("coverage"))
    judge = _normalize_judge(raw_spec.get("judge"), target_posts=target_posts)
    pacing = _normalize_pacing(raw_spec.get("pacing"))
    retention = _mapping(raw_spec.get("retention"))
    time_range = _mapping(raw_spec.get("time_range"))
    outputs = _normalize_outputs(raw_spec.get("outputs"))
    languages = _normalize_languages(raw_spec.get("languages"))
    raw_mode = _normalize_choice(retention.get("raw_mode") or raw_spec.get("raw_mode") or "full", _RAW_MODES, "raw_mode")
    item_text_mode = _normalize_choice(
        retention.get("item_text_mode") or raw_spec.get("item_text_mode") or "full",
        _ITEM_TEXT_MODES,
        "item_text_mode",
    )
    item_text_max_chars = _optional_positive_int(
        retention.get("item_text_max_chars") or raw_spec.get("item_text_max_chars"),
        "item_text_max_chars",
    )
    raw_max_bytes = _optional_positive_int(retention.get("raw_max_bytes") or raw_spec.get("raw_max_bytes"), "raw_max_bytes")
    if item_text_max_chars is not None and item_text_mode != "snippet":
        raise MissionSpecError("item_text_max_chars requires item_text_mode=snippet")
    return {
        "schema_version": SCHEMA_VERSION,
        "source": str(source_path),
        "run_id": str(run_id or raw_spec.get("run_id") or default_run_id()),
        "objective": _optional_text(raw_spec.get("objective")),
        "queries": queries,
        "time_range": {
            "since": _optional_text(time_range.get("since") or raw_spec.get("since")),
            "until": _optional_text(time_range.get("until") or raw_spec.get("until")),
        },
        "languages": languages,
        "target_posts": target_posts,
        "quality_profile": quality_profile,
        "exclude": {
            "keywords": _normalize_text_list(exclude.get("keywords")),
            "drop_retweets": _bool_or_default(exclude.get("drop_retweets"), True),
            "drop_replies": _bool_or_default(exclude.get("drop_replies"), True),
            "drop_links": _bool_or_default(exclude.get("drop_links"), False),
            "drop_low_content_posts": _bool_or_default(
                exclude.get("drop_low_content_posts"),
                quality_profile in {"precision", "balanced"},
            ),
            "max_same_author_posts": _optional_positive_int(exclude.get("max_same_author_posts"), "max_same_author_posts"),
            "min_likes": _optional_nonnegative_int(exclude.get("min_likes"), "min_likes"),
            "min_retweets": _optional_nonnegative_int(exclude.get("min_retweets"), "min_retweets"),
            "min_views": _optional_nonnegative_int(exclude.get("min_views"), "min_views"),
        },
        "diversity": {
            "max_posts_per_thread": _optional_positive_int(diversity.get("max_posts_per_thread"), "max_posts_per_thread"),
            "max_posts_per_author": _optional_positive_int(diversity.get("max_posts_per_author"), "max_posts_per_author"),
            "max_posts_per_url": _optional_positive_int(diversity.get("max_posts_per_url"), "max_posts_per_url"),
            "min_seen_in": _optional_positive_int(diversity.get("min_seen_in"), "min_seen_in"),
            "require_topic_spread": _bool_or_default(diversity.get("require_topic_spread"), False),
        },
        "coverage": _normalize_coverage(coverage, target_posts=target_posts),
        "judge": judge,
        "pacing": pacing,
        "retention": {
            "raw_mode": raw_mode,
            "raw_max_bytes": raw_max_bytes,
            "item_text_mode": item_text_mode,
            "item_text_max_chars": item_text_max_chars,
        },
        "require_query_match": _bool_or_default(raw_spec.get("require_query_match"), quality_profile != "recall"),
        "failure_policy": str(raw_spec.get("failure_policy") or "partial"),
        "outputs": outputs,
    }


def _normalize_queries(raw_queries: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_queries, list):
        return []
    queries: list[dict[str, Any]] = []
    for index, raw_query in enumerate(raw_queries, start=1):
        if isinstance(raw_query, str):
            text = raw_query.strip()
            if text:
                queries.append({"input": text})
            continue
        if not isinstance(raw_query, dict):
            raise MissionSpecError(f"query {index} must be a string or object")
        input_value = raw_query.get("input") or raw_query.get("query")
        if not isinstance(input_value, str) or not input_value.strip():
            raise MissionSpecError(f"query {index} requires input or query")
        query = dict(raw_query)
        query["input"] = input_value.strip()
        query.pop("query", None)
        queries.append(query)
    return queries


def _normalize_coverage(raw_coverage: dict[str, Any], *, target_posts: int) -> dict[str, Any]:
    enabled_value = raw_coverage.get("enabled")
    if enabled_value is None:
        enabled_value = raw_coverage.get("gap_fill")
    enabled = _bool_or_default(enabled_value, False)
    max_rounds = _optional_positive_int(raw_coverage.get("max_rounds"), "coverage.max_rounds") or 1
    if max_rounds != 1:
        raise MissionSpecError("coverage.max_rounds currently supports only 1")
    min_posts_per_topic = (
        _optional_positive_int(raw_coverage.get("min_posts_per_topic"), "coverage.min_posts_per_topic") or 1
    )
    max_queries = _optional_nonnegative_int(raw_coverage.get("max_queries"), "coverage.max_queries")
    if max_queries is None:
        max_queries = 4
    if enabled and max_queries < 1:
        raise MissionSpecError("coverage.max_queries must be greater than or equal to 1 when coverage is enabled")
    return {
        "enabled": enabled,
        "max_rounds": max_rounds,
        "max_queries": max_queries,
        "min_ranked_posts": (
            _optional_positive_int(raw_coverage.get("min_ranked_posts"), "coverage.min_ranked_posts")
            or target_posts
        ),
        "min_posts_per_topic": min_posts_per_topic,
        "probe_limit": (
            _optional_positive_int(raw_coverage.get("probe_limit"), "coverage.probe_limit")
            or min(max(math.ceil(target_posts / 2), 5), 25)
        ),
        "topics": _normalize_coverage_topics(
            raw_coverage.get("topics") or raw_coverage.get("required_topics"),
            default_min_posts=min_posts_per_topic,
        ),
    }


def _normalize_pacing(raw_pacing: Any) -> dict[str, Any]:
    try:
        return normalize_pacing_config(raw_pacing)
    except BatchPlanError as exc:
        raise MissionSpecError(str(exc)) from exc


def _apply_pacing_overrides(
    plan_payload: dict[str, Any],
    *,
    query_delay_seconds: float | None,
    query_jitter_seconds: float | None,
    throttle_cooldown_seconds: float | None,
    throttle_error_limit: int | None,
) -> None:
    if all(
        value is None
        for value in (
            query_delay_seconds,
            query_jitter_seconds,
            throttle_cooldown_seconds,
            throttle_error_limit,
        )
    ):
        return
    normalized_spec = plan_payload["normalized_spec"]
    try:
        pacing = normalize_pacing_config(
            normalized_spec.get("pacing"),
            query_delay_seconds=query_delay_seconds,
            query_jitter_seconds=query_jitter_seconds,
            throttle_cooldown_seconds=throttle_cooldown_seconds,
            throttle_error_limit=throttle_error_limit,
        )
    except BatchPlanError as exc:
        raise MissionSpecError(str(exc)) from exc
    normalized_spec["pacing"] = pacing
    plan_payload["pacing"] = pacing
    plan_payload["batch_plan"]["pacing"] = pacing


def _normalize_judge(raw_judge: Any, *, target_posts: int) -> dict[str, Any]:
    judge = _mapping(raw_judge)
    enabled = _bool_or_default(judge.get("enabled"), False)
    mode = str(judge.get("mode") or "llm").strip().casefold().replace("-", "_")
    if mode not in _JUDGE_MODES:
        raise MissionSpecError(f"judge.mode must be one of: {', '.join(sorted(_JUDGE_MODES))}")
    fallback_policy = str(judge.get("fallback_policy") or "keep_ranked").strip().casefold().replace("-", "_")
    if fallback_policy not in _JUDGE_FALLBACK_POLICIES:
        choices = ", ".join(sorted(_JUDGE_FALLBACK_POLICIES))
        raise MissionSpecError(f"judge.fallback_policy must be one of: {choices}")
    candidate_limit = (
        _optional_positive_int(judge.get("candidate_limit") or judge.get("limit"), "judge.candidate_limit")
        or min(target_posts, 20)
    )
    labels = _normalize_text_list(judge.get("labels") or judge.get("categories"))
    return {
        "enabled": enabled,
        "mode": mode,
        "provider": _optional_text(judge.get("provider")),
        "model": _optional_text(judge.get("model")),
        "candidate_limit": candidate_limit,
        "intent": _optional_text(judge.get("intent") or judge.get("task")),
        "criteria": _normalize_judge_criteria(judge.get("criteria")),
        "labels": labels or list(_DEFAULT_JUDGE_LABELS),
        "fallback_policy": fallback_policy,
        "result_schema": "judge-result",
    }


def _normalize_judge_criteria(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise MissionSpecError("judge.criteria must be a list")
    criteria: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(value, start=1):
        if isinstance(item, str):
            description = item.strip()
            if not description:
                continue
            criterion_id = _slugify(description) or f"criterion-{index}"
            required = True
        elif isinstance(item, dict):
            description = _optional_text(item.get("description") or item.get("prompt") or item.get("label"))
            criterion_id = _optional_text(item.get("id") or item.get("name"))
            if description is None:
                raise MissionSpecError(f"judge criterion {index} requires description, prompt, or label")
            criterion_id = criterion_id or _slugify(description) or f"criterion-{index}"
            required = _bool_or_default(item.get("required"), True)
        else:
            raise MissionSpecError(f"judge criterion {index} must be a string or object")
        if criterion_id in seen:
            continue
        criteria.append(
            {
                "id": criterion_id,
                "description": description,
                "required": required,
            }
        )
        seen.add(criterion_id)
    return criteria


def _normalize_coverage_topics(raw_topics: Any, *, default_min_posts: int) -> list[dict[str, Any]]:
    if raw_topics is None:
        return []
    if not isinstance(raw_topics, list):
        raise MissionSpecError("coverage.topics must be a list")
    topics: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_topic in enumerate(raw_topics, start=1):
        if isinstance(raw_topic, str):
            label = raw_topic.strip()
            if not label:
                continue
            topic = {
                "label": label,
                "terms": [label],
                "queries": [],
                "min_posts": default_min_posts,
                "probe_limit": None,
            }
        elif isinstance(raw_topic, dict):
            label = _optional_text(raw_topic.get("label") or raw_topic.get("name") or raw_topic.get("topic"))
            terms = _normalize_text_list(raw_topic.get("terms") or raw_topic.get("keywords") or raw_topic.get("any"))
            queries = _normalize_text_list(raw_topic.get("queries"))
            if label is None and terms:
                label = terms[0]
            if label is None and queries:
                label = queries[0]
            if label is None:
                raise MissionSpecError(f"coverage topic {index} requires label, terms, or queries")
            if not terms:
                terms = [label]
            topic = {
                "label": label,
                "terms": terms,
                "queries": queries,
                "min_posts": _optional_positive_int(raw_topic.get("min_posts"), f"coverage topic {index} min_posts")
                or default_min_posts,
                "probe_limit": _optional_positive_int(raw_topic.get("probe_limit"), f"coverage topic {index} probe_limit"),
            }
        else:
            raise MissionSpecError(f"coverage topic {index} must be a string or object")
        key = _slugify(topic["label"]) or str(index)
        if key in seen:
            continue
        topic["topic_id"] = key
        topics.append(topic)
        seen.add(key)
    return topics


def _build_batch_plan(spec: dict[str, Any]) -> dict[str, Any]:
    expanded_queries = _expanded_query_specs(spec)
    per_query_limit = max(math.ceil(int(spec["target_posts"]) / max(len(expanded_queries), 1)), 1)
    exclude_flags = _search_exclude_flags(spec["exclude"])
    plan_queries: list[dict[str, Any]] = []
    for index, query in enumerate(expanded_queries, start=1):
        limit = _optional_positive_int(query.get("limit"), "limit") or per_query_limit
        query_id = str(query.get("query_id") or f"q{index:02d}")
        plan_query: dict[str, Any] = {
            "query_id": query_id,
            "channel": "twitter",
            "operation": "search",
            "input": query["input"],
            "limit": limit,
            "intent": query.get("intent") or _mission_intent(spec),
            "source_role": query.get("source_role") or "mission_broad_recall",
            "quality_profile": spec["quality_profile"],
            "raw_mode": spec["retention"]["raw_mode"],
            "item_text_mode": spec["retention"]["item_text_mode"],
        }
        for name in ("raw_max_bytes", "item_text_max_chars"):
            if spec["retention"].get(name) is not None:
                plan_query[name] = spec["retention"][name]
        for name in ("since", "until"):
            value = query.get(name) if query.get(name) is not None else spec["time_range"].get(name)
            if value is not None:
                plan_query[name] = value
        if query.get("lang") is not None:
            plan_query["lang"] = query["lang"]
        if exclude_flags:
            plan_query["exclude"] = exclude_flags
        for name in ("min_likes", "min_retweets", "min_views"):
            value = query.get(name) if query.get(name) is not None else spec["exclude"].get(name)
            if value is not None:
                plan_query[name] = value
        plan_queries.append(plan_query)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "run_id": spec["run_id"],
        "objective": spec.get("objective"),
        "quality_profile": spec["quality_profile"],
        "failure_policy": spec["failure_policy"],
        "pacing": spec["pacing"],
        "metadata": {
            "intent": _mission_intent(spec),
            "source_role": "mission_broad_recall",
            "query_id_prefix": _slugify(spec.get("objective") or "mission"),
        },
        "queries": plan_queries,
    }


def _expanded_query_specs(spec: dict[str, Any]) -> list[dict[str, Any]]:
    languages = spec.get("languages") or []
    expanded: list[dict[str, Any]] = []
    for raw_query in spec["queries"]:
        query = dict(raw_query)
        query_lang = query.get("lang")
        if query_lang:
            expanded.append(query)
            continue
        if len(languages) == 1:
            query["lang"] = languages[0]
            expanded.append(query)
            continue
        if len(languages) > 1:
            for lang in languages:
                clone = dict(query)
                clone["lang"] = lang
                expanded.append(clone)
            continue
        expanded.append(query)
    return expanded


def _search_exclude_flags(exclude: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if exclude.get("drop_retweets"):
        flags.append("retweets")
    if exclude.get("drop_replies"):
        flags.append("replies")
    if exclude.get("drop_links"):
        flags.append("links")
    return flags


def _build_curated_payload(raw_jsonl: Path, spec: dict[str, Any]) -> dict[str, Any]:
    max_per_author = (
        spec["diversity"].get("max_posts_per_author")
        or spec["exclude"].get("max_same_author_posts")
    )
    scan_limit = max(int(spec["target_posts"]) * 3, int(spec["target_posts"]))
    candidate_payload = build_candidates_payload(
        raw_jsonl,
        by="post",
        limit=scan_limit,
        max_per_author=max_per_author,
        prefer_originals=True,
        drop_noise=bool(spec["exclude"].get("drop_low_content_posts")),
        drop_title_duplicates=True,
        require_query_match=bool(spec.get("require_query_match")),
        min_seen_in=spec["diversity"].get("min_seen_in"),
    )
    filtered, keyword_drops = _drop_excluded_keywords(
        candidate_payload.get("candidates") or [],
        spec["exclude"].get("keywords") or [],
    )
    ranked = _rank_candidates(filtered)
    ranked, diversity_drops = _apply_diversity_constraints(ranked, spec)
    _annotate_coverage_topics(ranked, spec)
    ranked, topic_spread = _apply_topic_spread_constraints(
        ranked,
        spec,
        target_count=int(spec["target_posts"]),
    )
    for rank, candidate in enumerate(ranked, start=1):
        candidate["rank"] = rank
    quality_reason_counts = count_quality_reasons(ranked)
    diagnostics = _build_curation_diagnostics(
        ranked,
        topic_spread=topic_spread,
        quality_reason_counts=quality_reason_counts,
    )
    filter_drop_counts = dict(candidate_payload["summary"].get("filter_drop_counts") or {})
    for reason, count in keyword_drops.items():
        filter_drop_counts[reason] = filter_drop_counts.get(reason, 0) + count
    for reason, count in diversity_drops.items():
        filter_drop_counts[reason] = filter_drop_counts.get(reason, 0) + count
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "command": "collect spec curate",
        "target_posts": spec["target_posts"],
        "candidate_summary": candidate_payload["summary"],
        "filter_drop_counts": {key: filter_drop_counts[key] for key in sorted(filter_drop_counts)},
        "quality_reason_counts": quality_reason_counts,
        "topic_spread": topic_spread,
        "diagnostics": diagnostics,
        "ranked_count": len(ranked),
        "ranked_candidates": ranked,
    }


def _build_judge_payload(
    curated_payload: dict[str, Any],
    spec: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    judge = spec.get("judge") if isinstance(spec.get("judge"), dict) else {}
    enabled = bool(judge.get("enabled"))
    ranked = curated_payload.get("ranked_candidates") or []
    candidate_limit = int(judge.get("candidate_limit") or min(len(ranked), 20))
    selected = [candidate for candidate in ranked[:candidate_limit] if isinstance(candidate, dict)]
    fallback_policy = str(judge.get("fallback_policy") or "keep_ranked")
    base_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "enabled": enabled,
        "mode": judge.get("mode") or "llm",
        "provider": judge.get("provider"),
        "model": judge.get("model"),
        "candidate_limit": candidate_limit,
        "candidate_count": len(selected),
        "intent": judge.get("intent"),
        "criteria": judge.get("criteria") or [],
        "labels": judge.get("labels") or list(_DEFAULT_JUDGE_LABELS),
        "result_schema": judge.get("result_schema") or "judge-result",
    }
    if not enabled:
        return {
            **base_payload,
            "status": "disabled",
            "fallback": {
                "used": False,
                "policy": fallback_policy,
                "reason": None,
            },
            "records_written": 0,
        }, []

    reason = "judge_runner_not_configured"
    records = [
        _build_judge_fallback_record(
            candidate,
            spec=spec,
            judge=judge,
            reason=reason,
        )
        for candidate in selected
    ]
    return {
        **base_payload,
        "status": "not_run",
        "fallback": {
            "used": True,
            "policy": fallback_policy,
            "reason": reason,
        },
        "records_written": len(records),
    }, records


def _build_judge_fallback_record(
    candidate: dict[str, Any],
    *,
    spec: dict[str, Any],
    judge: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    fallback_policy = str(judge.get("fallback_policy") or "keep_ranked")
    decision = "fallback_keep" if fallback_policy == "keep_ranked" else "unsure"
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "judge_result",
        "generated_at": utc_timestamp(),
        "run_id": spec.get("run_id"),
        "status": "unjudged",
        "decision": decision,
        "category": None,
        "confidence": None,
        "reasons": [reason],
        "judge": {
            "mode": judge.get("mode") or "llm",
            "provider": judge.get("provider"),
            "model": judge.get("model"),
            "intent": judge.get("intent"),
            "criteria": judge.get("criteria") or [],
            "labels": judge.get("labels") or list(_DEFAULT_JUDGE_LABELS),
        },
        "candidate": _candidate_judge_evidence(candidate),
        "fallback": {
            "used": True,
            "policy": fallback_policy,
            "reason": reason,
        },
    }


def _candidate_judge_evidence(candidate: dict[str, Any]) -> dict[str, Any]:
    media = candidate.get("media_references") if isinstance(candidate.get("media_references"), list) else []
    media_types = sorted(
        {
            str(media_item.get("media_type") or media_item.get("type"))
            for media_item in media
            if isinstance(media_item, dict) and (media_item.get("media_type") or media_item.get("type"))
        }
    )
    text = str(candidate.get("text") or candidate.get("title") or "")
    return {
        "rank": candidate.get("rank"),
        "id": candidate.get("id"),
        "source_item_id": candidate.get("source_item_id"),
        "url": candidate.get("url"),
        "canonical_url": candidate.get("canonical_url"),
        "title": candidate.get("title"),
        "text_preview": text[:500],
        "author": candidate.get("author"),
        "quality_score": candidate.get("quality_score"),
        "quality_reasons": candidate.get("quality_reasons") or [],
        "coverage_topics": candidate.get("coverage_topics") or [],
        "media_count": len(media),
        "media_types": media_types,
    }


def _coverage_analysis(
    curated_payload: dict[str, Any],
    spec: dict[str, Any],
    *,
    existing_queries: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    coverage = spec.get("coverage") if isinstance(spec.get("coverage"), dict) else {}
    ranked = curated_payload.get("ranked_candidates") or []
    ranked_count = len(ranked)
    topic_reports: list[dict[str, Any]] = []
    for topic in coverage.get("topics") or []:
        matches = [
            candidate
            for candidate in ranked
            if _candidate_matches_coverage_topic(candidate, topic.get("terms") or [])
        ]
        min_posts = int(topic.get("min_posts") or coverage.get("min_posts_per_topic") or 1)
        topic_reports.append(
            {
                "topic_id": topic.get("topic_id"),
                "label": topic.get("label"),
                "terms": topic.get("terms") or [],
                "count": len(matches),
                "min_posts": min_posts,
                "gap": max(min_posts - len(matches), 0),
                "queryable": False,
                "sample_ids": [str(candidate.get("id") or "") for candidate in matches[:3]],
            }
        )
    target_ranked_posts = int(coverage.get("min_ranked_posts") or spec.get("target_posts") or 0)
    target_gap = max(target_ranked_posts - ranked_count, 0)
    topic_gap_count = sum(1 for report in topic_reports if int(report.get("gap") or 0) > 0)
    gap_diagnostics = _mark_queryable_coverage_gaps(
        topic_reports,
        spec,
        existing_queries=existing_queries or [],
    )
    queryable_topic_gap_count = int(gap_diagnostics.get("queryable_topic_gap_count") or 0)
    return {
        "enabled": bool(coverage.get("enabled")),
        "ranked_count": ranked_count,
        "target_ranked_posts": target_ranked_posts,
        "target_gap": target_gap,
        "target_gap_report_only": target_gap > 0,
        "topic_gap_count": topic_gap_count,
        "queryable_topic_gap_count": queryable_topic_gap_count,
        "unqueryable_topic_gap_count": max(topic_gap_count - queryable_topic_gap_count, 0),
        "max_queries": int(coverage.get("max_queries") or 0),
        "topic_reports": topic_reports,
        "gap_count": queryable_topic_gap_count,
        "gap_diagnostics": gap_diagnostics,
    }


def _build_coverage_gap_plan(
    spec: dict[str, Any],
    coverage_analysis: dict[str, Any],
    *,
    existing_queries: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    coverage = spec.get("coverage") if isinstance(spec.get("coverage"), dict) else {}
    max_queries = int(coverage.get("max_queries") or 0)
    existing_keys = _coverage_existing_query_keys(existing_queries)
    generated: list[dict[str, Any]] = []

    for report in coverage_analysis.get("topic_reports") or []:
        if int(report.get("gap") or 0) <= 0:
            continue
        topic = _coverage_topic_by_id(spec, report.get("topic_id"))
        if topic is None:
            continue
        generated.extend(
            _coverage_followup_queries(
                spec,
                topic,
                existing_keys=existing_keys,
                start_index=len(generated) + 1,
                max_count=max_queries - len(generated),
            )
        )
        if len(generated) >= max_queries:
            break

    gap_spec = {**spec, "queries": generated}
    plan = _build_batch_plan(gap_spec) if generated else _empty_coverage_batch_plan(spec)
    plan["coverage"] = {
        "reason": "coverage_gap_fill",
        "initial_gap_count": coverage_analysis.get("gap_count", 0),
        "target_gap": coverage_analysis.get("target_gap", 0),
        "topic_gaps": [
            report
            for report in coverage_analysis.get("topic_reports") or []
            if int(report.get("gap") or 0) > 0
        ],
    }
    return plan


def _mark_queryable_coverage_gaps(
    topic_reports: Sequence[dict[str, Any]],
    spec: dict[str, Any],
    *,
    existing_queries: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    coverage = spec.get("coverage") if isinstance(spec.get("coverage"), dict) else {}
    remaining = int(coverage.get("max_queries") or 0)
    max_queries = remaining
    existing_keys = _coverage_existing_query_keys(existing_queries)
    queryable_count = 0
    planned_query_count = 0
    blocked_reasons: dict[str, int] = {}
    for report in topic_reports:
        if int(report.get("gap") or 0) <= 0:
            continue
        if remaining <= 0:
            reason = "query_budget_exhausted"
            report["blocked_reason"] = reason
            blocked_reasons[reason] = blocked_reasons.get(reason, 0) + 1
            continue
        topic = _coverage_topic_by_id(spec, report.get("topic_id"))
        if topic is None:
            reason = "topic_not_declared"
            report["blocked_reason"] = reason
            blocked_reasons[reason] = blocked_reasons.get(reason, 0) + 1
            continue
        queries = _coverage_followup_queries(
            spec,
            topic,
            existing_keys=existing_keys,
            start_index=1,
            max_count=remaining,
        )
        if not queries:
            reason = "no_new_followup_query"
            report["blocked_reason"] = reason
            blocked_reasons[reason] = blocked_reasons.get(reason, 0) + 1
            continue
        report["queryable"] = True
        report["planned_query_count"] = len(queries)
        queryable_count += 1
        planned_query_count += len(queries)
        remaining -= len(queries)
    return {
        "max_queries": max_queries,
        "planned_query_count": planned_query_count,
        "remaining_query_budget": max(remaining, 0),
        "queryable_topic_gap_count": queryable_count,
        "blocked_reasons": {key: blocked_reasons[key] for key in sorted(blocked_reasons)},
    }


def _coverage_followup_queries(
    spec: dict[str, Any],
    topic: dict[str, Any],
    *,
    existing_keys: set[tuple[str, str]],
    start_index: int,
    max_count: int,
) -> list[dict[str, Any]]:
    if max_count <= 0:
        return []
    coverage = spec.get("coverage") if isinstance(spec.get("coverage"), dict) else {}
    generated: list[dict[str, Any]] = []
    source_queries = topic.get("queries") or [_default_coverage_query(spec, topic)]
    for source_query in source_queries:
        for lang in _coverage_languages(spec):
            if len(generated) >= max_count:
                break
            query_text = str(source_query or "").strip()
            if not query_text:
                continue
            lang_text = str(lang or "").strip()
            key = (query_text.casefold(), lang_text.casefold())
            if key in existing_keys:
                continue
            existing_keys.add(key)
            topic_slug = _slugify(topic.get("label") or "topic")
            lang_suffix = f"-{_slugify(lang_text)}" if lang_text else ""
            generated.append(
                {
                    "query_id": f"gap{start_index + len(generated):02d}-{topic_slug}{lang_suffix}",
                    "input": query_text,
                    "lang": lang_text or None,
                    "limit": topic.get("probe_limit") or coverage.get("probe_limit"),
                    "intent": f"{_mission_intent(spec)}:coverage:{topic_slug}",
                    "source_role": "coverage_gap_fill",
                }
            )
        if len(generated) >= max_count:
            break
    return generated


def _coverage_existing_query_keys(queries: Sequence[dict[str, Any]]) -> set[tuple[str, str]]:
    return {
        (
            str(query.get("input") or "").strip().casefold(),
            str(query.get("lang") or "").strip().casefold(),
        )
        for query in queries
    }


def _coverage_languages(spec: dict[str, Any]) -> list[str | None]:
    languages = spec.get("languages") or [None]
    if not languages:
        return [None]
    return list(languages)


def _empty_coverage_batch_plan(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "run_id": spec["run_id"],
        "objective": spec.get("objective"),
        "quality_profile": spec["quality_profile"],
        "failure_policy": spec["failure_policy"],
        "pacing": spec["pacing"],
        "metadata": {
            "intent": _mission_intent(spec),
            "source_role": "coverage_gap_fill",
            "query_id_prefix": f"{_slugify(spec.get('objective') or 'mission')}-gap",
        },
        "queries": [],
    }


def _build_coverage_payload(
    *,
    initial: dict[str, Any],
    final: dict[str, Any],
    coverage_plan: dict[str, Any] | None,
    coverage_batch_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    planned_queries = (coverage_plan or {}).get("queries") or []
    max_queries = int(initial.get("max_queries") or 0)
    remaining_queries = max(max_queries - len(planned_queries), 0)
    final_topic_gap_count = int(final.get("topic_gap_count") or 0)
    target_gap = int(final.get("target_gap") or 0)
    return {
        "enabled": bool(initial.get("enabled")),
        "initial": initial,
        "final": final,
        "gap_queries": planned_queries,
        "gap_query_count": len(planned_queries),
        "executed": coverage_batch_payload is not None,
        "batch_summary": (coverage_batch_payload or {}).get("summary") or {},
        "diagnostics": {
            "max_queries": max_queries,
            "used_queries": len(planned_queries),
            "remaining_queries": remaining_queries,
            "query_budget_exhausted": bool(
                initial.get("enabled") and max_queries > 0 and remaining_queries == 0 and final_topic_gap_count > 0
            ),
            "gap_fill_disabled": not bool(initial.get("enabled")),
            "target_gap_report_only": target_gap > 0,
            "final_topic_gap_count": final_topic_gap_count,
        },
    }


def _combine_batch_payloads(primary: dict[str, Any], secondary: dict[str, Any] | None) -> dict[str, Any]:
    if secondary is None:
        return primary
    combined = dict(primary)
    queries = [*(primary.get("queries") or []), *(secondary.get("queries") or [])]
    combined["queries"] = queries
    combined["summary"] = _batch_summary_from_queries(queries)
    combined["pacing"] = _combined_pacing_payload(primary.get("pacing") or {}, combined["summary"])
    combined["save_targets"] = sorted(set(primary.get("save_targets") or []) | set(secondary.get("save_targets") or []))
    combined["coverage_batch"] = secondary
    return combined


def _batch_summary_from_queries(queries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    urls: list[str] = []
    source_roles: dict[str, int] = {}
    for query in queries:
        role = query.get("source_role")
        if role:
            source_roles[str(role)] = source_roles.get(str(role), 0) + 1
        urls.extend(str(url) for url in query.get("urls") or [] if url)
    unique_urls = set(urls)
    total_wait = sum(float(query.get("applied_wait_seconds") or 0.0) for query in queries)
    return {
        "total": len(queries),
        "ok": sum(1 for query in queries if query.get("status") == "ok"),
        "errors": sum(1 for query in queries if query.get("status") == "error"),
        "skipped": sum(1 for query in queries if query.get("status") == "skipped"),
        "items": sum(int(query.get("count") or 0) for query in queries),
        "unique_urls": len(unique_urls),
        "duplicate_urls": len(urls) - len(unique_urls),
        "source_roles": source_roles,
        "waits_applied": sum(1 for query in queries if float(query.get("applied_wait_seconds") or 0.0) > 0),
        "total_wait_seconds": round(max(total_wait, 0.0), 6),
        "throttle_sensitive_errors": sum(1 for query in queries if query.get("throttle_sensitive")),
        "throttle_guard_triggered": any(query.get("reason") == "throttle_guard" for query in queries),
    }


def _combined_pacing_payload(pacing: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    return {
        **pacing,
        "waits_applied": summary.get("waits_applied", 0),
        "total_wait_seconds": summary.get("total_wait_seconds", 0),
        "throttle_sensitive_errors": summary.get("throttle_sensitive_errors", 0),
        "throttle_guard_triggered": summary.get("throttle_guard_triggered", False),
    }


def _coverage_topic_by_id(spec: dict[str, Any], topic_id: Any) -> dict[str, Any] | None:
    coverage = spec.get("coverage") if isinstance(spec.get("coverage"), dict) else {}
    for topic in coverage.get("topics") or []:
        if topic.get("topic_id") == topic_id:
            return topic
    return None


def _default_coverage_query(spec: dict[str, Any], topic: dict[str, Any]) -> str:
    base = str(spec.get("objective") or "").strip()
    if not base and spec.get("queries"):
        base = str(spec["queries"][0].get("input") or "").strip()
    label = str(topic.get("label") or "").strip()
    if base and label and label.casefold() not in base.casefold():
        return f"{base} {label}"
    return base or label


def _candidate_matches_coverage_topic(candidate: dict[str, Any], terms: Sequence[str]) -> bool:
    normalized_terms = [str(term).casefold() for term in terms if str(term).strip()]
    if not normalized_terms:
        return False
    haystack = " ".join(
        str(value or "")
        for value in (
            candidate.get("title"),
            candidate.get("text"),
            candidate.get("author"),
        )
    ).casefold()
    return any(term in haystack for term in normalized_terms)


def _annotate_coverage_topics(candidates: Sequence[dict[str, Any]], spec: dict[str, Any]) -> None:
    coverage = spec.get("coverage") if isinstance(spec.get("coverage"), dict) else {}
    topics = coverage.get("topics") or []
    if not topics:
        return
    for candidate in candidates:
        matches = [
            {
                "topic_id": topic.get("topic_id"),
                "label": topic.get("label"),
            }
            for topic in topics
            if _candidate_matches_coverage_topic(candidate, topic.get("terms") or [])
        ]
        if matches:
            candidate["coverage_topics"] = matches


def _drop_excluded_keywords(
    candidates: Sequence[dict[str, Any]],
    keywords: Sequence[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    normalized_keywords = [str(keyword).casefold() for keyword in keywords if str(keyword).strip()]
    if not normalized_keywords:
        return [dict(candidate) for candidate in candidates], {}
    kept: list[dict[str, Any]] = []
    dropped = 0
    for candidate in candidates:
        haystack = " ".join(
            str(value or "")
            for value in (candidate.get("title"), candidate.get("text"), candidate.get("author"))
        ).casefold()
        if any(keyword in haystack for keyword in normalized_keywords):
            dropped += 1
            continue
        kept.append(dict(candidate))
    return kept, {"excluded_keyword": dropped} if dropped else {}


def _rank_candidates(candidates: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_copy = dict(candidate)
        score, reasons = score_candidate(candidate_copy)
        candidate_copy["quality_score"] = score
        candidate_copy["quality_reasons"] = reasons
        ranked.append(candidate_copy)
    ranked.sort(
        key=lambda item: (
            -float(item.get("quality_score") or 0),
            -int(item.get("seen_in_count") or 0),
            str(item.get("published_at") or ""),
            str(item.get("id") or ""),
        )
    )
    return ranked


def _apply_diversity_constraints(
    candidates: Sequence[dict[str, Any]],
    spec: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    max_per_author = spec["diversity"].get("max_posts_per_author") or spec["exclude"].get("max_same_author_posts")
    max_per_thread = spec["diversity"].get("max_posts_per_thread")
    max_per_url = spec["diversity"].get("max_posts_per_url")
    author_counts: dict[str, int] = {}
    thread_counts: dict[str, int] = {}
    url_counts: dict[str, int] = {}
    kept: list[dict[str, Any]] = []
    dropped: dict[str, int] = {}

    for candidate in candidates:
        author_key = _text_key(candidate.get("author"))
        if max_per_author is not None and author_key:
            if author_counts.get(author_key, 0) >= max_per_author:
                dropped["author_diversity"] = dropped.get("author_diversity", 0) + 1
                continue
        thread_key = _candidate_identifier(candidate, "conversation_id")
        if max_per_thread is not None and thread_key:
            if thread_counts.get(thread_key, 0) >= max_per_thread:
                dropped["thread_diversity"] = dropped.get("thread_diversity", 0) + 1
                continue
        url_key = _text_key(candidate.get("canonical_url") or candidate.get("url"))
        if max_per_url is not None and url_key:
            if url_counts.get(url_key, 0) >= max_per_url:
                dropped["url_diversity"] = dropped.get("url_diversity", 0) + 1
                continue

        kept.append(candidate)
        if author_key:
            author_counts[author_key] = author_counts.get(author_key, 0) + 1
        if thread_key:
            thread_counts[thread_key] = thread_counts.get(thread_key, 0) + 1
        if url_key:
            url_counts[url_key] = url_counts.get(url_key, 0) + 1
    return kept, dropped


def _apply_topic_spread_constraints(
    candidates: Sequence[dict[str, Any]],
    spec: dict[str, Any],
    *,
    target_count: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    original_selection = list(candidates[:target_count])
    requested = bool((spec.get("diversity") or {}).get("require_topic_spread"))
    topics = _coverage_topics(spec)
    base_diagnostic = {
        "requested": requested,
        "target_posts": target_count,
        "declared_topic_count": len(topics),
        "available_topic_count": 0,
        "selected_topic_count": 0,
        "selected_topic_ids": [],
        "unavailable_topic_ids": [str(topic.get("topic_id")) for topic in topics],
        "unselected_available_topic_ids": [],
        "promoted_count": 0,
        "reordered": False,
    }

    if not requested:
        return original_selection, {**base_diagnostic, "status": "not_requested"}
    if target_count <= 0:
        return [], {**base_diagnostic, "status": "skipped_no_target"}
    if not topics:
        return original_selection, {**base_diagnostic, "status": "skipped_no_topics"}
    if not candidates:
        return original_selection, {**base_diagnostic, "status": "skipped_no_candidates"}

    topic_ids = [str(topic.get("topic_id")) for topic in topics]
    available_topic_ids = _available_topic_ids(candidates, topic_ids)
    if not available_topic_ids:
        return original_selection, {
            **base_diagnostic,
            "status": "skipped_no_matches",
        }

    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    selected_topic_ids: set[str] = set()

    for topic_id in topic_ids:
        if len(selected) >= target_count:
            break
        if topic_id in selected_topic_ids:
            continue
        candidate = _first_candidate_for_topic(candidates, topic_id, selected_keys)
        if candidate is None:
            continue
        selected.append(candidate)
        selected_keys.add(_candidate_identity_key(candidate))
        selected_topic_ids.update(_candidate_topic_ids(candidate))

    for candidate in candidates:
        if len(selected) >= target_count:
            break
        key = _candidate_identity_key(candidate)
        if key in selected_keys:
            continue
        selected.append(candidate)
        selected_keys.add(key)
        selected_topic_ids.update(_candidate_topic_ids(candidate))

    selected = selected[:target_count]
    selected_topic_ids = _available_topic_ids(selected, topic_ids)
    original_keys = [_candidate_identity_key(candidate) for candidate in original_selection]
    selected_keys_ordered = [_candidate_identity_key(candidate) for candidate in selected]
    original_key_set = set(original_keys)
    promoted_count = sum(1 for key in selected_keys_ordered if key not in original_key_set)
    reordered = selected_keys_ordered != original_keys[: len(selected_keys_ordered)]
    unselected_available_topic_ids = [
        topic_id for topic_id in topic_ids if topic_id in available_topic_ids and topic_id not in selected_topic_ids
    ]
    unavailable_topic_ids = [topic_id for topic_id in topic_ids if topic_id not in available_topic_ids]
    desired_topic_count = min(len(available_topic_ids), target_count)

    if not reordered and len(selected_topic_ids) >= desired_topic_count:
        status = "already_satisfied"
    elif len(selected_topic_ids) >= desired_topic_count:
        status = "applied"
    else:
        status = "applied_partial"

    return selected, {
        **base_diagnostic,
        "status": status,
        "available_topic_count": len(available_topic_ids),
        "selected_topic_count": len(selected_topic_ids),
        "selected_topic_ids": [topic_id for topic_id in topic_ids if topic_id in selected_topic_ids],
        "unavailable_topic_ids": unavailable_topic_ids,
        "unselected_available_topic_ids": unselected_available_topic_ids,
        "promoted_count": promoted_count,
        "reordered": reordered,
    }


def _coverage_topics(spec: dict[str, Any]) -> list[dict[str, Any]]:
    coverage = spec.get("coverage") if isinstance(spec.get("coverage"), dict) else {}
    return [topic for topic in coverage.get("topics") or [] if isinstance(topic, dict)]


def _first_candidate_for_topic(
    candidates: Sequence[dict[str, Any]],
    topic_id: str,
    selected_keys: set[str],
) -> dict[str, Any] | None:
    for candidate in candidates:
        key = _candidate_identity_key(candidate)
        if key in selected_keys:
            continue
        if topic_id in _candidate_topic_ids(candidate):
            return candidate
    return None


def _candidate_topic_ids(candidate: dict[str, Any]) -> set[str]:
    raw_topics = candidate.get("coverage_topics")
    if not isinstance(raw_topics, list):
        return set()
    return {
        str(topic.get("topic_id"))
        for topic in raw_topics
        if isinstance(topic, dict) and topic.get("topic_id") is not None
    }


def _available_topic_ids(candidates: Sequence[dict[str, Any]], topic_ids: Sequence[str]) -> set[str]:
    declared = set(topic_ids)
    available: set[str] = set()
    for candidate in candidates:
        available.update(topic_id for topic_id in _candidate_topic_ids(candidate) if topic_id in declared)
    return available


def _candidate_identity_key(candidate: dict[str, Any]) -> str:
    for key in ("id", "source_item_id", "canonical_url", "url"):
        value = candidate.get(key)
        if value is not None and str(value).strip():
            return f"{key}:{value}"
    return f"object:{id(candidate)}"


def _build_curation_diagnostics(
    candidates: Sequence[dict[str, Any]],
    *,
    topic_spread: dict[str, Any],
    quality_reason_counts: dict[str, int],
) -> dict[str, Any]:
    return {
        "quality_reason_counts": quality_reason_counts,
        "topic_spread": topic_spread,
        "concentration": {
            "authors": _concentration_summary(candidates, _candidate_author_label),
            "threads": _concentration_summary(
                candidates,
                lambda candidate: _candidate_identifier(candidate, "conversation_id"),
            ),
            "urls": _concentration_summary(
                candidates,
                lambda candidate: _text_key(candidate.get("canonical_url") or candidate.get("url")),
            ),
        },
        "time_spread": _time_spread_summary(candidates),
    }


def _concentration_summary(
    candidates: Sequence[dict[str, Any]],
    key_fn: Callable[[dict[str, Any]], str | None],
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    missing = 0
    for candidate in candidates:
        key = key_fn(candidate)
        if not key:
            missing += 1
            continue
        counts[key] = counts.get(key, 0) + 1
    top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    return {
        "unique": len(counts),
        "missing": missing,
        "top": [{"key": key, "count": count} for key, count in top],
    }


def _candidate_author_label(candidate: dict[str, Any]) -> str | None:
    return _text_key(
        _candidate_identifier(candidate, "author_handle")
        or candidate.get("author")
        or _candidate_identifier(candidate, "author_name")
    )


def _time_spread_summary(candidates: Sequence[dict[str, Any]]) -> dict[str, Any]:
    timestamps = sorted(str(candidate.get("published_at")) for candidate in candidates if candidate.get("published_at"))
    buckets: dict[str, int] = {}
    for timestamp in timestamps:
        bucket = timestamp[:10] if len(timestamp) >= 10 else timestamp
        buckets[bucket] = buckets.get(bucket, 0) + 1
    return {
        "count": len(timestamps),
        "earliest": timestamps[0] if timestamps else None,
        "latest": timestamps[-1] if timestamps else None,
        "date_counts": {key: buckets[key] for key in sorted(buckets)},
    }


def _query_yield(batch_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query in batch_payload.get("queries") or []:
        if not isinstance(query, dict):
            continue
        rows.append(
            {
                "query_id": query.get("query_id"),
                "input": query.get("input"),
                "channel": query.get("channel"),
                "operation": query.get("operation"),
                "source_role": query.get("source_role"),
                "status": query.get("status"),
                "ok": query.get("ok"),
                "count": query.get("count", 0),
                "url_count": len(query.get("urls") or []),
                "error_code": query.get("error_code"),
                "error_category": query.get("error_category"),
                "error_retryable": query.get("error_retryable"),
                "started_at": query.get("started_at"),
                "finished_at": query.get("finished_at"),
                "duration_seconds": query.get("duration_seconds"),
                "planned_wait_seconds": query.get("planned_wait_seconds"),
                "applied_wait_seconds": query.get("applied_wait_seconds"),
                "throttle_sensitive": query.get("throttle_sensitive"),
            }
        )
    return rows


def _write_canonical_jsonl(raw_jsonl: Path, output_path: Path) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = 0
    items = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in iter_ledger_records(raw_jsonl):
            records += 1
            result = record.get("result") if isinstance(record.get("result"), dict) else {}
            for item in result.get("items") or []:
                if not isinstance(item, dict):
                    continue
                items += 1
                canonical = {
                    "schema_version": SCHEMA_VERSION,
                    "record_type": "canonical_item",
                    "run_id": record.get("run_id"),
                    "channel": record.get("channel") or result.get("channel"),
                    "operation": record.get("operation") or result.get("operation"),
                    "input": record.get("input"),
                    "intent": record.get("intent"),
                    "query_id": record.get("query_id"),
                    "source_role": record.get("source_role"),
                    "item": item,
                }
                handle.write(json.dumps(canonical, ensure_ascii=False))
                handle.write("\n")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "command": "collect spec canonicalize",
        "output": str(output_path),
        "records": records,
        "items": items,
    }


def _write_ranked_jsonl(path: Path, ranked_candidates: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for candidate in ranked_candidates:
            handle.write(json.dumps(candidate, ensure_ascii=False))
            handle.write("\n")


def _write_judge_jsonl(path: Path, judge_records: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in judge_records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def _build_result_payload(
    *,
    plan_payload: dict[str, Any],
    batch_payload: dict[str, Any],
    merge_payload: dict[str, Any],
    canonical_summary: dict[str, Any],
    curated_payload: dict[str, Any],
    coverage_payload: dict[str, Any],
    judge_payload: dict[str, Any],
    batch_exit_code: int,
    outputs: dict[str, Path],
    resume: bool,
    concurrency: int,
    checkpoint_every: int,
) -> dict[str, Any]:
    batch_summary = batch_payload.get("summary") or {}
    candidate_summary = curated_payload.get("candidate_summary") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "command": "collect spec",
        "cli_version": __version__,
        "ok": batch_exit_code == 0,
        "spec": plan_payload["spec"],
        "output_dir": plan_payload["output_dir"],
        "run_id": plan_payload["run_id"],
        "objective": plan_payload.get("objective"),
        "quality_profile": plan_payload["quality_profile"],
        "target_posts": plan_payload["target_posts"],
        "resume": resume,
        "concurrency": concurrency,
        "checkpoint_every": checkpoint_every,
        "pacing": batch_payload.get("pacing") or plan_payload.get("pacing") or {},
        "summary": {
            "queries_total": batch_summary.get("total", 0),
            "queries_ok": batch_summary.get("ok", 0),
            "queries_errors": batch_summary.get("errors", 0),
            "queries_skipped": batch_summary.get("skipped", 0),
            "throttle_sensitive_errors": batch_summary.get("throttle_sensitive_errors", 0),
            "throttle_guard_triggered": batch_summary.get("throttle_guard_triggered", False),
            "total_wait_seconds": batch_summary.get("total_wait_seconds", 0),
            "items_seen": batch_summary.get("items", 0),
            "unique_urls": batch_summary.get("unique_urls", 0),
            "duplicate_urls": batch_summary.get("duplicate_urls", 0),
            "records_merged": merge_payload.get("records_written", 0),
            "canonical_items": canonical_summary.get("items", 0),
            "unique_candidates": candidate_summary.get("candidate_count", 0),
            "filtered_candidates": candidate_summary.get("filtered_candidate_count", 0),
            "ranked_candidates": curated_payload.get("ranked_count", 0),
            "filter_drop_counts": curated_payload.get("filter_drop_counts", {}),
            "quality_reason_counts": curated_payload.get("quality_reason_counts", {}),
            "topic_spread_status": (curated_payload.get("topic_spread") or {}).get("status"),
            "coverage_enabled": coverage_payload.get("enabled", False),
            "coverage_gap_queries": coverage_payload.get("gap_query_count", 0),
            "coverage_initial_gaps": (coverage_payload.get("initial") or {}).get("gap_count", 0),
            "coverage_final_gaps": (coverage_payload.get("final") or {}).get("gap_count", 0),
            "coverage_target_gap": (coverage_payload.get("final") or {}).get("target_gap", 0),
            "coverage_query_budget_exhausted": (coverage_payload.get("diagnostics") or {}).get(
                "query_budget_exhausted",
                False,
            ),
            "judge_enabled": judge_payload.get("enabled", False),
            "judge_status": judge_payload.get("status"),
            "judge_fallback_used": (judge_payload.get("fallback") or {}).get("used", False),
            "judge_records": judge_payload.get("records_written", 0),
        },
        "batch": batch_payload,
        "merge": merge_payload,
        "canonical": canonical_summary,
        "coverage": coverage_payload,
        "judge": judge_payload,
        "diagnostics": {
            "query_yield": _query_yield(batch_payload),
            "pacing": batch_payload.get("pacing") or plan_payload.get("pacing") or {},
            "curation": curated_payload.get("diagnostics", {}),
        },
        "curation": {
            key: value
            for key, value in curated_payload.items()
            if key != "ranked_candidates"
        },
        "outputs": {
            "raw_dir": str(outputs["raw_dir"]),
            "raw_jsonl": str(outputs["raw_jsonl"]),
            "canonical_jsonl": str(outputs["canonical_jsonl"]),
            "ranked_jsonl": str(outputs["ranked_jsonl"]),
            "judge_jsonl": str(outputs["judge_jsonl"]),
            "summary_md": str(outputs["summary_md"]),
            "manifest": str(outputs["manifest"]),
            "batch_plan": str(outputs["batch_plan"]),
            "coverage_batch_plan": str(outputs["coverage_batch_plan"]),
            "normalized_spec": str(outputs["normalized_spec"]),
            "state": str(outputs["state"]),
        },
    }


def _render_summary_markdown(
    *,
    plan_payload: dict[str, Any],
    batch_payload: dict[str, Any],
    merge_payload: dict[str, Any],
    canonical_summary: dict[str, Any],
    curated_payload: dict[str, Any],
    coverage_payload: dict[str, Any],
    judge_payload: dict[str, Any],
    batch_exit_code: int,
) -> str:
    batch_summary = batch_payload.get("summary") or {}
    lines = [
        "# X Reach Mission Summary",
        "",
        f"- Spec: `{plan_payload['spec']}`",
        f"- Run ID: `{plan_payload['run_id']}`",
        f"- Objective: {plan_payload.get('objective') or '(none)'}",
        f"- Quality profile: `{plan_payload['quality_profile']}`",
        f"- Batch exit code: `{batch_exit_code}`",
        "",
        "## Counts",
        "",
        f"- Queries: {batch_summary.get('total', 0)} total / {batch_summary.get('ok', 0)} ok / {batch_summary.get('errors', 0)} errors / {batch_summary.get('skipped', 0)} skipped",
        f"- Items seen: {batch_summary.get('items', 0)}",
        f"- Records merged: {merge_payload.get('records_written', 0)}",
        f"- Canonical items: {canonical_summary.get('items', 0)}",
        f"- Ranked candidates: {curated_payload.get('ranked_count', 0)}",
        "",
        "## Filter Drops",
        "",
    ]
    filter_drop_counts = curated_payload.get("filter_drop_counts") or {}
    if filter_drop_counts:
        lines.extend(f"- {reason}: {count}" for reason, count in filter_drop_counts.items())
    else:
        lines.append("- none")
    lines.extend(["", "## Quality Reasons", ""])
    quality_reason_counts = curated_payload.get("quality_reason_counts") or {}
    if quality_reason_counts:
        lines.extend(f"- {reason}: {count}" for reason, count in quality_reason_counts.items())
    else:
        lines.append("- none")
    lines.extend(["", "## Topic Spread", ""])
    topic_spread = curated_payload.get("topic_spread") or {}
    lines.extend(
        [
            f"- Requested: {'yes' if topic_spread.get('requested') else 'no'}",
            f"- Status: {topic_spread.get('status') or 'unknown'}",
            f"- Declared topics: {topic_spread.get('declared_topic_count', 0)}",
            f"- Available topics: {topic_spread.get('available_topic_count', 0)}",
            f"- Selected topics: {topic_spread.get('selected_topic_count', 0)}",
            f"- Promoted candidates: {topic_spread.get('promoted_count', 0)}",
        ]
    )
    lines.extend(["", "## Coverage", ""])
    if coverage_payload.get("enabled"):
        initial = coverage_payload.get("initial") or {}
        final = coverage_payload.get("final") or {}
        coverage_diagnostics = coverage_payload.get("diagnostics") or {}
        lines.extend(
            [
                f"- Initial gaps: {initial.get('gap_count', 0)}",
                f"- Final gaps: {final.get('gap_count', 0)}",
                f"- Gap queries: {coverage_payload.get('gap_query_count', 0)}",
                f"- Target gap: {final.get('target_gap', 0)}",
                f"- Query budget exhausted: {'yes' if coverage_diagnostics.get('query_budget_exhausted') else 'no'}",
            ]
        )
        for report in final.get("topic_reports") or []:
            lines.append(
                f"- Topic `{report.get('label')}`: {report.get('count', 0)}/{report.get('min_posts', 0)}"
            )
    else:
        lines.append("- disabled")
    pacing = batch_payload.get("pacing") or {}
    if _mission_pacing_should_render(pacing):
        lines.extend(["", "## Pacing", ""])
        lines.extend(
            [
                f"- Query delay seconds: {pacing.get('query_delay_seconds', 0)}",
                f"- Query jitter seconds: {pacing.get('query_jitter_seconds', 0)}",
                f"- Throttle cooldown seconds: {pacing.get('throttle_cooldown_seconds', 0)}",
                f"- Throttle error limit: {pacing.get('throttle_error_limit', 0)}",
                f"- Waits applied: {pacing.get('waits_applied', 0)}",
                f"- Total wait seconds: {pacing.get('total_wait_seconds', 0)}",
                f"- Throttle-sensitive errors: {pacing.get('throttle_sensitive_errors', 0)}",
                f"- Throttle guard triggered: {'yes' if pacing.get('throttle_guard_triggered') else 'no'}",
            ]
        )
    lines.extend(["", "## Judge", ""])
    lines.extend(
        [
            f"- Status: {judge_payload.get('status') or 'disabled'}",
            f"- Candidate limit: {judge_payload.get('candidate_limit', 0)}",
            f"- Records written: {judge_payload.get('records_written', 0)}",
            f"- Fallback used: {'yes' if (judge_payload.get('fallback') or {}).get('used') else 'no'}",
        ]
    )
    fallback_reason = (judge_payload.get("fallback") or {}).get("reason")
    if fallback_reason:
        lines.append(f"- Fallback reason: {fallback_reason}")
    lines.extend(["", "## Top Candidates", ""])
    for candidate in (curated_payload.get("ranked_candidates") or [])[:10]:
        title = candidate.get("title") or candidate.get("id") or "(untitled)"
        url = candidate.get("url") or ""
        score = candidate.get("quality_score")
        lines.append(f"- #{candidate.get('rank')} score={score} {title} {url}".rstrip())
    if not curated_payload.get("ranked_candidates"):
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _mission_pacing_should_render(pacing: dict[str, Any]) -> bool:
    return any(
        bool(pacing.get(key))
        for key in (
            "query_delay_seconds",
            "query_jitter_seconds",
            "waits_applied",
            "throttle_sensitive_errors",
            "throttle_guard_triggered",
        )
    )


def _mission_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "raw_dir": output_dir / "raw",
        "raw_jsonl": output_dir / "raw.jsonl",
        "canonical_jsonl": output_dir / "canonical.jsonl",
        "ranked_jsonl": output_dir / "ranked.jsonl",
        "judge_jsonl": output_dir / _JUDGE_OUTPUT,
        "summary_md": output_dir / "summary.md",
        "manifest": output_dir / _MANIFEST_OUTPUT,
        "batch_plan": output_dir / "mission.batch.json",
        "coverage_batch_plan": output_dir / "mission.coverage.batch.json",
        "normalized_spec": output_dir / "mission.normalized.json",
        "state": output_dir / "mission-state.json",
    }


def _resolve_output_dir(
    output_dir: str | Path | None,
    *,
    source_path: Path,
    run_id: str,
) -> Path:
    if output_dir is not None:
        return Path(output_dir)
    stem = _slugify(source_path.stem) or "mission"
    run_token = _slugify(run_id) or "run"
    return Path(_MISSION_DIR) / f"{stem}-{run_token}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")


def _normalize_quality_profile(value: Any) -> str:
    text = str(value or "balanced").strip().casefold()
    normalized = _QUALITY_ALIASES.get(text)
    if normalized is None:
        choices = ", ".join(sorted(set(_QUALITY_ALIASES) | set(QUALITY_PROFILES)))
        raise MissionSpecError(f"Unsupported quality_profile: {value}. Supported values: {choices}")
    return normalized


def _normalize_outputs(value: Any) -> list[str]:
    if value is None:
        return ["raw.jsonl", "canonical.jsonl", "ranked.jsonl", "summary.md"]
    outputs = _normalize_text_list(value)
    unknown = sorted(set(outputs) - (_JSONL_OUTPUTS | {_SUMMARY_OUTPUT, _MANIFEST_OUTPUT}))
    if unknown:
        raise MissionSpecError(f"Unsupported output name(s): {', '.join(unknown)}")
    return outputs


def _normalize_languages(value: Any) -> list[str]:
    languages = _normalize_text_list(value)
    for language in languages:
        if not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{2,8})?", language):
            raise MissionSpecError(f"Unsupported language code: {language}")
    return languages


def _normalize_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, list):
        raise MissionSpecError("expected a list of strings")
    values: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if text and text not in seen:
            values.append(text)
            seen.add(text)
    return values


def _normalize_choice(value: Any, choices: set[str], name: str) -> str:
    text = str(value or "").strip()
    if text not in choices:
        raise MissionSpecError(f"{name} must be one of: {', '.join(sorted(choices))}")
    return text


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _positive_int(value: Any, *, default: int, name: str) -> int:
    if value is None:
        return default
    parsed = _optional_positive_int(value, name)
    return parsed if parsed is not None else default


def _optional_positive_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise MissionSpecError(f"{name} must be an integer") from exc
    if parsed < 1:
        raise MissionSpecError(f"{name} must be greater than or equal to 1")
    return parsed


def _optional_nonnegative_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise MissionSpecError(f"{name} must be an integer") from exc
    if parsed < 0:
        raise MissionSpecError(f"{name} must be greater than or equal to 0")
    return parsed


def _bool_or_default(value: Any, default: bool) -> bool:
    if value is None:
        return default
    return bool(value)


def _mission_intent(spec: dict[str, Any]) -> str:
    slug = _slugify(spec.get("objective") or "mission")
    return f"mission:{slug or 'x-research'}"


def _slugify(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    return text.strip("._-")[:80]


def _text_key(value: Any) -> str | None:
    text = str(value or "").strip().casefold()
    return text or None


def _candidate_identifier(candidate: dict[str, Any], name: str) -> str | None:
    raw_identifiers = candidate.get("identifiers")
    identifiers = raw_identifiers if isinstance(raw_identifiers, dict) else {}
    raw_extras = candidate.get("extras")
    extras = raw_extras if isinstance(raw_extras, dict) else {}
    value = identifiers.get(name) if identifiers.get(name) is not None else extras.get(name)
    return _text_key(value)
