# -*- coding: utf-8 -*-
"""Deterministic caller-declared topic-fit rules."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

TOPIC_FIT_LIST_FIELDS = (
    "required_any_terms",
    "required_all_terms",
    "preferred_terms",
    "excluded_terms",
    "exact_phrases",
    "negative_phrases",
)

TOPIC_FIT_MATCH_REQUIRED_ANY = "topic_fit_required_any"
TOPIC_FIT_MATCH_REQUIRED_ALL = "topic_fit_required_all"
TOPIC_FIT_MATCH_PREFERRED = "topic_fit_preferred"
TOPIC_FIT_MATCH_EXACT_PHRASE = "topic_fit_exact_phrase"
TOPIC_FIT_MATCH_SYNONYM_GROUP = "topic_fit_synonym_group"

TOPIC_FIT_DROP_EXCLUDED_TERM = "topic_fit_excluded_term"
TOPIC_FIT_DROP_NEGATIVE_PHRASE = "topic_fit_negative_phrase"
TOPIC_FIT_DROP_MISSING_REQUIRED_ANY = "topic_fit_missing_required_any"
TOPIC_FIT_DROP_MISSING_REQUIRED_ALL = "topic_fit_missing_required_all"

_SPACE_RE = re.compile(r"\s+")


def normalize_topic_fit_rules(raw_rules: Any) -> dict[str, Any]:
    """Normalize a caller-supplied topic-fit rule block."""

    if raw_rules is None:
        return _empty_rules()
    if not isinstance(raw_rules, Mapping):
        raise ValueError("topic_fit must be an object")

    rules = _empty_rules()
    for field in TOPIC_FIT_LIST_FIELDS:
        rules[field] = _normalize_text_list(raw_rules.get(field), name=f"topic_fit.{field}")
    rules["synonym_groups"] = _normalize_synonym_groups(raw_rules.get("synonym_groups"))
    return rules


def topic_fit_rules_enabled(rules: Mapping[str, Any] | None) -> bool:
    """Return True when a normalized rule block has any active rule."""

    if not isinstance(rules, Mapping):
        return False
    for field in TOPIC_FIT_LIST_FIELDS:
        if rules.get(field):
            return True
    return bool(rules.get("synonym_groups"))


def evaluate_topic_fit(parts: Sequence[Any], rules: Mapping[str, Any] | None) -> dict[str, Any]:
    """Evaluate text against topic-fit rules without model judgment."""

    normalized_rules = normalize_topic_fit_rules(rules)
    enabled = topic_fit_rules_enabled(normalized_rules)
    if not enabled:
        return {
            "enabled": False,
            "matched": True,
            "drop_reasons": [],
            "match_reasons": [],
            "matched_terms": {},
            "missing_required": {},
            "score_bonus": 0.0,
        }

    haystack = _normalize_search_text(" ".join(str(part or "") for part in parts if part is not None))
    matched_terms: dict[str, list[str]] = {}
    missing_required: dict[str, list[str]] = {}
    drop_reasons: list[str] = []
    match_reasons: list[str] = []
    score_bonus = 0.0

    excluded_matches = _matched_declared_terms(
        haystack,
        normalized_rules["excluded_terms"],
        normalized_rules,
        expand_synonyms=False,
    )
    if excluded_matches:
        matched_terms["excluded_terms"] = excluded_matches
        drop_reasons.append(TOPIC_FIT_DROP_EXCLUDED_TERM)

    negative_matches = _matched_plain_values(haystack, normalized_rules["negative_phrases"])
    if negative_matches:
        matched_terms["negative_phrases"] = negative_matches
        drop_reasons.append(TOPIC_FIT_DROP_NEGATIVE_PHRASE)

    required_any = normalized_rules["required_any_terms"]
    required_any_matches = _matched_declared_terms(haystack, required_any, normalized_rules)
    if required_any:
        if required_any_matches:
            matched_terms["required_any_terms"] = required_any_matches
            match_reasons.append(TOPIC_FIT_MATCH_REQUIRED_ANY)
            score_bonus += 2.0
        else:
            missing_required["required_any_terms"] = list(required_any)
            drop_reasons.append(TOPIC_FIT_DROP_MISSING_REQUIRED_ANY)

    required_all = normalized_rules["required_all_terms"]
    required_all_matches, required_all_missing = _matched_required_all(haystack, required_all, normalized_rules)
    if required_all_matches:
        matched_terms["required_all_terms"] = required_all_matches
        match_reasons.append(TOPIC_FIT_MATCH_REQUIRED_ALL)
        score_bonus += min(len(required_all_matches), 4) * 1.0
    if required_all_missing:
        missing_required["required_all_terms"] = required_all_missing
        drop_reasons.append(TOPIC_FIT_DROP_MISSING_REQUIRED_ALL)

    preferred_matches = _matched_declared_terms(haystack, normalized_rules["preferred_terms"], normalized_rules)
    if preferred_matches:
        matched_terms["preferred_terms"] = preferred_matches
        match_reasons.append(TOPIC_FIT_MATCH_PREFERRED)
        score_bonus += min(len(preferred_matches), 3) * 1.0

    phrase_matches = _matched_plain_values(haystack, normalized_rules["exact_phrases"])
    if phrase_matches:
        matched_terms["exact_phrases"] = phrase_matches
        match_reasons.append(TOPIC_FIT_MATCH_EXACT_PHRASE)
        score_bonus += min(len(phrase_matches), 2) * 2.0

    synonym_matches = _matched_synonym_groups(haystack, normalized_rules["synonym_groups"])
    if synonym_matches:
        matched_terms["synonym_groups"] = synonym_matches
        match_reasons.append(TOPIC_FIT_MATCH_SYNONYM_GROUP)
        score_bonus += min(len(synonym_matches), 3) * 0.75

    unique_drop_reasons = _dedupe(drop_reasons)
    return {
        "enabled": True,
        "matched": not unique_drop_reasons,
        "drop_reasons": unique_drop_reasons,
        "match_reasons": _dedupe(match_reasons),
        "matched_terms": matched_terms,
        "missing_required": missing_required,
        "score_bonus": round(score_bonus, 3),
    }


def evaluate_candidate_topic_fit(candidate: Mapping[str, Any], rules: Mapping[str, Any] | None) -> dict[str, Any]:
    """Evaluate a public candidate-shaped mapping against topic-fit rules."""

    return evaluate_topic_fit(candidate_topic_fit_parts(candidate), rules)


def candidate_topic_fit_parts(candidate: Mapping[str, Any]) -> list[Any]:
    """Return candidate fields that callers reasonably expect topic-fit to inspect."""

    raw_extras = candidate.get("extras")
    extras = raw_extras if isinstance(raw_extras, Mapping) else {}
    parts: list[Any] = [
        candidate.get("title"),
        candidate.get("text"),
        candidate.get("author"),
        candidate.get("url"),
        candidate.get("canonical_url"),
        extras.get("author_name"),
        extras.get("author_handle"),
        extras.get("quoted_author_name"),
        extras.get("quoted_author_handle"),
    ]
    raw_urls = extras.get("urls")
    if isinstance(raw_urls, Sequence) and not isinstance(raw_urls, (str, bytes)):
        parts.extend(raw_urls)
    return parts


def topic_fit_quality_reasons(result: Mapping[str, Any] | None) -> list[str]:
    """Return positive topic-fit reasons suitable for quality diagnostics."""

    if not isinstance(result, Mapping) or not result.get("matched"):
        return []
    reasons = result.get("match_reasons")
    if not isinstance(reasons, list):
        return []
    return [str(reason) for reason in reasons if str(reason).startswith("topic_fit_")]


def topic_fit_score_bonus(result: Mapping[str, Any] | None) -> float:
    """Return the deterministic score bonus emitted by the evaluator."""

    if not isinstance(result, Mapping) or not result.get("matched"):
        return 0.0
    value = result.get("score_bonus")
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def topic_fit_reason_counts(candidates: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Count positive topic-fit match reasons in stable order."""

    counts: dict[str, int] = {}
    for candidate in candidates:
        for reason in topic_fit_quality_reasons(candidate.get("topic_fit")):
            counts[reason] = counts.get(reason, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def topic_fit_result_summary(
    rules: Mapping[str, Any] | None,
    results: Sequence[Mapping[str, Any]],
    *,
    query_match_fallback_used: bool = False,
) -> dict[str, Any]:
    """Summarize topic-fit evaluations for diagnostics."""

    normalized_rules = normalize_topic_fit_rules(rules)
    enabled = topic_fit_rules_enabled(normalized_rules)
    drop_counts: dict[str, int] = {}
    match_counts: dict[str, int] = {}
    missing_counts: dict[str, int] = {}
    matched = 0
    dropped = 0
    for result in results:
        if result.get("matched"):
            matched += 1
        else:
            dropped += 1
        for reason in result.get("drop_reasons") or []:
            key = str(reason)
            drop_counts[key] = drop_counts.get(key, 0) + 1
        for reason in result.get("match_reasons") or []:
            key = str(reason)
            match_counts[key] = match_counts.get(key, 0) + 1
        missing = result.get("missing_required")
        if isinstance(missing, Mapping):
            for field, values in missing.items():
                key = str(field)
                if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
                    missing_counts[key] = missing_counts.get(key, 0) + len(values)
                else:
                    missing_counts[key] = missing_counts.get(key, 0) + 1
    return {
        "enabled": enabled,
        "rules": normalized_rules if enabled else {},
        "query_match_fallback_used": bool(query_match_fallback_used),
        "evaluated": len(results),
        "matched": matched,
        "dropped": dropped,
        "drop_counts": {key: drop_counts[key] for key in sorted(drop_counts)},
        "match_reason_counts": {key: match_counts[key] for key in sorted(match_counts)},
        "missing_required_counts": {key: missing_counts[key] for key in sorted(missing_counts)},
    }


def _empty_rules() -> dict[str, Any]:
    return {**{field: [] for field in TOPIC_FIT_LIST_FIELDS}, "synonym_groups": []}


def _normalize_text_list(value: Any, *, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    values: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        key = _normalize_search_text(text)
        if not key or key in seen:
            continue
        seen.add(key)
        values.append(text)
    return values


def _normalize_synonym_groups(value: Any) -> list[list[str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("topic_fit.synonym_groups must be a list")
    groups: list[list[str]] = []
    seen_groups: set[tuple[str, ...]] = set()
    for index, group in enumerate(value, start=1):
        if not isinstance(group, list):
            raise ValueError(f"topic_fit.synonym_groups[{index}] must be a list")
        terms: list[str] = []
        seen_terms: set[str] = set()
        for item in group:
            text = str(item or "").strip()
            key = _normalize_search_text(text)
            if not key or key in seen_terms:
                continue
            seen_terms.add(key)
            terms.append(text)
        if not terms:
            continue
        group_key = tuple(sorted(seen_terms))
        if group_key in seen_groups:
            continue
        seen_groups.add(group_key)
        groups.append(terms)
    return groups


def _matched_declared_terms(
    haystack: str,
    terms: Sequence[str],
    rules: Mapping[str, Any],
    *,
    expand_synonyms: bool = True,
) -> list[str]:
    matches: list[str] = []
    for term in terms:
        if _matches_any(haystack, _term_alternates(term, rules) if expand_synonyms else [term]):
            matches.append(str(term))
    return matches


def _matched_required_all(
    haystack: str,
    terms: Sequence[str],
    rules: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    matches: list[str] = []
    missing: list[str] = []
    for term in terms:
        if _matches_any(haystack, _term_alternates(term, rules)):
            matches.append(str(term))
        else:
            missing.append(str(term))
    return matches, missing


def _matched_plain_values(haystack: str, values: Sequence[str]) -> list[str]:
    return [str(value) for value in values if _contains_normalized(haystack, value)]


def _matched_synonym_groups(haystack: str, groups: Sequence[Sequence[str]]) -> list[str]:
    matches: list[str] = []
    for index, group in enumerate(groups):
        if _matches_any(haystack, group):
            matches.append(f"group:{index}")
    return matches


def _term_alternates(term: str, rules: Mapping[str, Any]) -> list[str]:
    normalized_term = _normalize_search_text(term)
    alternates = [str(term)]
    seen = {normalized_term}
    for group in rules.get("synonym_groups") or []:
        if not isinstance(group, Sequence) or isinstance(group, (str, bytes)):
            continue
        normalized_group = [_normalize_search_text(value) for value in group]
        if normalized_term not in normalized_group:
            continue
        for value in group:
            key = _normalize_search_text(value)
            if key and key not in seen:
                seen.add(key)
                alternates.append(str(value))
    return alternates


def _matches_any(haystack: str, values: Sequence[Any]) -> bool:
    return any(_contains_normalized(haystack, value) for value in values)


def _contains_normalized(haystack: str, needle: Any) -> bool:
    normalized = _normalize_search_text(needle)
    return bool(normalized and normalized in haystack)


def _normalize_search_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return _SPACE_RE.sub(" ", text).strip()


def _dedupe(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))
