# -*- coding: utf-8 -*-
"""Shared high-signal collection heuristics for X Reach."""

from __future__ import annotations

import re
from typing import Any, Sequence

from x_reach.results import normalize_engagement

QUALITY_PROFILES = ("precision", "balanced", "recall")
BROAD_OPERATIONS = frozenset({"search", "hashtag", "user_posts"})
DEFAULT_BROAD_RAW_MODE = "none"
DEFAULT_BROAD_ITEM_TEXT_MODE = "snippet"
DEFAULT_BROAD_ITEM_TEXT_MAX_CHARS = 280

_QUALITY_FETCH_MULTIPLIERS = {
    "precision": 5,
    "balanced": 3,
    "recall": 1,
}
_QUALITY_FETCH_CAPS = {
    "precision": 150,
    "balanced": 100,
    "recall": None,
}
_QUALITY_ENGAGEMENT_THRESHOLDS = {
    "precision": {"views": 5000, "likes": 100, "retweets": 20},
    "balanced": {"views": 1000, "likes": 25, "retweets": 5},
}
_DEFAULT_SEARCH_TYPE = {
    "precision": "top",
    "balanced": "top",
}
_DEFAULT_EXCLUDES = {
    "precision": ("retweets", "replies"),
    "balanced": ("retweets", "replies"),
}
_PROMO_PHRASES = (
    "airdrop",
    "giveaway",
    "referral",
    "promo code",
    "invite code",
    "dm me",
    "follow back",
    "whitelist",
    "mint live",
    "プレゼント企画",
)
_KNOWN_QUERY_OPERATORS = {
    "from",
    "to",
    "lang",
    "type",
    "since",
    "until",
    "has",
    "exclude",
    "min_likes",
    "min-likes",
    "min_retweets",
    "min-retweets",
    "min_views",
    "min-views",
}
_HASHTAG_RE = re.compile(r"(?<!\w)#[\w_]+", re.UNICODE)
_CASHTAG_RE = re.compile(r"(?<!\w)\$[A-Za-z][A-Za-z0-9_]*")
_MENTION_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{1,15}")
_URL_RE = re.compile(r"(?:https?://|www\.|t\.co/)\S+", re.IGNORECASE)
_STRIP_PUNCTUATION = "\"'()[]{}<>.,!?;:"


def is_broad_operation(operation: str) -> bool:
    return operation in BROAD_OPERATIONS


def normalize_quality_profile(
    operation: str,
    quality_profile: str | None,
) -> str | None:
    if quality_profile is None:
        if is_broad_operation(operation):
            return "balanced"
        return None
    if quality_profile not in QUALITY_PROFILES:
        raise ValueError(
            "quality_profile must be one of: precision, balanced, recall"
        )
    return quality_profile


def resolve_fetch_limit(requested_limit: int, quality_profile: str | None) -> int:
    if quality_profile is None or quality_profile == "recall":
        return requested_limit
    multiplier = _QUALITY_FETCH_MULTIPLIERS[quality_profile]
    cap = _QUALITY_FETCH_CAPS[quality_profile]
    fetch_limit = requested_limit * multiplier
    if cap is not None:
        fetch_limit = min(fetch_limit, cap)
    return max(requested_limit, fetch_limit)


def resolve_default_search_type(
    search_type: str | None,
    quality_profile: str | None,
) -> tuple[str | None, bool]:
    if search_type is not None or quality_profile not in _DEFAULT_SEARCH_TYPE:
        return search_type, False
    return _DEFAULT_SEARCH_TYPE[quality_profile], True


def merge_default_excludes(
    exclude: Sequence[str] | None,
    quality_profile: str | None,
) -> tuple[list[str] | None, bool]:
    values: list[str] = []
    seen: set[str] = set()
    for raw_value in exclude or []:
        value = str(raw_value).strip()
        if value and value not in seen:
            values.append(value)
            seen.add(value)

    applied_default = False
    for value in _DEFAULT_EXCLUDES.get(quality_profile or "", ()):
        if value not in seen:
            values.append(value)
            seen.add(value)
            applied_default = True
    return (values or None), applied_default


def resolve_default_originals_only(
    originals_only: bool | None,
    quality_profile: str | None,
) -> tuple[bool, bool]:
    if originals_only is not None:
        return bool(originals_only), False
    if quality_profile in {"precision", "balanced"}:
        return True, True
    return False, False


def extract_query_tokens(query: str) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for raw_token in str(query or "").split():
        token = raw_token.strip()
        if not token:
            continue
        if ":" in token:
            key, _value = token.split(":", 1)
            if key.lower() in _KNOWN_QUERY_OPERATORS:
                continue
        normalized = token.strip(_STRIP_PUNCTUATION).lstrip("#").casefold()
        if not normalized:
            continue
        if len(normalized) < 2 and normalized.isascii():
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        tokens.append(normalized)
    return tokens


