# -*- coding: utf-8 -*-
"""Deterministic evidence-utility scoring shared by mission and candidate planning."""

from __future__ import annotations

import math
import re
from typing import Any, Mapping, Sequence

from x_reach.high_signal import has_low_content, has_promo_phrase
from x_reach.topic_fit import topic_fit_quality_reasons, topic_fit_score_bonus

SCORING_RUBRIC_VERSION = "deterministic_evidence_v3"

_ENGAGEMENT_SCORE_CAP = 4.0
_CONCRETE_DETAIL_RE = re.compile(
    r"(\b\d{1,4}(?:[.,]\d+)?%?\b|\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|"
    r"\$[0-9]|\bv?\d+\.\d+\b|\b(?:p50|p90|p95|p99)\b|"
    r"\b(?:ms|sec|secs|seconds|minutes|hours|days|g|kg|mg|ml|l|oz|lb|"
    r"rpm|bar|psi|degc|degf|celsius|fahrenheit)\b)",
    re.IGNORECASE,
)
_FIRST_HAND_CONTEXT_RE = re.compile(
    r"(\b(?:i|we|my|our)\b.{0,64}\b"
    r"(?:tried|tested|built|shipped|deployed|migrated|ran|saw|found|noticed|"
    r"measured|benchmarked|reproduced|debugged|used|switched|paid|cancelled|"
    r"installed|upgraded|rolled back|hit|fixed|broke|dialed|dialled|brewed|"
    r"pulled|tasted|compared|changed|adjusted|logged|observed|recorded|cooked|"
    r"baked|mixed|weighed)\b|"
    r"\b(?:our|my) (?:team|company|org|production|prod|deployment|workflow)\b)",
    re.IGNORECASE,
)
_PROCESS_EVIDENCE_RE = re.compile(
    r"\b(?:tried|tested|ran|measured|benchmarked|timed|logged|observed|recorded|"
    r"reproduced|debugged|built|shipped|deployed|migrated|installed|upgraded|"
    r"rolled back|switched|changed|adjusted|compared|sampled|dialed|dialled|"
    r"brewed|pulled|tasted|cooked|baked|mixed|weighed|configured|"
    r"validated|verified)\b",
    re.IGNORECASE,
)
_OBSERVABLE_SIGNAL_RE = re.compile(
    r"\b(?:screenshot|screen recording|video|demo|log|logs|trace|stack trace|"
    r"error|repro|reproduced|benchmark|metric|metrics|chart|table|graph|diff|"
    r"commit|pull request|pr #?\d+|issue #?\d+|latency|throughput|photo|"
    r"before/after|before and after|result|results|measured|measurement|measurements)\b",
    re.IGNORECASE,
)
_COMPARISON_SIGNAL_RE = re.compile(
    r"\b(?:compared|versus|vs\.?|before/after|before and after|a/b|baseline|"
    r"regression|improved|worse|better|changed from|changed to)\b",
    re.IGNORECASE,
)
_SPECIFICITY_HINT_RE = re.compile(
    r"\b(?:workflow|setup|configuration|settings|recipe|process|steps|method|"
    r"workaround|rollout|deployment|tasting note|notes|details|ingredient|"
    r"sample|batch|run|trial|experiment)\b",
    re.IGNORECASE,
)
_PROMO_LANGUAGE_RE = re.compile(
    r"\b(?:ad|sponsored|sponsorship|giveaway|coupon|discount|promo code|use code|"
    r"referral|affiliate|sale|limited time|free shipping|merch|storefront|"
    r"shop now|buy now|order now|pre[- ]?order|link in bio|dm (?:me|us) to order|"
    r"grand opening|visit us at|book now|reserve now)\b",
    re.IGNORECASE,
)
_COMMERCE_LANGUAGE_RE = re.compile(
    r"\b(?:shop|buy|order|purchase|book|reserve|get yours|"
    r"available now|on sale|sold out|restock)\b",
    re.IGNORECASE,
)
_CTA_LANGUAGE_RE = re.compile(
    r"(\blink in bio\b|\bdm (?:me|us)\b|\b(?:click|tap|visit|follow|subscribe|"
    r"join|sign up|shop|buy|order|book|reserve|get|download)\b.{0,36}\b"
    r"(?:now|today|here|below|bio|link|for more|to order|to buy)\b)",
    re.IGNORECASE,
)
_GENERIC_ANNOUNCEMENT_RE = re.compile(
    r"\b(?:we'?re excited to announce|introducing|now available|launching|"
    r"just launched|new drop|come visit|check out our)\b",
    re.IGNORECASE,
)
_STRONG_TOPIC_FIT_REASONS = {
    "topic_fit_required_any",
    "topic_fit_required_all",
    "topic_fit_exact_phrase",
}
_NEGATIVE_REASON_KEYS = {
    "query_miss_penalty",
    "reply",
    "retweet",
    "thin_quote",
    "thin_content",
    "promo_language",
    "commerce_language",
    "cta_language",
    "generic_announcement",
    "low_evidence_promo",
    "cta_over_evidence",
    "weak_evidence_density",
    "coverage_topic_only",
    "media_only",
    "near_duplicate_downrank",
    "near_duplicate_promo_cluster",
    "near_duplicate_template",
}
_DOWNRANK_REASON_KEYS = {
    "near_duplicate_downrank",
    "near_duplicate_promo_cluster",
    "near_duplicate_template",
}
_URL_RE = re.compile(r"(?:https?://|www\.|t\.co/)\S+", re.IGNORECASE)
_MENTION_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{1,15}")
_HASHTAG_RE = re.compile(r"(?<!\w)#[\w_]+", re.UNICODE)
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+-]*", re.IGNORECASE)
_STOP_TOKENS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "because",
    "been",
    "before",
    "being",
    "but",
    "can",
    "for",
    "from",
    "get",
    "had",
    "has",
    "have",
    "here",
    "how",
    "into",
    "just",
    "link",
    "more",
    "now",
    "our",
    "out",
    "over",
    "post",
    "that",
    "the",
    "this",
    "today",
    "use",
    "was",
    "with",
    "you",
    "your",
}


