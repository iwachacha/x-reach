# -*- coding: utf-8 -*-
"""Mission-spec runtime for X-focused collection jobs."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Callable, Sequence

from x_reach._version import __version__
from x_reach.batch import BatchPlanError, run_batch_plan, validate_batch_plan
from x_reach.candidates import CandidatePlanError, build_candidates_payload
from x_reach.client import XReachClient
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
_DEFAULT_TARGET_POSTS = 100
_MISSION_DIR = ".x-reach/missions"
_JSONL_OUTPUTS = {"raw.jsonl", "canonical.jsonl", "ranked.jsonl"}
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
    client_factory: Callable[[], XReachClient] | None = None,
) -> dict[str, Any]:
    """Execute a mission spec and write raw, canonical, and curated artifacts."""

    plan_payload = build_mission_plan_payload(spec_path, output_dir=output_dir, run_id=run_id)
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
            client_factory=client_factory,
        )
        merge_payload = merge_ledger_inputs(raw_dir, paths["raw_jsonl"])
        canonical_summary = _write_canonical_jsonl(paths["raw_jsonl"], paths["canonical_jsonl"])
        curated_payload = _build_curated_payload(paths["raw_jsonl"], normalized_spec)
        _write_ranked_jsonl(paths["ranked_jsonl"], curated_payload["ranked_candidates"])
        summary_text = _render_summary_markdown(
            plan_payload=plan_payload,
            batch_payload=batch_payload,
            merge_payload=merge_payload,
            canonical_summary=canonical_summary,
            curated_payload=curated_payload,
            batch_exit_code=batch_exit_code,
        )
        paths["summary_md"].write_text(summary_text, encoding="utf-8", newline="\n")
        result_payload = _build_result_payload(
            plan_payload=plan_payload,
            batch_payload=batch_payload,
            merge_payload=merge_payload,
            canonical_summary=canonical_summary,
            curated_payload=curated_payload,
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
            f"Raw ledger: {outputs.get('raw_jsonl', '')}",
            f"Ranked posts: {outputs.get('ranked_jsonl', '')}",
            f"Summary: {outputs.get('summary_md', '')}",
        ]
    )


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
    ranked = ranked[: int(spec["target_posts"])]
    for rank, candidate in enumerate(ranked, start=1):
        candidate["rank"] = rank
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
        "ranked_count": len(ranked),
        "ranked_candidates": ranked,
    }


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
        score, reasons = _candidate_score(candidate_copy)
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


def _candidate_score(candidate: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    seen_in_count = int(candidate.get("seen_in_count") or 0)
    if seen_in_count > 1:
        score += min(seen_in_count, 5) * 6.0
        reasons.append("multi_seen")

    raw_extras = candidate.get("extras")
    extras = raw_extras if isinstance(raw_extras, dict) else {}
    kind = str(extras.get("timeline_item_kind") or "").lower()
    if kind == "original":
        score += 8.0
        reasons.append("original")
    elif kind == "quote":
        score += 3.0
        reasons.append("quote")
    elif kind == "reply":
        score -= 4.0
        reasons.append("reply")
    elif kind == "retweet":
        score -= 8.0
        reasons.append("retweet")

    engagement = candidate.get("engagement") if isinstance(candidate.get("engagement"), dict) else {}
    engagement_score = 0.0
    for field, weight in (
        ("likes", 1.0),
        ("retweets", 2.0),
        ("reposts", 2.0),
        ("quotes", 1.5),
        ("replies", 1.0),
        ("views", 0.2),
    ):
        value = _number_or_zero(engagement.get(field))
        if value > 0:
            engagement_score += math.log10(value + 1) * weight
    if engagement_score:
        score += engagement_score
        reasons.append("engagement")

    text = str(candidate.get("text") or candidate.get("title") or "")
    if len(text) >= 80:
        score += 4.0
        reasons.append("substantial_text")
    elif len(text) >= 35:
        score += 2.0
        reasons.append("some_text")
    if candidate.get("media_references"):
        score += 1.0
        reasons.append("media")
    if candidate.get("url"):
        score += 1.0
        reasons.append("has_url")
    return round(score, 3), reasons


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


def _build_result_payload(
    *,
    plan_payload: dict[str, Any],
    batch_payload: dict[str, Any],
    merge_payload: dict[str, Any],
    canonical_summary: dict[str, Any],
    curated_payload: dict[str, Any],
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
        "summary": {
            "queries_total": batch_summary.get("total", 0),
            "queries_ok": batch_summary.get("ok", 0),
            "queries_errors": batch_summary.get("errors", 0),
            "queries_skipped": batch_summary.get("skipped", 0),
            "items_seen": batch_summary.get("items", 0),
            "unique_urls": batch_summary.get("unique_urls", 0),
            "duplicate_urls": batch_summary.get("duplicate_urls", 0),
            "records_merged": merge_payload.get("records_written", 0),
            "canonical_items": canonical_summary.get("items", 0),
            "unique_candidates": candidate_summary.get("candidate_count", 0),
            "filtered_candidates": candidate_summary.get("filtered_candidate_count", 0),
            "ranked_candidates": curated_payload.get("ranked_count", 0),
            "filter_drop_counts": curated_payload.get("filter_drop_counts", {}),
        },
        "batch": batch_payload,
        "merge": merge_payload,
        "canonical": canonical_summary,
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
            "summary_md": str(outputs["summary_md"]),
            "manifest": str(outputs["manifest"]),
            "batch_plan": str(outputs["batch_plan"]),
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


def _mission_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "raw_dir": output_dir / "raw",
        "raw_jsonl": output_dir / "raw.jsonl",
        "canonical_jsonl": output_dir / "canonical.jsonl",
        "ranked_jsonl": output_dir / "ranked.jsonl",
        "summary_md": output_dir / "summary.md",
        "manifest": output_dir / _MANIFEST_OUTPUT,
        "batch_plan": output_dir / "mission.batch.json",
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


def _number_or_zero(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return 0.0


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