def timeline_item_kind(raw_kind: str | None) -> str | None:
    if raw_kind is None:
        return None
    kind = str(raw_kind).strip().lower()
    return kind or None


def original_preference_rank(raw_kind: str | None) -> int:
    kind = timeline_item_kind(raw_kind)
    if kind == "original":
        return 0
    if kind == "quote":
        return 1
    if kind == "reply":
        return 2
    if kind == "retweet":
        return 3
    return 4


def analyze_item_quality(
    *,
    text: str | None,
    searchable_parts: Sequence[str | None] | None = None,
    urls: Sequence[str] | None = None,
    query_tokens: Sequence[str] | None = None,
    item_kind: str | None = None,
    engagement: dict[str, Any] | None = None,
    quality_profile: str | None = None,
    require_query_match: bool = False,
    drop_retweets: bool = False,
    drop_replies: bool = False,
    drop_low_content: bool = False,
) -> dict[str, Any]:
    matched_tokens = _matched_query_tokens(searchable_parts or (text,), query_tokens or ())
    noise_counts = structural_noise_counts(text, urls=urls)
    reasons: list[str] = []
    normalized_kind = timeline_item_kind(item_kind)

    if drop_retweets and normalized_kind == "retweet":
        reasons.append("retweet")
    if drop_replies and normalized_kind == "reply":
        reasons.append("reply")
    if require_query_match and query_tokens and not matched_tokens:
        reasons.append("query_miss")
    if has_structural_noise(noise_counts):
        reasons.append("structural_noise")
    if has_promo_phrase(text):
        reasons.append("promo_phrase")
    low_content = has_low_content(text, item_kind=normalized_kind)
    if drop_low_content and low_content:
        reasons.append("low_content")

    engagement_pass = passes_engagement_gate(engagement, quality_profile)
    if quality_profile in _QUALITY_ENGAGEMENT_THRESHOLDS and not engagement_pass:
        reasons.append("engagement_gate")

    return {
        "item_kind": normalized_kind,
        "matched_query_tokens": matched_tokens,
        "topic_match": bool(matched_tokens) if query_tokens else True,
        "structural_noise_counts": noise_counts,
        "structural_noise": has_structural_noise(noise_counts),
        "promo_phrase": has_promo_phrase(text),
        "low_content": low_content,
        "engagement_pass": engagement_pass,
        "drop_reasons": reasons,
    }


def passes_engagement_gate(
    engagement: dict[str, Any] | None,
    quality_profile: str | None,
) -> bool:
    thresholds = _QUALITY_ENGAGEMENT_THRESHOLDS.get(quality_profile or "")
    if thresholds is None:
        return True
    normalized = normalize_engagement(engagement)
    return any((normalized.get(field) or 0) >= threshold for field, threshold in thresholds.items())


def structural_noise_counts(
    text: str | None,
    *,
    urls: Sequence[str] | None = None,
) -> dict[str, int]:
    content = str(text or "")
    detected_urls = max(len([value for value in (urls or []) if value]), len(_URL_RE.findall(content)))
    return {
        "hashtags": len(_HASHTAG_RE.findall(content)),
        "cashtags": len(_CASHTAG_RE.findall(content)),
        "mentions": len(_MENTION_RE.findall(content)),
        "urls": detected_urls,
    }


def has_structural_noise(counts: dict[str, int]) -> bool:
    return (
        counts.get("hashtags", 0) >= 5
        or counts.get("cashtags", 0) >= 3
        or counts.get("mentions", 0) >= 4
        or counts.get("urls", 0) >= 2
    )


def has_promo_phrase(text: str | None) -> bool:
    haystack = str(text or "").casefold()
    return any(phrase in haystack for phrase in _PROMO_PHRASES)


def has_low_content(text: str | None, *, item_kind: str | None = None) -> bool:
    """Return True when text is too thin to stand alone as research evidence."""

    normalized = " ".join(str(text or "").split())
    if not normalized:
        return True
    words = normalized.split()
    if len(normalized) <= 12:
        return True
    if item_kind == "quote" and len(words) <= 8 and normalized.endswith(":"):
        return True
    return False


def maybe_urls(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if str(item).strip()]


def _matched_query_tokens(parts: Sequence[str | None], query_tokens: Sequence[str]) -> list[str]:
    haystack = " ".join(str(part or "").casefold() for part in parts if part).strip()
    if not haystack:
        return []
    matched: list[str] = []
    for token in query_tokens:
        normalized = str(token).casefold()
        if normalized and normalized in haystack:
            matched.append(normalized)
    return matched