def score_candidate(candidate: dict[str, Any]) -> tuple[float, list[str]]:
    """Return a deterministic utility score and compact reasons for a candidate."""

    score = 0.0
    reasons: list[str] = []
    topic_signal = False
    text = str(candidate.get("text") or candidate.get("title") or "")
    concrete_detail_count = _concrete_detail_count(candidate)
    first_hand_signal = _has_first_hand_signal(candidate)
    process_signal = _has_process_signal(candidate)
    observable_signal = _has_observable_signal(
        candidate,
        concrete_detail_count=concrete_detail_count,
        first_hand_signal=first_hand_signal,
        process_signal=process_signal,
    )
    comparison_signal = _has_comparison_signal(candidate)
    specificity_signal = _has_specificity_signal(candidate)
    evidence_support_units = sum(
        1
        for value in (
            concrete_detail_count > 0,
            first_hand_signal,
            process_signal,
            observable_signal,
            comparison_signal,
            specificity_signal,
        )
        if value
    )
    promo_language = _has_promo_language(text)
    commerce_language = _has_commerce_language(text)
    cta_language = _has_cta_language(text)
    generic_announcement = _has_generic_announcement(text)

    def add_reason(reason: str) -> None:
        if reason not in reasons:
            reasons.append(reason)

    seen_in_count = int(candidate.get("seen_in_count") or 0)
    if seen_in_count > 1:
        score += min(seen_in_count, 5) * 6.0
        add_reason("multi_seen")

    kind = _candidate_timeline_kind(candidate)
    if kind == "original":
        score += 8.0
        add_reason("original")
    elif kind == "quote":
        score += 3.0
        add_reason("quote")
    elif kind == "reply":
        score -= 4.0
        add_reason("reply")
    elif kind == "retweet":
        score -= 8.0
        add_reason("retweet")

    query_tokens = _candidate_query_tokens(candidate)
    if query_tokens:
        matched_tokens = _matched_candidate_query_tokens(candidate, query_tokens)
        if matched_tokens:
            match_ratio = len(matched_tokens) / len(query_tokens)
            score += 2.0 + min(len(matched_tokens) * 1.5, 4.0)
            add_reason("query_match")
            topic_signal = True
            if match_ratio >= 0.75:
                score += 2.0
                add_reason("strong_query_match")
        else:
            score -= 3.0
            add_reason("query_miss_penalty")

    engagement_score = _engagement_score(candidate)
    if engagement_score:
        if engagement_score > _ENGAGEMENT_SCORE_CAP:
            add_reason("engagement_capped")
        score += min(engagement_score, _ENGAGEMENT_SCORE_CAP)
        add_reason("engagement")

    if len(text) >= 80:
        score += 3.0
        add_reason("substantial_text")
    elif len(text) >= 35:
        score += 1.5
        add_reason("some_text")
    if candidate.get("media_references"):
        score += 0.5
        add_reason("media")
        if not observable_signal:
            add_reason("media_only")
    if candidate.get("url"):
        score += 0.5
        add_reason("has_url")
    if concrete_detail_count:
        score += min(2.0 + concrete_detail_count * 0.75, 4.0)
        add_reason("concrete_detail")
    if process_signal:
        score += 2.0
        add_reason("process_evidence")
    if first_hand_signal:
        score += 4.0
        add_reason("first_hand_signal")
    if observable_signal:
        score += 1.5
        add_reason("observable_signal")
    if comparison_signal:
        score += 1.5
        add_reason("comparison_signal")
    if specificity_signal:
        score += 1.0
        add_reason("specificity_signal")
    if _has_declared_diversity_signal(candidate):
        score += 0.75
        add_reason("novel_signal")
        if evidence_support_units == 0:
            score -= 1.5
            add_reason("coverage_topic_only")
    if kind == "quote" and len(_text_without_urls(text)) < 80:
        score -= 3.0
        add_reason("thin_quote")
    if has_low_content(text, item_kind=kind):
        score -= 3.0
        add_reason("thin_content")
    if promo_language:
        score -= 4.0
        add_reason("promo_language")
    if commerce_language:
        score -= 2.0
        add_reason("commerce_language")
    if cta_language:
        score -= 3.0
        add_reason("cta_language")
    if generic_announcement and evidence_support_units <= 1:
        score -= 1.5
        add_reason("generic_announcement")
    if (promo_language or commerce_language or cta_language or generic_announcement) and evidence_support_units <= 1:
        score -= 4.0
        add_reason("low_evidence_promo")
    if cta_language and evidence_support_units <= 1:
        score -= 2.0
        add_reason("cta_over_evidence")
    topic_fit = candidate.get("topic_fit") if isinstance(candidate.get("topic_fit"), dict) else None
    topic_bonus = topic_fit_score_bonus(topic_fit)
    if topic_bonus:
        score += min(topic_bonus, 3.0)
        topic_reasons = topic_fit_quality_reasons(topic_fit)
        for reason in topic_reasons:
            add_reason(reason)
        topic_signal = True
        if _has_strong_topic_fit(topic_bonus, topic_reasons):
            score += 1.0
            add_reason("topic_fit_strong")
    if topic_signal and evidence_support_units == 0:
        score -= 3.0
        add_reason("weak_evidence_density")
    if topic_signal and evidence_support_units >= 3:
        score += 2.5
        add_reason("evidence_dense")
    return round(score, 3), reasons


