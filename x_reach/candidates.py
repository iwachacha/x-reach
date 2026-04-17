# -*- coding: utf-8 -*-
"""Candidate planning helpers for evidence ledgers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlsplit, urlunsplit

from x_reach.evidence_scoring import quality_reason_counts, score_candidate
from x_reach.high_signal import (
    analyze_item_quality,
    extract_query_tokens,
    original_preference_rank,
)
from x_reach.ledger import iter_jsonl_lines
from x_reach.results import canonicalize_url as result_canonicalize_url
from x_reach.schemas import SCHEMA_VERSION, utc_timestamp


class CandidatePlanError(Exception):
    """Raised when candidate planning input cannot be read or parsed."""


SORT_BY_FIRST_SEEN = "first_seen"
SORT_BY_QUALITY_SCORE = "quality_score"
ALLOWED_SORT_BY = {SORT_BY_FIRST_SEEN, SORT_BY_QUALITY_SCORE}

ALLOWED_CANDIDATE_FIELDS = {
    "id",
    "kind",
    "title",
    "url",
    "text",
    "author",
    "published_at",
    "source",
    "canonical_url",
    "source_item_id",
    "engagement",
    "media_references",
    "identifiers",
    "intent",
    "query_id",
    "source_role",
    "seen_in_count",
    "quality_score",
    "quality_reasons",
    "extras",
}


def canonicalize_url(url: str | None) -> str | None:
    """Return a minimal canonical URL for dedupe."""

    if not url:
        return None
    text = str(url).strip()
    if not text:
        return None
    parts = urlsplit(text)
    path = parts.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            parts.query,
            "",
        )
    )


def build_candidates_payload(
    path: str | Path,
    *,
    by: str = "url",
    limit: int = 20,
    summary_only: bool = False,
    fields: Sequence[str] | str | None = None,
    max_per_author: int | None = None,
    prefer_originals: bool = False,
    drop_noise: bool = False,
    drop_title_duplicates: bool = False,
    require_query_match: bool = False,
    min_seen_in: int | None = None,
    sort_by: str = SORT_BY_FIRST_SEEN,
) -> dict[str, Any]:
    """Read evidence JSONL and return a deduped candidate payload."""

    if by not in {"url", "normalized_url", "id", "source_item_id", "domain", "author", "post"}:
        raise CandidatePlanError(f"Unsupported dedupe mode: {by}")
    if sort_by not in ALLOWED_SORT_BY:
        choices = ", ".join(sorted(ALLOWED_SORT_BY))
        raise CandidatePlanError(f"sort_by must be one of: {choices}")
    if limit < 1:
        raise CandidatePlanError("limit must be greater than or equal to 1")
    if max_per_author is not None and max_per_author < 1:
        raise CandidatePlanError("max_per_author must be greater than or equal to 1")
    if min_seen_in is not None and min_seen_in < 1:
        raise CandidatePlanError("min_seen_in must be greater than or equal to 1")
    selected_fields = _normalize_fields(fields)

    evidence_path = Path(path)
    records, skipped_records = _read_collection_records(evidence_path)
    candidates: list[dict[str, Any]] = []
    by_key: dict[str, dict[str, Any]] = {}
    items_seen = 0
    skipped_items = 0
    filter_drop_counts: dict[str, int] = {}
    channel_keys: dict[str, set[str]] = {}
    source_role_keys: dict[str, set[str]] = {}
    intent_keys: dict[str, set[str]] = {}

    for record in records:
        result = record["result"]
        meta = result.get("meta") or {}
        record_query_tokens = _query_tokens_for_record(record, result)
        for item in result.get("items") or []:
            if not isinstance(item, dict):
                skipped_items += 1
                continue
            items_seen += 1
            key = _dedupe_key(item, result, by=by)
            if key is None:
                skipped_items += 1
                continue
            intent = _metadata_value(record, result, item, "intent")
            query_id = _metadata_value(record, result, item, "query_id")
            source_role = _metadata_value(record, result, item, "source_role")
            source = item.get("source") or result.get("channel")
            _track_summary_key(channel_keys, source, key)
            _track_summary_key(source_role_keys, source_role, key)
            _track_summary_key(intent_keys, intent, key)

            sighting = {
                "run_id": record.get("run_id"),
                "channel": result.get("channel"),
                "operation": result.get("operation"),
                "input": record.get("input") if record.get("input") is not None else meta.get("input"),
                "item_id": item.get("id"),
                "url": item.get("url"),
            }
            _add_if_present(sighting, "intent", intent)
            _add_if_present(sighting, "query_id", query_id)
            _add_if_present(sighting, "source_role", source_role)

            if key in by_key:
                by_key[key]["extras"]["seen_in"].append(sighting)
                by_key[key]["seen_in_count"] = len(by_key[key]["extras"]["seen_in"])
                _fill_missing_candidate_metadata(by_key[key], intent, query_id, source_role)
                _append_alternate_url(by_key[key], item.get("url"))
                _merge_query_tokens(by_key[key], record_query_tokens)
                if prefer_originals:
                    incoming = _candidate_from_item(item, query_tokens=record_query_tokens)
                    incoming["intent"] = intent
                    incoming["query_id"] = query_id
                    incoming["source_role"] = source_role
                    if _should_promote_candidate(by_key[key], incoming):
                        _promote_candidate(by_key[key], incoming)
                continue

            candidate = _candidate_from_item(item, query_tokens=record_query_tokens)
            candidate["intent"] = intent
            candidate["query_id"] = query_id
            candidate["source_role"] = source_role
            candidate["extras"]["seen_in"] = [sighting]
            candidate["extras"]["candidate_key"] = key
            candidate["extras"].setdefault("alternate_urls", [])
            candidate["seen_in_count"] = 1
            by_key[key] = candidate
            candidates.append(candidate)

    filtered_candidates, filter_drop_counts = _post_filter_candidates(
        candidates,
        max_per_author=max_per_author,
        drop_noise=drop_noise,
        drop_title_duplicates=drop_title_duplicates,
        require_query_match=require_query_match,
        min_seen_in=min_seen_in,
    )
    scored_candidates = _score_candidates(filtered_candidates)
    ordered_candidates = _sort_candidates(scored_candidates, sort_by=sort_by)
    returned = ordered_candidates[:limit]
    returned_quality_reason_counts = quality_reason_counts(returned)
    max_seen_in = max((int(candidate.get("seen_in_count") or 0) for candidate in candidates), default=0)
    output_candidates = [] if summary_only else [_filter_candidate(candidate, selected_fields) for candidate in returned]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "command": "plan candidates",
        "input": str(evidence_path),
        "by": by,
        "sort_by": sort_by,
        "limit": limit,
        "summary_only": summary_only,
        "fields": list(selected_fields) if selected_fields is not None else None,
        "max_per_author": max_per_author,
        "prefer_originals": prefer_originals,
        "drop_noise": drop_noise,
        "drop_title_duplicates": drop_title_duplicates,
        "require_query_match": require_query_match,
        "min_seen_in": min_seen_in,
        "summary": {
            "records": len(records) + skipped_records,
            "collection_results": len(records),
            "skipped_records": skipped_records,
            "items_seen": items_seen,
            "skipped_items": skipped_items,
            "candidate_count": len(candidates),
            "multi_seen_candidates": sum(1 for candidate in candidates if int(candidate.get("seen_in_count") or 0) > 1),
            "max_seen_in": max_seen_in,
            "returned": len(returned),
            "filtered_candidate_count": len(filtered_candidates),
            "filter_drop_counts": filter_drop_counts,
            "quality_reason_counts": returned_quality_reason_counts,
            "channel_counts": _count_summary_keys(channel_keys),
            "source_role_counts": _count_summary_keys(source_role_keys),
            "intent_counts": _count_summary_keys(intent_keys),
        },
        "candidates": output_candidates,
    }


def render_candidates_text(payload: dict[str, Any]) -> str:
    """Render candidate planner output for humans."""

    summary = payload["summary"]
    lines = [
        "X Reach Candidate Plan",
        "========================================",
        f"Input: {payload['input']}",
        f"Mode: {payload['by']}",
        f"Sort: {payload.get('sort_by', SORT_BY_FIRST_SEEN)}",
        f"Candidates: {summary['returned']}/{summary['candidate_count']}",
    ]
    if summary.get("skipped_records"):
        lines.append(f"Skipped records: {summary['skipped_records']}")
    if summary.get("skipped_items"):
        lines.append(f"Skipped items: {summary['skipped_items']}")
    if summary.get("channel_counts"):
        lines.append(f"Channels: {_render_count_summary(summary['channel_counts'])}")
    if summary.get("source_role_counts"):
        lines.append(f"Source roles: {_render_count_summary(summary['source_role_counts'])}")
    if summary.get("quality_reason_counts"):
        lines.append(f"Quality reasons: {_render_count_summary(summary['quality_reason_counts'])}")
    for candidate in payload["candidates"]:
        title = candidate.get("title") or candidate.get("id") or "(untitled)"
        url = candidate.get("url") or ""
        score = candidate.get("quality_score")
        score_label = f" score={score}" if isinstance(score, (int, float)) else ""
        lines.append(f"  - {title}{score_label} {url}".rstrip())
    return "\n".join(lines)


def _read_collection_records(path: Path) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    skipped_records = 0
    try:
        lines = list(iter_jsonl_lines(path))
    except OSError as exc:
        raise CandidatePlanError(f"Could not read evidence input: {exc}") from exc

    for line_number, line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            record = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CandidatePlanError(f"Invalid JSONL at line {line_number}: {exc.msg}") from exc
        collection_record = _collection_record_from_json(record)
        if collection_record is None:
            skipped_records += 1
            continue
        records.append(collection_record)
    return records, skipped_records


def _collection_record_from_json(record: Any) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None

    if record.get("record_type") == "collection_result":
        result = record.get("result")
        if _is_collection_result(result):
            return {
                "run_id": record.get("run_id"),
                "input": record.get("input"),
                "intent": record.get("intent"),
                "query_id": record.get("query_id"),
                "source_role": record.get("source_role"),
                "result": result,
            }
        return None

    if _is_collection_result(record):
        meta = record.get("meta") or {}
        return {
            "run_id": record.get("run_id"),
            "input": meta.get("input"),
            "intent": meta.get("intent"),
            "query_id": meta.get("query_id"),
            "source_role": meta.get("source_role"),
            "result": record,
        }
    return None


def _is_collection_result(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    required = {"ok", "channel", "operation", "items", "meta", "error"}
    return required.issubset(value.keys()) and isinstance(value.get("items"), list)


def _candidate_from_item(
    item: dict[str, Any],
    *,
    query_tokens: Sequence[str] | None = None,
) -> dict[str, Any]:
    raw_extras = item.get("extras")
    extras: dict[str, Any] = raw_extras if isinstance(raw_extras, dict) else {}
    merged_extras = {**extras}
    if query_tokens:
        merged_extras["query_tokens"] = list(dict.fromkeys(str(token) for token in query_tokens))
    return {
        "id": item.get("id"),
        "kind": item.get("kind"),
        "title": item.get("title"),
        "url": item.get("url"),
        "canonical_url": item.get("canonical_url"),
        "source_item_id": item.get("source_item_id"),
        "engagement": item.get("engagement") if isinstance(item.get("engagement"), dict) else {},
        "media_references": item.get("media_references") if isinstance(item.get("media_references"), list) else [],
        "identifiers": item.get("identifiers") if isinstance(item.get("identifiers"), dict) else {},
        "text": item.get("text"),
        "author": item.get("author"),
        "published_at": item.get("published_at"),
        "source": item.get("source"),
        "intent": extras.get("intent"),
        "query_id": extras.get("query_id"),
        "source_role": extras.get("source_role"),
        "seen_in_count": 0,
        "extras": merged_extras,
        "_preference_rank": original_preference_rank(extras.get("timeline_item_kind")),
    }


def _metadata_value(
    record: dict[str, Any],
    result: dict[str, Any],
    item: dict[str, Any],
    name: str,
) -> Any:
    raw_meta = result.get("meta")
    raw_extras = item.get("extras")
    meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    extras: dict[str, Any] = raw_extras if isinstance(raw_extras, dict) else {}
    for source in (record, meta, extras):
        value = source.get(name)
        if value is not None:
            return value
    return None


def _add_if_present(target: dict[str, Any], name: str, value: Any) -> None:
    if value is not None:
        target[name] = value


def _track_summary_key(summary: dict[str, set[str]], name: Any, key: str) -> None:
    if name is None:
        return
    label = str(name).strip()
    if not label:
        return
    summary.setdefault(label, set()).add(key)


def _count_summary_keys(summary: dict[str, set[str]]) -> dict[str, int]:
    ordered = sorted(summary.items(), key=lambda item: (-len(item[1]), item[0]))
    return {name: len(keys) for name, keys in ordered}


def _render_count_summary(summary: dict[str, int]) -> str:
    return ", ".join(f"{name}={count}" for name, count in summary.items())


def _fill_missing_candidate_metadata(
    candidate: dict[str, Any],
    intent: Any,
    query_id: Any,
    source_role: Any,
) -> None:
    if candidate.get("intent") is None and intent is not None:
        candidate["intent"] = intent
    if candidate.get("query_id") is None and query_id is not None:
        candidate["query_id"] = query_id
    if candidate.get("source_role") is None and source_role is not None:
        candidate["source_role"] = source_role


def _append_alternate_url(candidate: dict[str, Any], url: Any) -> None:
    if not url:
        return
    text = str(url)
    if not text or text == candidate.get("url"):
        return
    alternates = candidate.setdefault("extras", {}).setdefault("alternate_urls", [])
    if text not in alternates:
        alternates.append(text)


def _query_tokens_for_record(record: dict[str, Any], result: dict[str, Any]) -> list[str]:
    raw_meta = result.get("meta")
    meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    raw_tokens = meta.get("query_tokens")
    if isinstance(raw_tokens, list):
        return list(dict.fromkeys(str(token).casefold() for token in raw_tokens if str(token).strip()))

    if result.get("operation") not in {"search", "hashtag"}:
        return []
    input_value = record.get("input") if record.get("input") is not None else meta.get("input")
    return extract_query_tokens(str(input_value or ""))


def _merge_query_tokens(candidate: dict[str, Any], query_tokens: Sequence[str]) -> None:
    if not query_tokens:
        return
    extras = candidate.setdefault("extras", {})
    existing = extras.get("query_tokens")
    existing_tokens = [str(token).casefold() for token in existing] if isinstance(existing, list) else []
    merged = list(dict.fromkeys([*existing_tokens, *(str(token).casefold() for token in query_tokens)]))
    extras["query_tokens"] = merged


def _should_promote_candidate(existing: dict[str, Any], incoming: dict[str, Any]) -> bool:
    return int(incoming.get("_preference_rank", 99)) < int(existing.get("_preference_rank", 99))


def _promote_candidate(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    seen_in = list(existing.get("extras", {}).get("seen_in", []))
    alternate_urls = list(existing.get("extras", {}).get("alternate_urls", []))
    candidate_key = existing.get("extras", {}).get("candidate_key")
    query_tokens = list(existing.get("extras", {}).get("query_tokens", []))
    existing_intent = existing.get("intent")
    existing_query_id = existing.get("query_id")
    existing_source_role = existing.get("source_role")

    replacement = _copy_candidate(incoming)
    replacement_extras = replacement.setdefault("extras", {})
    replacement_extras["seen_in"] = seen_in
    replacement_extras["alternate_urls"] = alternate_urls
    replacement_extras["candidate_key"] = candidate_key
    replacement["seen_in_count"] = len(seen_in)
    if query_tokens:
        replacement_extras["query_tokens"] = query_tokens
    existing.clear()
    existing.update(replacement)
    _fill_missing_candidate_metadata(existing, existing_intent, existing_query_id, existing_source_role)


def _copy_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    copy: dict[str, Any] = {}
    for key, value in candidate.items():
        if isinstance(value, dict):
            copy[key] = dict(value)
        elif isinstance(value, list):
            copy[key] = list(value)
        else:
            copy[key] = value
    return copy


def _score_candidates(candidates: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_copy = _copy_candidate(candidate)
        score, reasons = score_candidate(candidate_copy)
        candidate_copy["quality_score"] = score
        candidate_copy["quality_reasons"] = reasons
        scored.append(candidate_copy)
    return scored


def _sort_candidates(candidates: Sequence[dict[str, Any]], *, sort_by: str) -> list[dict[str, Any]]:
    if sort_by == SORT_BY_FIRST_SEEN:
        return list(candidates)
    if sort_by == SORT_BY_QUALITY_SCORE:
        return sorted(
            candidates,
            key=lambda candidate: float(candidate.get("quality_score") or 0),
            reverse=True,
        )
    choices = ", ".join(sorted(ALLOWED_SORT_BY))
    raise CandidatePlanError(f"sort_by must be one of: {choices}")


def _normalize_fields(fields: Sequence[str] | str | None) -> tuple[str, ...] | None:
    if fields is None:
        return None
    if isinstance(fields, str):
        values = tuple(item.strip() for item in fields.split(",") if item.strip())
    else:
        values = tuple(str(item).strip() for item in fields if str(item).strip())
    if not values:
        raise CandidatePlanError("fields must include at least one field name")
    unknown = sorted(set(values) - ALLOWED_CANDIDATE_FIELDS)
    if unknown:
        supported = ", ".join(sorted(ALLOWED_CANDIDATE_FIELDS))
        raise CandidatePlanError(
            f"Unsupported candidate field(s): {', '.join(unknown)}. Supported fields: {supported}"
        )
    return values


def _filter_candidate(
    candidate: dict[str, Any],
    fields: tuple[str, ...] | None,
) -> dict[str, Any]:
    public_candidate = _public_candidate(candidate)
    if fields is None:
        return public_candidate
    return {field: public_candidate.get(field) for field in fields}


def _public_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in candidate.items()
        if not key.startswith("_")
    }


def _post_filter_candidates(
    candidates: list[dict[str, Any]],
    *,
    max_per_author: int | None,
    drop_noise: bool,
    drop_title_duplicates: bool,
    require_query_match: bool,
    min_seen_in: int | None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    returned: list[dict[str, Any]] = []
    dropped: dict[str, int] = {}
    author_counts: dict[str, int] = {}
    seen_title_keys: set[str] = set()

    for candidate in candidates:
        if drop_noise or require_query_match:
            analysis = analyze_item_quality(
                text=_candidate_text(candidate),
                searchable_parts=_candidate_searchable_parts(candidate),
                urls=_candidate_urls(candidate),
                query_tokens=_candidate_query_tokens(candidate),
                item_kind=_candidate_item_kind(candidate),
                engagement=None,
                quality_profile=None,
                require_query_match=require_query_match,
                drop_retweets=drop_noise,
                drop_replies=drop_noise,
                drop_low_content=drop_noise,
            )
            reasons = []
            for reason in analysis["drop_reasons"]:
                if reason == "engagement_gate":
                    continue
                if reason == "query_miss" and not require_query_match:
                    continue
                reasons.append(str(reason))
            if reasons:
                for reason in list(dict.fromkeys(reasons)):
                    dropped[reason] = dropped.get(reason, 0) + 1
                continue

        if min_seen_in is not None and int(candidate.get("seen_in_count") or 0) < min_seen_in:
            dropped["seen_in"] = dropped.get("seen_in", 0) + 1
            continue

        if drop_title_duplicates:
            title_key = _candidate_title_key(candidate)
            if title_key is not None:
                if title_key in seen_title_keys:
                    dropped["title_duplicate"] = dropped.get("title_duplicate", 0) + 1
                    continue
                seen_title_keys.add(title_key)

        author_key = _candidate_author_key(candidate)
        if max_per_author is not None and author_key is not None:
            current = author_counts.get(author_key, 0)
            if current >= max_per_author:
                dropped["author_cap"] = dropped.get("author_cap", 0) + 1
                continue
            author_counts[author_key] = current + 1

        returned.append(candidate)
    return returned, {key: dropped[key] for key in sorted(dropped)}


def _dedupe_key(
    item: dict[str, Any],
    result: dict[str, Any],
    *,
    by: str,
) -> str | None:
    source = item.get("source") or result.get("channel") or "unknown"
    item_id = item.get("id")
    url = _normalized_url(item)
    source_item_id = item.get("source_item_id") or item_id
    domain = _identifier_value(item, "domain")
    author_handle = _identifier_value(item, "author_handle") or item.get("author")
    post_id = _identifier_value(item, "post_id") or source_item_id
    if by == "id":
        if item_id:
            return f"id:{source}:{item_id}"
        if url:
            return f"url:{url}"
    if by == "source_item_id":
        if source_item_id:
            return f"source_item_id:{source}:{source_item_id}"
        if url:
            return f"url:{url}"
    if by == "domain":
        if domain:
            return f"domain:{domain}"
        return None
    if by == "author":
        if author_handle:
            return f"author:{source}:{author_handle}"
        return None
    if by == "post":
        if post_id:
            return f"post:{source}:{post_id}"
        return None
    if by == "normalized_url":
        if url:
            return f"normalized_url:{url}"
        return None
    if by == "url":
        if url:
            return f"url:{url}"
        if item_id:
            return f"id:{source}:{item_id}"
    return None


def _candidate_text(candidate: dict[str, Any]) -> str | None:
    text = candidate.get("text")
    if text is not None:
        return str(text)
    title = candidate.get("title")
    return str(title) if title is not None else None


def _candidate_searchable_parts(candidate: dict[str, Any]) -> list[str | None]:
    raw_extras = candidate.get("extras")
    extras: dict[str, Any] = raw_extras if isinstance(raw_extras, dict) else {}
    return [
        candidate.get("title"),
        candidate.get("text"),
        candidate.get("author"),
        extras.get("author_name"),
        extras.get("quoted_author_handle"),
        extras.get("quoted_author_name"),
        candidate.get("url"),
        " ".join(_candidate_urls(candidate)) or None,
    ]


def _candidate_urls(candidate: dict[str, Any]) -> list[str]:
    raw_extras = candidate.get("extras")
    extras: dict[str, Any] = raw_extras if isinstance(raw_extras, dict) else {}
    raw_urls = extras.get("urls")
    if not isinstance(raw_urls, list):
        return []
    return [str(url) for url in raw_urls if str(url).strip()]


def _candidate_query_tokens(candidate: dict[str, Any]) -> list[str]:
    raw_extras = candidate.get("extras")
    extras: dict[str, Any] = raw_extras if isinstance(raw_extras, dict) else {}
    raw_tokens = extras.get("query_tokens")
    if not isinstance(raw_tokens, list):
        return []
    return [str(token).casefold() for token in raw_tokens if str(token).strip()]


def _candidate_item_kind(candidate: dict[str, Any]) -> str | None:
    raw_extras = candidate.get("extras")
    extras: dict[str, Any] = raw_extras if isinstance(raw_extras, dict) else {}
    value = extras.get("timeline_item_kind")
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _candidate_author_key(candidate: dict[str, Any]) -> str | None:
    author = candidate.get("author")
    if author is None:
        return None
    text = str(author).strip().casefold()
    return text or None


def _candidate_title_key(candidate: dict[str, Any]) -> str | None:
    title = candidate.get("title")
    if title is None:
        return None
    normalized = " ".join(str(title).casefold().split())
    if not normalized:
        return None
    if len(normalized) < 24 and len(normalized.split()) < 4:
        return None
    return normalized


def _normalized_url(item: dict[str, Any]) -> str | None:
    value = item.get("canonical_url") or result_canonicalize_url(item.get("url")) or canonicalize_url(item.get("url"))
    return str(value) if value else None


def _identifier_value(item: dict[str, Any], key: str) -> str | None:
    raw_identifiers = item.get("identifiers")
    identifiers = raw_identifiers if isinstance(raw_identifiers, dict) else {}
    raw_extras = item.get("extras")
    extras = raw_extras if isinstance(raw_extras, dict) else {}
    value = identifiers.get(key)
    if value is None:
        value = extras.get(key)
    if value is None and key == "domain":
        url = _normalized_url(item)
        if url:
            value = urlsplit(url).netloc.lower()
    if value is None:
        return None
    text = str(value).strip()
    return text or None

