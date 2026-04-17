# -*- coding: utf-8 -*-
"""Twitter/X collection adapter."""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from typing import Any, Sequence
from urllib.parse import urlparse

from x_reach.high_signal import (
    analyze_item_quality,
    extract_query_tokens,
    merge_default_excludes,
    normalize_quality_profile,
    resolve_default_originals_only,
    resolve_default_search_type,
    resolve_fetch_limit,
)
from x_reach.media_references import build_media_reference, dedupe_media_references
from x_reach.results import (
    CollectionResult,
    NormalizedItem,
    build_item,
    derive_title_from_text,
    normalize_engagement,
    parse_timestamp,
)
from x_reach.topic_fit import (
    evaluate_topic_fit,
    normalize_topic_fit_rules,
    topic_fit_quality_reasons,
    topic_fit_result_summary,
    topic_fit_rules_enabled,
)

from .base import BaseAdapter


def _normalize_screen_name(value: str) -> str:
    text = value.strip()
    if text.startswith("@"):
        return text[1:]
    if "twitter.com" in text or "x.com" in text:
        parsed = urlparse(text)
        segments = [segment for segment in parsed.path.split("/") if segment]
        return segments[0] if segments else text
    return text


def _normalize_tweet_id(value: str) -> str:
    text = value.strip()
    if "twitter.com" not in text and "x.com" not in text:
        return text
    parsed = urlparse(text)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if "status" in segments:
        idx = segments.index("status")
        if idx + 1 < len(segments):
            return segments[idx + 1]
    return text


def _tweet_url(tweet: dict) -> str | None:
    tweet_id = tweet.get("id")
    screen_name = (tweet.get("author") or {}).get("screenName")
    if tweet_id:
        return f"https://x.com/{screen_name or 'i'}/status/{tweet_id}"
    return None


def _normalize_hashtag(value: str) -> str | None:
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    text = text.strip()
    if not text or any(character.isspace() for character in text):
        return None
    return f"#{text}"


def _twitter_media_references(media: object) -> list[dict[str, object]]:
    if not isinstance(media, list):
        return []

    references: list[dict[str, object]] = []
    for entry in media:
        if not isinstance(entry, dict):
            continue
        raw_type = str(entry.get("type") or "")
        normalized_type = "video" if raw_type in {"video", "animated_gif", "gif"} else "image"
        reference = build_media_reference(
            type=normalized_type,
            media_type=raw_type or None,
            url=entry.get("url") or entry.get("mediaUrl") or entry.get("media_url"),
            relation="post_media",
            thumb_url=entry.get("thumbnail") or entry.get("thumbUrl") or entry.get("previewImageUrl"),
            alt=entry.get("alt"),
            width=entry.get("width"),
            height=entry.get("height"),
            duration_seconds=entry.get("durationSeconds"),
            source_field="media[]",
        )
        if reference is not None:
            references.append(reference)
    return dedupe_media_references(references)


def _tweet_item(
    tweet: dict,
    idx: int,
    source: str,
    *,
    timeline_owner_handle: str | None = None,
) -> NormalizedItem:
    author = tweet.get("author") or {}
    media = tweet.get("media") or []
    metrics = tweet.get("metrics") or {}
    media_references = _twitter_media_references(media)
    quoted_tweet = tweet.get("quotedTweet")
    quoted_post_id = quoted_tweet.get("id") if isinstance(quoted_tweet, dict) else None
    quoted_author = quoted_tweet.get("author") if isinstance(quoted_tweet, dict) else {}
    retweeted_by = tweet.get("retweetedBy")
    timeline_item_kind = _tweet_timeline_item_kind(tweet)
    return build_item(
        item_id=str(tweet.get("id") or f"tweet-{idx}"),
        kind="post",
        title=derive_title_from_text(tweet.get("text"), fallback=f"Tweet {tweet.get('id')}"),
        url=_tweet_url(tweet),
        text=tweet.get("text"),
        author=author.get("screenName"),
        published_at=parse_timestamp(tweet.get("createdAtISO") or tweet.get("createdAt")),
        source=source,
        extras=_compact_mapping(
            {
                "author_name": author.get("name"),
                "author_verified": author.get("verified"),
                "lang": tweet.get("lang"),
                "urls": tweet.get("urls") or [],
                "is_retweet": tweet.get("isRetweet"),
                "retweeted_by": retweeted_by,
                "is_quote": quoted_post_id is not None,
                "quoted_post_id": quoted_post_id,
                "quoted_author_handle": quoted_author.get("screenName") if isinstance(quoted_author, dict) else None,
                "quoted_author_name": quoted_author.get("name") if isinstance(quoted_author, dict) else None,
                "in_reply_to_post_id": tweet.get("inReplyToStatusId"),
                "timeline_owner_handle": timeline_owner_handle,
                "timeline_item_kind": timeline_item_kind,
            }
        ),
        engagement=metrics,
        media_references=media_references,
        identifiers=_compact_mapping(
            {
                "author_handle": author.get("screenName"),
                "post_id": tweet.get("id"),
                "conversation_id": tweet.get("conversationId"),
                "timeline_owner_handle": timeline_owner_handle,
            }
        ),
    )


