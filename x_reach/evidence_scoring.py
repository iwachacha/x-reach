# -*- coding: utf-8 -*-
"""Deterministic evidence-utility scoring shared by mission and candidate planning."""

from __future__ import annotations

import math
import re
from typing import Any, Sequence

from x_reach.high_signal import has_low_content, has_promo_phrase

_ENGAGEMENT_SCORE_CAP = 6.0
_CONCRETE_DETAIL_RE = re.compile(
    r"(\b\d{1,4}(?:[.,]\d+)?%?\b|\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|"
    r"\$[0-9]|\bv?\d+\.\d+\b)",
    re.IGNORECASE,
)


def score_candidate(candidate: dict[str, Any]) -> tuple[float, list[str]]:
    """Return a deterministic utility score and compact reasons for a candidate."""

    score = 0.0
    reasons: list[str] = []
    seen_in_count = int(candidate.get("seen_in_count") or 0)
    if seen_in_count > 1:
        score += min(seen_in_count, 5) * 6.0
        reasons.append("multi_seen")

    kind = _candidate_timeline_kind(candidate)
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

    query_tokens = _candidate_query_tokens(candidate)
    if query_tokens:
        matched_tokens = _matched_candidate_query_tokens(candidate, query_tokens)
        if matched_tokens:
            match_ratio = len(matched_tokens) / len(query_tokens)
            score += 2.0 + min(len(matched_tokens) * 1.5, 4.0)
            reasons.append("query_match")
            if match_ratio >= 0.75:
                score += 2.0
                reasons.append("strong_query_match")
        else:
            score -= 3.0
            reasons.append("query_miss_penalty")

    engagement_score = _engagement_score(candidate)
    if engagement_score:
        if engagement_score > _ENGAGEMENT_SCORE_CAP:
            reasons.append("engagement_capped")
        score += min(engagement_score, _ENGAGEMENT_SCORE_CAP)
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
    if _has_concrete_detail(candidate):
        score += 3.0
        reasons.append("concrete_detail")
    if kind == "quote" and len(_text_without_urls(text)) < 80:
        score -= 3.0
        reasons.append("thin_quote")
    if has_low_content(text, item_kind=kind):
        score -= 3.0
        reasons.append("thin_content")
    if has_promo_phrase(text):
        score -= 2.0
        reasons.append("promo_language")
    return round(score, 3), reasons


def quality_reason_counts(candidates: Sequence[dict[str, Any]]) -> dict[str, int]:
    """Count score reasons in a stable order."""

    counts: dict[str, int] = {}
    for candidate in candidates:
        reasons = candidate.get("quality_reasons")
        if not isinstance(reasons, list):
            continue
        for reason in reasons:
            reason_key = str(reason)
            counts[reason_key] = counts.get(reason_key, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _candidate_timeline_kind(candidate: dict[str, Any]) -> str:
    raw_extras = candidate.get("extras")
    extras = raw_extras if isinstance(raw_extras, dict) else {}
    return str(extras.get("timeline_item_kind") or "").lower()


def _candidate_query_tokens(candidate: dict[str, Any]) -> list[str]:
    raw_extras = candidate.get("extras")
    extras = raw_extras if isinstance(raw_extras, dict) else {}
    raw_tokens = extras.get("query_tokens")
    if not isinstance(raw_tokens, list):
        return []
    tokens: list[str] = []
    seen: set[str] = set()
    for raw_token in raw_tokens:
        token = str(raw_token or "").strip().casefold()
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _matched_candidate_query_tokens(candidate: dict[str, Any], query_tokens: Sequence[str]) -> list[str]:
    haystack = _candidate_search_text(candidate).casefold()
    matched: list[str] = []
    for token in query_tokens:
        if token and token in haystack:
            matched.append(token)
    return matched


def _candidate_search_text(candidate: dict[str, Any]) -> str:
    return " ".join(
        str(value or "")
        for value in (
            candidate.get("title"),
            candidate.get("text"),
            candidate.get("author"),
            candidate.get("url"),
            candidate.get("canonical_url"),
        )
    )


def _engagement_score(candidate: dict[str, Any]) -> float:
    engagement = candidate.get("engagement") if isinstance(candidate.get("engagement"), dict) else {}
    score = 0.0
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
            score += math.log10(value + 1) * weight
    return score


def _has_concrete_detail(candidate: dict[str, Any]) -> bool:
    text = str(candidate.get("text") or candidate.get("title") or "")
    return bool(_CONCRETE_DETAIL_RE.search(text))


def _text_without_urls(text: str) -> str:
    return re.sub(r"https?://\S+", "", text).strip()


def _number_or_zero(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return 0.0
