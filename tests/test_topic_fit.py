# -*- coding: utf-8 -*-
"""Tests for deterministic caller-declared topic-fit rules."""

from x_reach.topic_fit import (
    TOPIC_FIT_DROP_EXCLUDED_TERM,
    TOPIC_FIT_DROP_MISSING_REQUIRED_ALL,
    TOPIC_FIT_DROP_MISSING_REQUIRED_ANY,
    TOPIC_FIT_DROP_NEGATIVE_PHRASE,
    TOPIC_FIT_MATCH_EXACT_PHRASE,
    TOPIC_FIT_MATCH_PREFERRED,
    TOPIC_FIT_MATCH_REQUIRED_ALL,
    TOPIC_FIT_MATCH_REQUIRED_ANY,
    TOPIC_FIT_MATCH_SYNONYM_GROUP,
    evaluate_topic_fit,
)


def test_required_any_passes_when_one_term_matches():
    result = evaluate_topic_fit(
        ["OpenAI Codex shipped a CLI update"],
        {"required_any_terms": ["codex", "chatgpt"]},
    )

    assert result["matched"] is True
    assert result["drop_reasons"] == []
    assert result["matched_terms"]["required_any_terms"] == ["codex"]
    assert TOPIC_FIT_MATCH_REQUIRED_ANY in result["match_reasons"]


def test_required_any_drops_when_all_terms_miss():
    result = evaluate_topic_fit(
        ["Completely unrelated post"],
        {"required_any_terms": ["codex", "coding agent"]},
    )

    assert result["matched"] is False
    assert result["drop_reasons"] == [TOPIC_FIT_DROP_MISSING_REQUIRED_ANY]
    assert result["missing_required"]["required_any_terms"] == ["codex", "coding agent"]


def test_required_all_drops_when_one_term_is_missing():
    result = evaluate_topic_fit(
        ["OpenAI platform update"],
        {"required_all_terms": ["openai", "codex"]},
    )

    assert result["matched"] is False
    assert result["drop_reasons"] == [TOPIC_FIT_DROP_MISSING_REQUIRED_ALL]
    assert result["matched_terms"]["required_all_terms"] == ["openai"]
    assert result["missing_required"]["required_all_terms"] == ["codex"]


def test_excluded_terms_and_negative_phrases_drop():
    excluded = evaluate_topic_fit(
        ["OpenAI Codex airdrop giveaway"],
        {"excluded_terms": ["giveaway"]},
    )
    negative = evaluate_topic_fit(
        ["This is not about codex"],
        {"negative_phrases": ["not about codex"]},
    )

    assert excluded["matched"] is False
    assert excluded["drop_reasons"] == [TOPIC_FIT_DROP_EXCLUDED_TERM]
    assert negative["matched"] is False
    assert negative["drop_reasons"] == [TOPIC_FIT_DROP_NEGATIVE_PHRASE]


def test_exact_phrases_become_positive_reasons():
    result = evaluate_topic_fit(
        ["Hands-on notes for OpenAI Codex in the SDK"],
        {"exact_phrases": ["OpenAI Codex"]},
    )

    assert result["matched"] is True
    assert result["matched_terms"]["exact_phrases"] == ["OpenAI Codex"]
    assert TOPIC_FIT_MATCH_EXACT_PHRASE in result["match_reasons"]
    assert result["score_bonus"] > 0


def test_synonym_groups_satisfy_required_and_preferred_terms():
    result = evaluate_topic_fit(
        ["The AI coding assistant now works from the command line"],
        {
            "required_any_terms": ["codex"],
            "preferred_terms": ["cli"],
            "synonym_groups": [
                ["codex", "coding agent", "ai coding assistant"],
                ["cli", "command line"],
            ],
        },
    )

    assert result["matched"] is True
    assert result["matched_terms"]["required_any_terms"] == ["codex"]
    assert result["matched_terms"]["preferred_terms"] == ["cli"]
    assert result["matched_terms"]["synonym_groups"] == ["group:0", "group:1"]
    assert TOPIC_FIT_MATCH_REQUIRED_ANY in result["match_reasons"]
    assert TOPIC_FIT_MATCH_PREFERRED in result["match_reasons"]
    assert TOPIC_FIT_MATCH_SYNONYM_GROUP in result["match_reasons"]


def test_japanese_substring_and_phrase_match():
    result = evaluate_topic_fit(
        ["東京の開発者がOpenAI Codex CLIの使い勝手を詳しく共有"],
        {
            "required_all_terms": ["開発者", "使い勝手"],
            "exact_phrases": ["OpenAI Codex CLI"],
        },
    )

    assert result["matched"] is True
    assert result["matched_terms"]["required_all_terms"] == ["開発者", "使い勝手"]
    assert TOPIC_FIT_MATCH_REQUIRED_ALL in result["match_reasons"]
    assert TOPIC_FIT_MATCH_EXACT_PHRASE in result["match_reasons"]


def test_empty_rules_are_noop():
    result = evaluate_topic_fit(["anything"], {})

    assert result == {
        "enabled": False,
        "matched": True,
        "drop_reasons": [],
        "match_reasons": [],
        "matched_terms": {},
        "missing_required": {},
        "score_bonus": 0.0,
    }