def apply_ranking_quality_adjustments(candidates: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply deterministic cross-candidate downranks that need ranking context."""

    adjusted = [_copy_candidate(candidate) for candidate in candidates]
    ranked_indexes = sorted(
        range(len(adjusted)),
        key=lambda index: (-float(adjusted[index].get("quality_score") or 0), index),
    )
    representatives: list[dict[str, Any]] = []
    cluster_counts: dict[int, int] = {}

    for index in ranked_indexes:
        candidate = adjusted[index]
        signature = _near_duplicate_signature(candidate)
        if signature is None:
            continue
        cluster_index = _matching_near_duplicate_cluster(signature, representatives)
        if cluster_index is None:
            representatives.append(signature)
            cluster_counts[len(representatives) - 1] = 1
            continue

        duplicate_number = cluster_counts.get(cluster_index, 1)
        cluster_counts[cluster_index] = duplicate_number + 1
        penalty = min(4.0 + duplicate_number * 1.5, 8.0)
        candidate["quality_score"] = round(float(candidate.get("quality_score") or 0) - penalty, 3)
        reasons = _candidate_reasons(candidate)
        if "near_duplicate_downrank" not in reasons:
            reasons.append("near_duplicate_downrank")
        if signature["promoish"]:
            if "near_duplicate_promo_cluster" not in reasons:
                reasons.append("near_duplicate_promo_cluster")
        elif "near_duplicate_template" not in reasons:
            reasons.append("near_duplicate_template")
        candidate["quality_reasons"] = reasons

    return adjusted


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
    reason_counts = quality_reason_counts(candidates)
    return {
        "scoring_version": SCORING_RUBRIC_VERSION,
        "scored_candidates": scored_candidates,
        "reason_counts": reason_counts,
        "negative_reason_counts": {
            key: reason_counts[key]
            for key in sorted(reason_counts)
            if key in _NEGATIVE_REASON_KEYS
        },
        "downrank_reason_counts": {
            key: reason_counts[key]
            for key in sorted(reason_counts)
            if key in _DOWNRANK_REASON_KEYS
        },
        "downrank_samples": _downrank_samples(candidates),
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
    return bool(_FIRST_HAND_CONTEXT_RE.search(text)) or bool(_PROCESS_EVIDENCE_RE.search(text))


def _has_process_signal(candidate: dict[str, Any]) -> bool:
    text = str(candidate.get("text") or candidate.get("title") or "")
    return bool(_PROCESS_EVIDENCE_RE.search(text))


def _has_observable_signal(
    candidate: dict[str, Any],
    *,
    concrete_detail_count: int,
    first_hand_signal: bool,
    process_signal: bool,
) -> bool:
    text = str(candidate.get("text") or candidate.get("title") or "")
    if _OBSERVABLE_SIGNAL_RE.search(text):
        return True
    if not candidate.get("media_references"):
        return False
    return concrete_detail_count > 0 or first_hand_signal or process_signal or _has_specificity_signal(candidate)


def _has_comparison_signal(candidate: dict[str, Any]) -> bool:
    text = str(candidate.get("text") or candidate.get("title") or "")
    return bool(_COMPARISON_SIGNAL_RE.search(text))


def _has_specificity_signal(candidate: dict[str, Any]) -> bool:
    text = str(candidate.get("text") or candidate.get("title") or "")
    return bool(_SPECIFICITY_HINT_RE.search(text))


def _has_promo_language(text: str) -> bool:
    return has_promo_phrase(text) or bool(_PROMO_LANGUAGE_RE.search(text))


def _has_commerce_language(text: str) -> bool:
    return bool(_COMMERCE_LANGUAGE_RE.search(text))


def _has_cta_language(text: str) -> bool:
    return bool(_CTA_LANGUAGE_RE.search(text))


def _has_generic_announcement(text: str) -> bool:
    return bool(_GENERIC_ANNOUNCEMENT_RE.search(text))


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


def _candidate_reasons(candidate: Mapping[str, Any]) -> list[str]:
    reasons = candidate.get("quality_reasons")
    if not isinstance(reasons, list):
        return []
    return [str(reason) for reason in reasons]


def _downrank_samples(candidates: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for candidate in candidates:
        reasons = [reason for reason in _candidate_reasons(candidate) if reason in _DOWNRANK_REASON_KEYS]
        if not reasons:
            continue
        text = str(candidate.get("text") or candidate.get("title") or "")
        samples.append(
            {
                "id": candidate.get("id"),
                "source_item_id": candidate.get("source_item_id"),
                "reasons": reasons,
                "quality_score": candidate.get("quality_score"),
                "text_preview": text[:160],
            }
        )
        if len(samples) >= 5:
            break
    return samples


def _near_duplicate_signature(candidate: Mapping[str, Any]) -> dict[str, Any] | None:
    text = " ".join(
        str(value or "")
        for value in (
            candidate.get("title"),
            candidate.get("text"),
        )
    )
    tokens = _near_duplicate_tokens(text)
    if len(tokens) < 6:
        return None
    token_set = set(tokens)
    if len(token_set) < 5:
        return None
    author = str(candidate.get("author") or "").strip().casefold()
    promoish = any(
        reason in _candidate_reasons(candidate)
        for reason in (
            "promo_language",
            "commerce_language",
            "cta_language",
            "generic_announcement",
            "low_evidence_promo",
            "weak_evidence_density",
        )
    )
    text_key = " ".join(tokens[:48])
    return {
        "author": author,
        "prefix": tuple(tokens[:10]),
        "tokens": token_set,
        "text_key": text_key,
        "promoish": promoish,
    }


def _near_duplicate_tokens(text: str) -> list[str]:
    cleaned = _URL_RE.sub(" ", str(text or "").casefold())
    cleaned = _MENTION_RE.sub(" ", cleaned)
    cleaned = _HASHTAG_RE.sub(lambda match: " " + match.group(0).lstrip("#") + " ", cleaned)
    tokens: list[str] = []
    for match in _TOKEN_RE.finditer(cleaned):
        token = match.group(0)
        token = "0" if token.isdigit() else token
        if len(token) < 3 and token != "0":
            continue
        if token in _STOP_TOKENS:
            continue
        tokens.append(token)
    return tokens


def _matching_near_duplicate_cluster(
    signature: Mapping[str, Any],
    representatives: Sequence[Mapping[str, Any]],
) -> int | None:
    for index, representative in enumerate(representatives):
        if _signatures_near_duplicate(signature, representative):
            return index
    return None


def _signatures_near_duplicate(current: Mapping[str, Any], representative: Mapping[str, Any]) -> bool:
    current_tokens = current.get("tokens")
    representative_tokens = representative.get("tokens")
    if not isinstance(current_tokens, set) or not isinstance(representative_tokens, set):
        return False
    shared = len(current_tokens & representative_tokens)
    if shared < 5:
        return False
    overlap = shared / max(min(len(current_tokens), len(representative_tokens)), 1)
    union = len(current_tokens | representative_tokens)
    jaccard = shared / max(union, 1)
    same_author = bool(current.get("author")) and current.get("author") == representative.get("author")
    same_text = bool(current.get("text_key")) and current.get("text_key") == representative.get("text_key")
    same_prefix = tuple(current.get("prefix") or ())[:8] == tuple(representative.get("prefix") or ())[:8]
    promoish = bool(current.get("promoish") or representative.get("promoish"))
    if same_text:
        return True
    if same_prefix and overlap >= 0.75:
        return True
    if overlap >= 0.9 and jaccard >= 0.72:
        return True
    if same_author and promoish and overlap >= 0.62:
        return True
    if promoish and overlap >= 0.72 and jaccard >= 0.55:
        return True
    return False


def _number_or_zero(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return 0.0
