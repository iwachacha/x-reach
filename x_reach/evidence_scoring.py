# -*- coding: utf-8 -*-
"""Deterministic evidence-utility scoring shared by mission and candidate planning."""

from __future__ import annotations

import math
import re
from typing import Any, Sequence

from x_reach.high_signal import has_low_content, has_promo_phrase
from x_reach.topic_fit import topic_fit_quality_reasons, topic_fit_score_bonus

SCORING_RUBRIC_VERSION = "deterministic_evidence_v2"

_ENGAGEMENT_SCORE_CAP = 6.0
_CONCRETE_DETAIL_RE = re.compile(
    r"(\b\d{1,4}(?:[.,]\d+)?%?\b|\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|"
    r"\$[0-9]|\bv?\d+\.\d+\b|\b(?:p50|p90|p95|p99)\b|"
    r"\b(?:ms|sec|secs|seconds|minutes|hours|days)\b)",
    re.IGNORECASE,
)
_FIRST_HAND_SIGNAL_RE = re.compile(
    r"(\b(?:i|we|my|our)\b.{0,48}\b"
    r"(?:tried|tested|built|shipped|deployed|migrated|ran|saw|found|noticed|"
    r"measured|benchmarked|reproduced|debugged|used|switched|paid|cancelled|"
    r"installed|upgraded|rolled back|hit|fixed|broke)\b|"
    r"\b(?:our|my) (?:team|company|org|production|prod|deployment|workflow)\b)",
    re.IGNORECASE,
)
_OBSERVABLE_SIGNAL_RE = re.compile(
    r"\b(?:screenshot|screen recording|video|demo|log|logs|trace|stack trace|"
    r"error|repro|reproduced|benchmark|metric|metrics|chart|table|graph|diff|"
    r"commit|pull request|pr #?\d+|issue #?\d+|latency|throughput)\b",
    re.IGNORECASE,
)
_STRONG_TOPIC_FIT_REASONS = {
    "topic_fit_required_any",
    "topic_fit_required_all",
    "topic_fit_exact_phrase",
}


def score_candidate(candidate: dict[str, Any]) -> tuple[float, list[str]]:
    """Return a deterministic utility score and compact reasons for a candidate."""

    score = 0.0
    reasons: list[str] = []
    evidence_units = 0
    topic_signal = False
    seen_in_count = int(candidate.get("seen_in_count") or 0)
    if seen_in_count > 1:
        score += min(seen_in_count, 5) * 6.0
        reasons.append("multi_seen")
        evidence_units += 1

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
            topic_signal = True
            evidence_units += 1
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
        evidence_units += 1
    elif len(text) >= 35:
        score += 2.0
        reasons.append("some_text")
    if candidate.get("media_references"):
        score += 1.0
        reasons.append("media")
        evidence_units += 1
    if candidate.get("url"):
        score += 1.0
        reasons.append("has_url")
        evidence_units += 1
    concrete_detail_count = _concrete_detail_count(candidate)
    if concrete_detail_count:
        score += 3.0
        reasons.append("concrete_detail")
        evidence_units += min(concrete_detail_count, 3)
    if _has_first_hand_signal(candidate):
        score += 3.0
        reasons.append("first_hand_signal")
        evidence_units += 1
    if _has_observable_signal(candidate):
        score += 2.0
        reasons.append("observable_signal")
        evidence_units += 1
    if _has_declared_diversity_signal(candidate):
        score += 2.0
        reasons.append("novel_signal")
        evidence_units += 1
    if kind == "quote" and len(_text_without_urls(text)) < 80:
        score -= 3.0
        reasons.append("thin_quote")
    if has_low_content(text, item_kind=kind):
        score -= 3.0
        reasons.append("thin_content")
    if has_promo_phrase(text):
        score -= 2.0
        reasons.append("promo_language")
    topic_fit = candidate.get("topic_fit") if isinstance(candidate.get("topic_fit"), dict) else None
    topic_bonus = topic_fit_score_bonus(topic_fit)
    if topic_bonus:
        score += topic_bonus
        topic_reasons = topic_fit_quality_reasons(topic_fit)
        reasons.extend(topic_reasons)
        topic_signal = True
        evidence_units += 1
        if _has_strong_topic_fit(topic_bonus, topic_reasons):
            score += 2.0
            reasons.append("topic_fit_strong")
    if topic_signal and evidence_units >= 4:
        score += 2.5
        reasons.append("evidence_dense")
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


def quality_diagnostics(candidates: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Return compact public diagnostics for deterministic quality scoring."""

    scored_candidates = 0
    for candidate in candidates:
        value = candidate.get("quality_score")
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            scored_candidates += 1
    return {
        "scoring_version": SCORING_RUBRIC_VERSION,
        "scored_candidates": scored_candidates,
        "reason_counts": quality_reason_counts(candidates),
    }


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
    raw_engagement = candidate.get("engagement")
    engagement = raw_engagement if isinstance(raw_engagement, dict) else {}
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


def _concrete_detail_count(candidate: dict[str, Any]) -> int:
    text = str(candidate.get("text") or candidate.get("title") or "")
    return len({match.group(0).casefold() for match in _CONCRETE_DETAIL_RE.finditer(text)})


def _has_first_hand_signal(candidate: dict[str, Any]) -> bool:
    text = str(candidate.get("text") or candidate.get("title") or "")
    return bool(_FIRST_HAND_SIGNAL_RE.search(text))


def _has_observable_signal(candidate: dict[str, Any]) -> bool:
    text = str(candidate.get("text") or candidate.get("title") or "")
    return bool(candidate.get("media_references")) or bool(_OBSERVABLE_SIGNAL_RE.search(text))


def _has_declared_diversity_signal(candidate: dict[str, Any]) -> bool:
    raw_topics = candidate.get("coverage_topics")
    if isinstance(raw_topics, list) and raw_topics:
        return True
    source_role = str(candidate.get("source_role") or "").strip().casefold()
    return source_role == "coverage_gap_fill"


def _has_strong_topic_fit(topic_bonus: float, topic_reasons: Sequence[str]) -> bool:
    return topic_bonus >= 4.0 or any(reason in _STRONG_TOPIC_FIT_REASONS for reason in topic_reasons)


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