def _compact_mapping(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in values.items()
        if value not in (None, "", [], {}, False)
    }


def _tweet_timeline_item_kind(tweet: dict[str, Any]) -> str:
    quoted_tweet = tweet.get("quotedTweet")
    quoted_post_id = quoted_tweet.get("id") if isinstance(quoted_tweet, dict) else None
    if tweet.get("isRetweet"):
        return "retweet"
    if tweet.get("inReplyToStatusId"):
        return "reply"
    if quoted_post_id is not None:
        return "quote"
    return "original"


def _tweet_item_shape(*, engagement_complete: bool, media_complete: bool) -> dict[str, dict[str, str]]:
    return {
        "item_shape": {
            "engagement": "complete" if engagement_complete else "partial",
            "media": "complete" if media_complete else "partial",
        }
    }


def _string_list(value: Sequence[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    return [str(item).strip() for item in value if str(item).strip()]


def _append_repeatable_option(args: list[str], flag: str, values: Sequence[str] | str | None) -> None:
    for value in _string_list(values):
        args.extend([flag, value])


def _tweet_metric(tweet: dict[str, Any], field: str) -> int | float | None:
    metrics = tweet.get("metrics")
    if not isinstance(metrics, dict):
        return None
    return normalize_engagement(metrics).get(field)


def _apply_min_views(data: list[dict[str, Any]], min_views: int | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if min_views is None:
        return data, {}
    filtered = [
        tweet
        for tweet in data
        if (_tweet_metric(tweet, "views") or 0) >= min_views
    ]
    return filtered, {
        "client_side_filters": {
            "min_views": min_views,
            "items_before_min_views": len(data),
            "items_after_min_views": len(filtered),
        }
    }


def _apply_metric_filters(
    data: list[dict[str, Any]],
    *,
    min_likes: int | None = None,
    min_retweets: int | None = None,
    min_views: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, int], list[str]]:
    thresholds = [
        ("min_likes", "likes", min_likes),
        ("min_retweets", "retweets", min_retweets),
        ("min_views", "views", min_views),
    ]
    active = [(reason, field, int(value)) for reason, field, value in thresholds if value is not None]
    if not active:
        return data, {}, {}, []

    kept: list[dict[str, Any]] = []
    dropped = Counter()
    dropped_samples: list[dict[str, Any]] = []
    for tweet in data:
        reasons = [
            reason
            for reason, field, threshold in active
            if (_tweet_metric(tweet, field) or 0) < threshold
        ]
        if not reasons:
            kept.append(tweet)
            continue
        for reason in reasons:
            dropped[reason] += 1
        _append_quality_drop_sample(dropped_samples, tweet, reasons)

    filter_drop_counts = {key: dropped[key] for key in sorted(dropped)}
    metric_filter: dict[str, Any] = {
        "items_before_metric_filters": len(data),
        "items_after_metric_filters": len(kept),
        "filter_drop_counts": filter_drop_counts,
    }
    if dropped_samples:
        metric_filter["dropped_samples"] = dropped_samples
    diagnostics = {
        "client_side_filters": {
            **{reason: threshold for reason, _field, threshold in active},
            "items_before_metric_filters": len(data),
            "items_after_metric_filters": len(kept),
        },
        "metric_filters": metric_filter,
    }
    return kept, diagnostics, filter_drop_counts, list(filter_drop_counts)


def _apply_originals_only(
    data: list[dict[str, Any]],
    originals_only: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not originals_only:
        return data, {}
    filtered = [tweet for tweet in data if not tweet.get("isRetweet")]
    return filtered, {
        "client_side_filters": {
            "originals_only": True,
            "items_before_originals_only": len(data),
            "items_after_originals_only": len(filtered),
        }
    }


def _tweet_url_values(tweet: dict[str, Any]) -> list[str]:
    raw_urls = tweet.get("urls")
    if not isinstance(raw_urls, list):
        return []

    values: list[str] = []
    for entry in raw_urls:
        if isinstance(entry, dict):
            for candidate in (
                entry.get("expandedUrl"),
                entry.get("url"),
                entry.get("expanded_url"),
                entry.get("displayUrl"),
            ):
                if candidate:
                    values.append(str(candidate))
                    break
            continue
        text = str(entry).strip()
        if text:
            values.append(text)
    return values


def _tweet_searchable_parts(tweet: dict[str, Any]) -> list[str | None]:
    author = tweet.get("author") or {}
    quoted_tweet = tweet.get("quotedTweet")
    quoted_author = quoted_tweet.get("author") if isinstance(quoted_tweet, dict) else {}
    return [
        tweet.get("text"),
        author.get("screenName"),
        author.get("name"),
        quoted_author.get("screenName") if isinstance(quoted_author, dict) else None,
        quoted_author.get("name") if isinstance(quoted_author, dict) else None,
        " ".join(_tweet_url_values(tweet)) or None,
    ]


def _apply_topic_fit_filter(
    data: list[dict[str, Any]],
    *,
    topic_fit: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, int], list[str], dict[int, dict[str, Any]]]:
    if not topic_fit_rules_enabled(topic_fit):
        return data, {}, {}, [], {}

    kept: list[dict[str, Any]] = []
    kept_results: dict[int, dict[str, Any]] = {}
    evaluated_results: list[dict[str, Any]] = []
    dropped = Counter()
    dropped_samples: list[dict[str, Any]] = []
    for tweet in data:
        result = evaluate_topic_fit(_tweet_searchable_parts(tweet), topic_fit)
        evaluated_results.append(result)
        if result.get("matched"):
            kept.append(tweet)
            kept_results[id(tweet)] = result
            continue
        reasons = [str(reason) for reason in result.get("drop_reasons") or []]
        for reason in reasons:
            dropped[reason] += 1
        _append_quality_drop_sample(dropped_samples, tweet, reasons)

    filter_drop_counts = {key: dropped[key] for key in sorted(dropped)}
    summary = topic_fit_result_summary(topic_fit, evaluated_results)
    if dropped_samples:
        summary["dropped_samples"] = dropped_samples
    diagnostics = {"topic_fit": summary}
    return kept, diagnostics, filter_drop_counts, list(filter_drop_counts), kept_results


def _apply_quality_profile_filter(
    data: list[dict[str, Any]],
    *,
    requested_limit: int,
    quality_profile: str | None,
    query_tokens: Sequence[str] | None = None,
    require_query_match: bool = False,
    drop_retweets: bool = False,
    drop_replies: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], list[str]]:
    if quality_profile not in {"precision", "balanced"}:
        return data[:requested_limit], {}, {}, []

    kept: list[dict[str, Any]] = []
    fallback: list[dict[str, Any]] = []
    dropped = Counter()
    dropped_samples: list[dict[str, Any]] = []

    for tweet in data:
        analysis = analyze_item_quality(
            text=tweet.get("text"),
            searchable_parts=_tweet_searchable_parts(tweet),
            urls=_tweet_url_values(tweet),
            query_tokens=query_tokens,
            item_kind=_tweet_timeline_item_kind(tweet),
            engagement=tweet.get("metrics") if isinstance(tweet.get("metrics"), dict) else tweet,
            quality_profile=quality_profile,
            require_query_match=require_query_match,
            drop_retweets=drop_retweets,
            drop_replies=drop_replies,
        )
        reasons = list(dict.fromkeys(str(reason) for reason in analysis["drop_reasons"]))
        if not reasons:
            kept.append(tweet)
            continue
        if reasons == ["engagement_gate"]:
            fallback.append(tweet)
            continue
        for reason in reasons:
            dropped[reason] += 1
        _append_quality_drop_sample(dropped_samples, tweet, reasons)

    used_fallback = max(requested_limit - len(kept), 0)
    if used_fallback:
        kept.extend(fallback[:used_fallback])
    for _tweet in fallback[used_fallback:]:
        dropped["engagement_gate"] += 1
        _append_quality_drop_sample(dropped_samples, _tweet, ["engagement_gate"])

    filter_drop_counts = {key: dropped[key] for key in sorted(dropped)}
    quality_diagnostics = {
        "quality_profile": quality_profile,
        "items_before_quality_filter": len(data),
        "items_after_quality_filter": len(kept[:requested_limit]),
        "fallback_candidates": len(fallback),
        "fallback_used": min(used_fallback, len(fallback)),
    }
    if dropped_samples:
        quality_diagnostics["dropped_samples"] = dropped_samples
    diagnostics = {"quality_filter": quality_diagnostics}
    return kept[:requested_limit], diagnostics, filter_drop_counts, list(filter_drop_counts)


def _append_quality_drop_sample(
    samples: list[dict[str, Any]],
    tweet: dict[str, Any],
    reasons: Sequence[str],
    *,
    limit: int = 5,
) -> None:
    if len(samples) >= limit:
        return
    author = tweet.get("author") if isinstance(tweet.get("author"), dict) else {}
    text = " ".join(str(tweet.get("text") or "").split())
    samples.append(
        {
            "id": str(tweet.get("id") or ""),
            "author": author.get("screenName"),
            "text_preview": text[:160],
            "reasons": list(reasons),
        }
    )


def _merge_diagnostics(*diagnostics: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for diagnostic in diagnostics:
        for key, value in diagnostic.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
    return merged


def _merge_filter_drop_counts(*counts: dict[str, int]) -> dict[str, int]:
    merged = Counter()
    for count_map in counts:
        merged.update(count_map)
    return {key: merged[key] for key in sorted(merged)}


def _topic_fit_reason_counts(results: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for result in results:
        for reason in topic_fit_quality_reasons(result):
            counts[reason] += 1
    return {key: counts[key] for key in sorted(counts)}


def _build_search_args(
    query: str,
    limit: int,
    *,
    since: str | None = None,
    until: str | None = None,
    from_user: str | None = None,
    to_user: str | None = None,
    lang: str | None = None,
    search_type: str | None = None,
    has: Sequence[str] | str | None = None,
    exclude: Sequence[str] | str | None = None,
    min_likes: int | None = None,
    min_retweets: int | None = None,
) -> list[str]:
    """Translate common X-style search tokens into twitter-cli flags."""

    args = ["search"]
    remaining: list[str] = []
    option_values = {
        "from": "--from",
        "to": "--to",
        "lang": "--lang",
        "since": "--since",
        "until": "--until",
        "type": "--type",
        "min_likes": "--min-likes",
        "min-likes": "--min-likes",
        "min_retweets": "--min-retweets",
        "min-retweets": "--min-retweets",
    }
    repeatable_values = {
        "has": "--has",
        "exclude": "--exclude",
    }
    explicit_repeatable = {
        "has": bool(_string_list(has)),
        "exclude": bool(_string_list(exclude)),
    }

    for token in query.split():
        if ":" not in token:
            remaining.append(token)
            continue
        key, value = token.split(":", 1)
        lowered_key = key.lower()
        if not value:
            remaining.append(token)
            continue
        if lowered_key == "since" and since is not None:
            continue
        if lowered_key == "until" and until is not None:
            continue
        if lowered_key == "from" and from_user is not None:
            continue
        if lowered_key == "to" and to_user is not None:
            continue
        if lowered_key == "lang" and lang is not None:
            continue
        if lowered_key == "type" and search_type is not None:
            continue
        if lowered_key in {"min_likes", "min-likes"} and min_likes is not None:
            continue
        if lowered_key in {"min_retweets", "min-retweets"} and min_retweets is not None:
            continue
        if lowered_key in option_values:
            args.extend([option_values[lowered_key], value])
            continue
        if lowered_key in repeatable_values:
            if explicit_repeatable.get(lowered_key):
                continue
            args.extend([repeatable_values[lowered_key], value])
            continue
        remaining.append(token)

    if search_type is not None:
        args.extend(["--type", search_type])
    if from_user is not None:
        args.extend(["--from", from_user])
    if to_user is not None:
        args.extend(["--to", to_user])
    if lang is not None:
        args.extend(["--lang", lang])
    _append_repeatable_option(args, "--has", has)
    _append_repeatable_option(args, "--exclude", exclude)
    if min_likes is not None:
        args.extend(["--min-likes", str(min_likes)])
    if min_retweets is not None:
        args.extend(["--min-retweets", str(min_retweets)])
    text_query = " ".join(remaining).strip()
    if text_query:
        args.append(text_query)
    if since is not None:
        args.extend(["--since", since])
    if until is not None:
        args.extend(["--until", until])
    args.extend(["-n", str(limit), "--json"])
    return args


def _query_has_time_window(query: str) -> bool:
    return any(token.lower().startswith(("since:", "until:")) for token in query.split())


def _query_has_search_type(query: str) -> bool:
    return any(token.lower().startswith("type:") for token in query.split())


def _time_window_diagnostics(query: str, since: str | None, until: str | None) -> dict[str, object]:
    bounded = since is not None or until is not None or _query_has_time_window(query)
    return {
        "unbounded_time_window": not bounded,
        "time_window_fields": ["since", "until"],
    }


def _parse_error_output(raw_output: str) -> tuple[str | None, str | None, dict | None]:
    """Extract a structured error from twitter-cli stderr/stdout when available."""

    try:
        payload = json.loads(raw_output or "{}")
    except json.JSONDecodeError:
        return None, None, None

    if not isinstance(payload, dict):
        return None, None, None

    error = payload.get("error")
    if not isinstance(error, dict):
        return None, None, payload

    code = error.get("code")
    message = error.get("message")
    return (str(code) if code else None), (str(message) if message else None), payload


def _detect_http_status(raw_output: str) -> int | None:
    match = re.search(r"(?:http[\s_-]*|status[\s_-]*|error[\s_-]*)(\d{3})", raw_output, re.IGNORECASE)
    if not match:
        match = re.search(r"\b(409|429)\b", raw_output)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _plain_error_code(raw_output: str) -> str | None:
    text = raw_output.casefold()
    status = _detect_http_status(raw_output)
    if status == 429 or "too many requests" in text or "rate limit" in text:
        return "rate_limited"
    if status == 409 or "conflict" in text:
        return "http_409"
    if "not_authenticated" in text:
        return "not_authenticated"
    return None


def _plain_error_message(operation: str, code: str | None) -> str | None:
    if code == "rate_limited":
        return f"Twitter {operation} was rate limited or returned too many requests"
    if code == "http_409":
        return f"Twitter {operation} returned a conflict response"
    return None


class TwitterAdapter(BaseAdapter):
    """Read Twitter/X data through twitter-cli."""

    channel = "twitter"
    operations = ("search", "hashtag", "user", "user_posts", "tweet")

    def search(
        self,
        query: str,
        limit: int = 10,
        since: str | None = None,
        until: str | None = None,
        from_user: str | None = None,
        to_user: str | None = None,
        lang: str | None = None,
        search_type: str | None = None,
        has: Sequence[str] | str | None = None,
        exclude: Sequence[str] | str | None = None,
        min_likes: int | None = None,
        min_retweets: int | None = None,
        min_views: int | None = None,
        quality_profile: str | None = None,
    ) -> CollectionResult:
        started_at = time.perf_counter()
        effective_quality_profile = normalize_quality_profile("search", quality_profile)
        requested_limit = max(int(limit), 1)
        fetch_limit = resolve_fetch_limit(requested_limit, effective_quality_profile)
        if search_type is None and _query_has_search_type(query):
            effective_search_type, defaulted_search_type = None, False
        else:
            effective_search_type, defaulted_search_type = resolve_default_search_type(
                search_type,
                effective_quality_profile,
            )
        effective_exclude, defaulted_exclude = merge_default_excludes(
            _string_list(exclude) or None,
            effective_quality_profile,
        )
        query_tokens = extract_query_tokens(query)
        applied_defaults: dict[str, Any] = {}
        if quality_profile is None and effective_quality_profile is not None:
            applied_defaults["quality_profile"] = effective_quality_profile
        if defaulted_search_type and effective_search_type is not None:
            applied_defaults["search_type"] = effective_search_type
        if defaulted_exclude and effective_exclude is not None:
            applied_defaults["exclude"] = effective_exclude
        result = self._run_twitter(
            _build_search_args(
                query,
                fetch_limit,
                since=since,
                until=until,
                from_user=from_user,
                to_user=to_user,
                lang=lang,
                search_type=effective_search_type,
                has=has,
                exclude=effective_exclude,
                min_likes=min_likes,
                min_retweets=min_retweets,
            ),
            operation="search",
            value=query,
            limit=requested_limit,
            started_at=started_at,
            extra_meta={
                "since": since,
                "until": until,
                "from_user": from_user,
                "to_user": to_user,
                "lang": lang,
                "search_type": effective_search_type,
                "has": _string_list(has) or None,
                "exclude": effective_exclude,
                "min_likes": min_likes,
                "min_retweets": min_retweets,
                "min_views": min_views,
                "quality_profile": effective_quality_profile,
                "fetch_limit": fetch_limit,
                "query_tokens": query_tokens or None,
                **({"applied_defaults": applied_defaults} if applied_defaults else {}),
            },
        )
        if isinstance(result, dict):
            return result

        raw, _raw_output = result
        raw_data = raw.get("data", [])
        data = raw_data if isinstance(raw_data, list) else []
        data, client_filter_diagnostics = _apply_min_views(data, min_views)
        data, quality_diagnostics, filter_drop_counts, filter_drop_reasons = _apply_quality_profile_filter(
            data,
            requested_limit=requested_limit,
            quality_profile=effective_quality_profile,
            query_tokens=query_tokens,
            require_query_match=True,
            drop_retweets=True,
            drop_replies=True,
        )
        items = [
            _tweet_item(
                tweet,
                idx,
                self.channel,
            )
            for idx, tweet in enumerate(data)
        ]
        return self.ok_result(
            "search",
            items=items,
            raw=raw,
            meta=self.make_meta(
                value=query,
                limit=requested_limit,
                started_at=started_at,
                since=since,
                until=until,
                from_user=from_user,
                to_user=to_user,
                lang=lang,
                search_type=effective_search_type,
                has=_string_list(has) or None,
                exclude=effective_exclude,
                min_likes=min_likes,
                min_retweets=min_retweets,
                min_views=min_views,
                quality_profile=effective_quality_profile,
                fetch_limit=fetch_limit,
                query_tokens=query_tokens or None,
                **({"applied_defaults": applied_defaults} if applied_defaults else {}),
                **({"filter_drop_counts": filter_drop_counts} if filter_drop_counts else {}),
                **({"filter_drop_reasons": filter_drop_reasons} if filter_drop_reasons else {}),
                diagnostics={
                    **_time_window_diagnostics(query, since, until),
                    **client_filter_diagnostics,
                    **quality_diagnostics,
                },
                **_tweet_item_shape(engagement_complete=False, media_complete=False),
            ),
        )

    def user(self, screen_name: str, limit: int | None = None) -> CollectionResult:
        started_at = time.perf_counter()
        normalized = _normalize_screen_name(screen_name)
        result = self._run_twitter(
            ["user", normalized, "--json"],
            operation="user",
            value=normalized,
            limit=limit,
            started_at=started_at,
        )
        if isinstance(result, dict):
            return result

        raw, _raw_output = result
        data = raw.get("data") or {}
        if not isinstance(data, dict):
            return self.error_result(
                "user",
                code="invalid_response",
                message="Twitter user returned an unexpected payload",
                raw=raw,
                meta=self.make_meta(value=normalized, limit=limit, started_at=started_at),
            )

        item = build_item(
            item_id=str(data.get("id") or data.get("screenName") or normalized),
            kind="profile",
            title=data.get("name") or data.get("screenName") or normalized,
            url=f"https://x.com/{data.get('screenName') or normalized}",
            text=data.get("bio"),
            author=data.get("screenName"),
            published_at=parse_timestamp(data.get("createdAtISO") or data.get("createdAt")),
            source=self.channel,
            extras=_compact_mapping(
                {
                    "followers": data.get("followers"),
                    "following": data.get("following"),
                    "tweets": data.get("tweets"),
                    "likes": data.get("likes"),
                    "profile_verified": data.get("verified"),
                    "location": data.get("location"),
                    "profile_image_url": data.get("profileImageUrl"),
                    "website_url": data.get("url"),
                }
            ),
            media_references=dedupe_media_references(
                [
                    reference
                    for reference in [
                        build_media_reference(
                            type="image",
                            url=data.get("profileImageUrl"),
                            relation="avatar",
                            source_field="profileImageUrl",
                        )
                    ]
                    if reference is not None
                ]
            ),
            identifiers=_compact_mapping(
                {
                    "author_handle": data.get("screenName"),
                    "profile_handle": data.get("screenName"),
                }
            ),
        )
        return self.ok_result(
            "user",
            items=[item],
            raw=raw,
            meta=self.make_meta(value=normalized, limit=limit, started_at=started_at),
        )

    def hashtag(
        self,
        hashtag: str,
        limit: int = 10,
        since: str | None = None,
        until: str | None = None,
        from_user: str | None = None,
        to_user: str | None = None,
        lang: str | None = None,
        search_type: str | None = None,
        has: Sequence[str] | str | None = None,
        exclude: Sequence[str] | str | None = None,
        min_likes: int | None = None,
        min_retweets: int | None = None,
        min_views: int | None = None,
        quality_profile: str | None = None,
    ) -> CollectionResult:
        started_at = time.perf_counter()
        normalized = _normalize_hashtag(hashtag)
        if normalized is None:
            return self.error_result(
                "hashtag",
                code="invalid_input",
                message="Twitter hashtag must be one non-empty hashtag without whitespace",
                meta=self.make_meta(value=hashtag, limit=limit, started_at=started_at),
            )
        payload = self.search(
            normalized,
            limit=limit,
            since=since,
            until=until,
            from_user=from_user,
            to_user=to_user,
            lang=lang,
            search_type=search_type,
            has=has,
            exclude=exclude,
            min_likes=min_likes,
            min_retweets=min_retweets,
            min_views=min_views,
            quality_profile=quality_profile,
        )
        meta = dict(payload.get("meta") or {})
        meta["input"] = hashtag
        meta["resolved_query"] = normalized
        meta["hashtag"] = normalized[1:]
        return {
            **payload,
            "operation": "hashtag",
            "meta": meta,
        }

    def user_posts(
        self,
        screen_name: str,
        limit: int = 10,
        originals_only: bool | None = None,
        min_likes: int | None = None,
        min_retweets: int | None = None,
        min_views: int | None = None,
        topic_fit: dict[str, Any] | None = None,
        quality_profile: str | None = None,
    ) -> CollectionResult:
        started_at = time.perf_counter()
        normalized = _normalize_screen_name(screen_name)
        try:
            normalized_topic_fit = normalize_topic_fit_rules(topic_fit)
        except ValueError as exc:
            return self.error_result(
                "user_posts",
                code="invalid_input",
                message=str(exc),
                meta=self.make_meta(
                    value=normalized,
                    limit=limit,
                    started_at=started_at,
                    topic_fit=topic_fit,
                ),
            )
        effective_quality_profile = normalize_quality_profile("user_posts", quality_profile)
        requested_limit = max(int(limit), 1)
        fetch_limit = resolve_fetch_limit(requested_limit, effective_quality_profile)
        effective_originals_only, defaulted_originals_only = resolve_default_originals_only(
            originals_only,
            effective_quality_profile,
        )
        applied_defaults: dict[str, Any] = {}
        if quality_profile is None and effective_quality_profile is not None:
            applied_defaults["quality_profile"] = effective_quality_profile
        if defaulted_originals_only:
            applied_defaults["originals_only"] = True
        result = self._run_twitter(
            ["user-posts", normalized, "-n", str(fetch_limit), "--json"],
            operation="user_posts",
            value=normalized,
            limit=requested_limit,
            started_at=started_at,
            extra_meta={
                "min_likes": min_likes,
                "min_retweets": min_retweets,
                "min_views": min_views,
                "topic_fit": normalized_topic_fit if topic_fit is not None else None,
                "quality_profile": effective_quality_profile,
                "fetch_limit": fetch_limit,
                **({"applied_defaults": applied_defaults} if applied_defaults else {}),
            },
        )
        if isinstance(result, dict):
            return result

        raw, _raw_output = result
        data = raw.get("data", [])
        if not isinstance(data, list):
            return self.error_result(
                "user_posts",
                code="invalid_response",
                message="Twitter user posts returned an unexpected payload",
                raw=raw,
                meta=self.make_meta(value=normalized, limit=requested_limit, started_at=started_at),
            )
        data, client_filter_diagnostics = _apply_originals_only(data, effective_originals_only)
        data, metric_diagnostics, metric_drop_counts, _metric_drop_reasons = _apply_metric_filters(
            data,
            min_likes=min_likes,
            min_retweets=min_retweets,
            min_views=min_views,
        )
        (
            data,
            topic_fit_diagnostics,
            topic_fit_drop_counts,
            _topic_fit_drop_reasons,
            topic_fit_results,
        ) = _apply_topic_fit_filter(data, topic_fit=normalized_topic_fit)
        data, quality_diagnostics, filter_drop_counts, _filter_drop_reasons = _apply_quality_profile_filter(
            data,
            requested_limit=requested_limit,
            quality_profile=effective_quality_profile,
            drop_retweets=effective_originals_only,
        )
        merged_filter_drop_counts = _merge_filter_drop_counts(
            metric_drop_counts,
            topic_fit_drop_counts,
            filter_drop_counts,
        )
        items: list[NormalizedItem] = []
        returned_topic_fit_results: list[dict[str, Any]] = []
        for idx, tweet in enumerate(data):
            item = _tweet_item(
                tweet,
                idx,
                self.channel,
                timeline_owner_handle=normalized,
            )
            topic_fit_result = topic_fit_results.get(id(tweet))
            if topic_fit_result is not None:
                item["extras"]["topic_fit"] = topic_fit_result
                returned_topic_fit_results.append(topic_fit_result)
            items.append(item)
        returned_topic_fit_reason_counts = _topic_fit_reason_counts(returned_topic_fit_results)
        return self.ok_result(
            "user_posts",
            items=items,
            raw=raw,
            meta=self.make_meta(
                value=normalized,
                limit=requested_limit,
                started_at=started_at,
                originals_only=effective_originals_only or None,
                min_likes=min_likes,
                min_retweets=min_retweets,
                min_views=min_views,
                topic_fit=normalized_topic_fit if topic_fit is not None else None,
                quality_profile=effective_quality_profile,
                fetch_limit=fetch_limit,
                **({"applied_defaults": applied_defaults} if applied_defaults else {}),
                **({"filter_drop_counts": merged_filter_drop_counts} if merged_filter_drop_counts else {}),
                **({"filter_drop_reasons": list(merged_filter_drop_counts)} if merged_filter_drop_counts else {}),
                **(
                    {"topic_fit_reason_counts": returned_topic_fit_reason_counts}
                    if returned_topic_fit_reason_counts
                    else {}
                ),
                diagnostics=_merge_diagnostics(
                    client_filter_diagnostics,
                    metric_diagnostics,
                    topic_fit_diagnostics,
                    quality_diagnostics,
                ),
                **_tweet_item_shape(engagement_complete=False, media_complete=False),
            ),
        )

    def tweet(self, tweet_id_or_url: str, limit: int = 20) -> CollectionResult:
        started_at = time.perf_counter()
        normalized = _normalize_tweet_id(tweet_id_or_url)
        result = self._run_twitter(
            ["tweet", normalized, "-n", str(limit), "--json"],
            operation="tweet",
            value=normalized,
            limit=limit,
            started_at=started_at,
        )
        if isinstance(result, dict):
            return result

        raw, _raw_output = result
        data = raw.get("data", [])
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return self.error_result(
                "tweet",
                code="invalid_response",
                message="Twitter tweet returned an unexpected payload",
                raw=raw,
                meta=self.make_meta(value=normalized, limit=limit, started_at=started_at),
            )

        items = [
            _tweet_item(
                tweet,
                idx,
                self.channel,
            )
            for idx, tweet in enumerate(data)
        ]
        return self.ok_result(
            "tweet",
            items=items,
            raw=raw,
            meta=self.make_meta(
                value=normalized,
                limit=limit,
                started_at=started_at,
                **_tweet_item_shape(engagement_complete=True, media_complete=True),
            ),
        )

    def _run_twitter(
        self,
        args: list[str],
        *,
        operation: str,
        value: str,
        limit: int | None,
        started_at: float,
        extra_meta: dict[str, object] | None = None,
    ) -> tuple[dict, str] | CollectionResult:
        twitter = self.command_path("twitter")
        if not twitter:
            return self.error_result(
                operation,
                code="missing_dependency",
                message="twitter-cli is missing. Install it with uv tool install twitter-cli",
                meta=self.make_meta(value=value, limit=limit, started_at=started_at, **(extra_meta or {})),
            )

        try:
            result = self.run_command([twitter, *args], timeout=120)
        except Exception as exc:
            return self.error_result(
                operation,
                code="command_failed",
                message=f"Twitter {operation} failed: {exc}",
                meta=self.make_meta(value=value, limit=limit, started_at=started_at, **(extra_meta or {})),
            )

        raw_output = f"{result.stdout}\n{result.stderr}".strip()
        if result.returncode != 0:
            code = "command_failed"
            message = f"Twitter {operation} command did not complete cleanly"
            raw: dict | str = raw_output
            parsed_code, parsed_message, parsed_payload = _parse_error_output(raw_output)
            plain_code = _plain_error_code(raw_output)
            if parsed_code:
                code = parsed_code
            elif plain_code:
                code = plain_code
            if parsed_message:
                message = parsed_message
            elif plain_code:
                message = _plain_error_message(operation, plain_code) or message
            if parsed_payload is not None:
                raw = parsed_payload
            details: dict[str, object] = {"returncode": result.returncode}
            http_status = _detect_http_status(raw_output)
            if http_status is not None:
                details["http_status"] = http_status
            return self.error_result(
                operation,
                code=code,
                message=message,
                raw=raw,
                meta=self.make_meta(value=value, limit=limit, started_at=started_at, **(extra_meta or {})),
                details=details,
            )

        try:
            parsed_raw = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            return self.error_result(
                operation,
                code="invalid_response",
                message=f"Twitter {operation} returned a non-JSON payload",
                raw=raw_output,
                meta=self.make_meta(value=value, limit=limit, started_at=started_at, **(extra_meta or {})),
            )
        if not isinstance(parsed_raw, dict):
            return self.error_result(
                operation,
                code="invalid_response",
                message=f"Twitter {operation} returned an unexpected JSON payload",
                raw=parsed_raw,
                meta=self.make_meta(value=value, limit=limit, started_at=started_at, **(extra_meta or {})),
            )
        return parsed_raw, raw_output

