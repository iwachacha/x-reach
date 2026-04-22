# -*- coding: utf-8 -*-
"""Tests for evidence-ledger candidate planning."""

import json

import pytest

from x_reach.candidates import (
    CandidatePlanError,
    build_candidates_payload,
    render_candidates_text,
)
from x_reach.evidence_scoring import (
    SCORING_RUBRIC_VERSION,
    quality_reason_counts,
    score_candidate,
)
from x_reach.ledger import build_ledger_record
from x_reach.results import build_item, build_result


def _result(channel="web", operation="read", items=None, input_value="query", meta=None):
    return build_result(
        ok=True,
        channel=channel,
        operation=operation,
        items=items or [],
        raw={"ok": True},
        meta={"input": input_value, **(meta or {})},
        error=None,
    )


def _item(item_id, url, title, source="web"):
    return build_item(
        item_id=item_id,
        kind="page",
        title=title,
        url=url,
        text=None,
        author=None,
        published_at=None,
        source=source,
    )


def _post(item_id, text, *, author="alice", likes=0, media_references=None, extras=None):
    return build_item(
        item_id=item_id,
        kind="post",
        title=text,
        url=f"https://x.com/{author}/status/{item_id}",
        text=text,
        author=author,
        published_at=None,
        source="twitter",
        extras={"timeline_item_kind": "original", **(extras or {})},
        engagement={"likes": likes} if likes else None,
        media_references=media_references,
    )


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def test_candidates_dedupe_by_canonical_url(tmp_path):
    path = tmp_path / "evidence.jsonl"
    first = _result(
        channel="exa_search",
        operation="search",
        items=[_item("exa-1", "HTTPS://Example.com/post/#section", "First", source="exa_search")],
    )
    second = _result(
        channel="web",
        operation="read",
        items=[_item("web-1", "https://example.com/post", "Second", source="web")],
    )
    _write_jsonl(
        path,
        [
            build_ledger_record(first, run_id="run-1", input_value="topic"),
            build_ledger_record(second, run_id="run-1", input_value="https://example.com/post"),
        ],
    )

    payload = build_candidates_payload(path, by="url", limit=20)

    assert payload["summary"]["candidate_count"] == 1
    assert payload["candidates"][0]["title"] == "First"
    assert payload["candidates"][0]["extras"]["seen_in"] == [
        {
            "run_id": "run-1",
            "channel": "exa_search",
            "operation": "search",
            "input": "topic",
            "item_id": "exa-1",
            "url": "HTTPS://Example.com/post/#section",
        },
        {
            "run_id": "run-1",
            "channel": "web",
            "operation": "read",
            "input": "https://example.com/post",
            "item_id": "web-1",
            "url": "https://example.com/post",
        },
    ]


def test_candidates_fallback_dedupe_by_source_and_id(tmp_path):
    path = tmp_path / "evidence.jsonl"
    first = _result(
        channel="github",
        operation="read",
        items=[_item("openai/openai-python", None, "OpenAI Python", source="github")],
    )
    second = _result(
        channel="github",
        operation="read",
        items=[_item("openai/openai-python", None, "Duplicate", source="github")],
    )
    third = _result(
        channel="rss",
        operation="read",
        items=[_item("openai/openai-python", None, "Different source", source="rss")],
    )
    _write_jsonl(
        path,
        [
            build_ledger_record(first, run_id="run-1"),
            build_ledger_record(second, run_id="run-2"),
            build_ledger_record(third, run_id="run-3"),
        ],
    )

    payload = build_candidates_payload(path, by="url", limit=20)

    assert payload["summary"]["candidate_count"] == 2
    assert payload["candidates"][0]["title"] == "OpenAI Python"
    assert len(payload["candidates"][0]["extras"]["seen_in"]) == 2
    assert payload["candidates"][1]["title"] == "Different source"


def test_candidates_limit_keeps_first_seen_order(tmp_path):
    path = tmp_path / "evidence.jsonl"
    result = _result(
        items=[
            _item("1", "https://example.com/1", "One"),
            _item("2", "https://example.com/2", "Two"),
            _item("3", "https://example.com/3", "Three"),
        ],
    )
    _write_jsonl(path, [build_ledger_record(result, run_id="run-1")])

    payload = build_candidates_payload(path, by="url", limit=2)

    assert payload["summary"]["candidate_count"] == 3
    assert payload["summary"]["returned"] == 2
    assert payload["sort_by"] == "first_seen"
    assert [candidate["title"] for candidate in payload["candidates"]] == ["One", "Two"]
    assert "Sort: first_seen" in render_candidates_text(payload)


def test_candidates_expose_quality_scores_without_reordering(tmp_path):
    path = tmp_path / "evidence.jsonl"
    thin = build_item(
        item_id="thin",
        kind="post",
        title="OpenAI Codex launches:",
        url="https://x.com/example/status/1",
        text="OpenAI Codex launches:",
        author="example",
        published_at=None,
        source="twitter",
        extras={"timeline_item_kind": "quote"},
        engagement={"likes": 500_000, "retweets": 20_000, "views": 2_000_000},
    )
    detailed = build_item(
        item_id="detail",
        kind="post",
        title="OpenAI Codex rollout notes",
        url="https://x.com/example/status/2",
        text=(
            "OpenAI Codex eval on 2026-04-10 reduced review time by 37% for "
            "12 maintainers after the v2.1 rollout."
        ),
        author="example",
        published_at=None,
        source="twitter",
        extras={"timeline_item_kind": "original"},
        engagement={"likes": 3},
    )
    result = _result(
        channel="twitter",
        operation="search",
        items=[thin, detailed],
        input_value="OpenAI Codex",
        meta={"query_tokens": ["openai", "codex"]},
    )
    _write_jsonl(path, [build_ledger_record(result, run_id="run-1")])

    payload = build_candidates_payload(path, by="post", limit=20)

    assert payload["sort_by"] == "first_seen"
    assert [candidate["id"] for candidate in payload["candidates"]] == ["thin", "detail"]
    by_id = {candidate["id"]: candidate for candidate in payload["candidates"]}
    assert by_id["detail"]["quality_score"] > by_id["thin"]["quality_score"]
    assert "engagement_capped" in by_id["thin"]["quality_reasons"]
    assert "thin_quote" in by_id["thin"]["quality_reasons"]
    assert "concrete_detail" in by_id["detail"]["quality_reasons"]
    assert "strong_query_match" in by_id["detail"]["quality_reasons"]
    assert payload["summary"]["quality_reason_counts"]["strong_query_match"] == 2

    projected = build_candidates_payload(path, by="post", limit=20, fields="id,quality_score,quality_reasons")
    assert sorted(projected["candidates"][0]) == ["id", "quality_reasons", "quality_score"]


def test_evidence_scoring_v2_emits_principle_aligned_reasons():
    candidate = {
        "id": "rich",
        "title": "OpenAI Codex deployment notes",
        "url": "https://x.com/alice/status/1",
        "text": (
            "OpenAI Codex report: our team deployed v2.1 on 2026-04-10; "
            "logs show p95 latency fell 37% after 12 runs. Screenshot attached."
        ),
        "author": "alice",
        "seen_in_count": 2,
        "engagement": {"likes": 8},
        "media_references": [{"kind": "image", "url": "https://example.com/screenshot.png"}],
        "coverage_topics": [{"topic_id": "codex", "label": "codex"}],
        "topic_fit": {
            "matched": True,
            "match_reasons": ["topic_fit_required_any", "topic_fit_exact_phrase"],
            "score_bonus": 4.0,
        },
        "extras": {
            "timeline_item_kind": "original",
            "query_tokens": ["openai", "codex"],
        },
    }

    score, reasons = score_candidate(candidate)

    assert score > 0
    for reason in {
        "topic_fit_strong",
        "concrete_detail",
        "first_hand_signal",
        "observable_signal",
        "evidence_dense",
        "novel_signal",
    }:
        assert reason in reasons
    counts = quality_reason_counts(
        [
            {"quality_reasons": reasons},
            {"quality_reasons": ["first_hand_signal", "novel_signal"]},
        ]
    )
    assert list(counts) == sorted(counts)
    assert counts["first_hand_signal"] == 2
    assert counts["novel_signal"] == 2


def test_candidates_scoring_v2_reasons_and_counts_are_public(tmp_path):
    path = tmp_path / "evidence.jsonl"
    item = build_item(
        item_id="rich",
        kind="post",
        title="OpenAI Codex deployment notes",
        url="https://x.com/alice/status/1",
        text=(
            "OpenAI Codex report: our team deployed v2.1 on 2026-04-10; "
            "logs show p95 latency fell 37% after 12 runs. Screenshot attached."
        ),
        author="alice",
        published_at=None,
        source="twitter",
        extras={
            "timeline_item_kind": "original",
            "coverage_topics": [{"topic_id": "codex", "label": "codex"}],
        },
        media_references=[{"kind": "image", "url": "https://example.com/screenshot.png"}],
    )
    result = _result(
        channel="twitter",
        operation="search",
        items=[item],
        input_value="OpenAI Codex",
        meta={"query_tokens": ["openai", "codex"]},
    )
    _write_jsonl(path, [build_ledger_record(result, run_id="run-1")])

    payload = build_candidates_payload(
        path,
        by="post",
        limit=20,
        topic_fit={
            "required_any_terms": ["codex"],
            "exact_phrases": ["OpenAI Codex"],
        },
        fields="id,quality_score,quality_reasons,coverage_topics",
    )

    candidate = payload["candidates"][0]
    assert sorted(candidate) == ["coverage_topics", "id", "quality_reasons", "quality_score"]
    assert candidate["coverage_topics"] == [{"topic_id": "codex", "label": "codex"}]
    for reason in {
        "topic_fit_strong",
        "concrete_detail",
        "first_hand_signal",
        "observable_signal",
        "evidence_dense",
        "novel_signal",
    }:
        assert reason in candidate["quality_reasons"]
        assert payload["summary"]["quality_reason_counts"][reason] == 1
    diagnostics = payload["summary"]["quality_diagnostics"]
    assert diagnostics["scoring_version"] == SCORING_RUBRIC_VERSION
    assert diagnostics["scored_candidates"] == 1
    assert diagnostics["reason_counts"] == payload["summary"]["quality_reason_counts"]
    assert diagnostics["negative_reason_counts"] == {}
    assert diagnostics["downrank_reason_counts"] == {}
    assert diagnostics["downrank_samples"] == []


def test_candidates_can_sort_by_quality_score_with_stable_ties(tmp_path):
    path = tmp_path / "evidence.jsonl"
    thin = build_item(
        item_id="thin",
        kind="post",
        title="OpenAI Codex launches:",
        url="https://x.com/example/status/1",
        text="OpenAI Codex launches:",
        author="example",
        published_at=None,
        source="twitter",
        extras={"timeline_item_kind": "quote"},
        engagement={"likes": 500_000, "retweets": 20_000, "views": 2_000_000},
    )
    detail_a = build_item(
        item_id="detail-a",
        kind="post",
        title="OpenAI Codex rollout notes",
        url="https://x.com/example/status/2",
        text=(
            "OpenAI Codex eval on 2026-04-10 reduced review time by 37% for "
            "12 maintainers after the v2.1 rollout."
        ),
        author="example",
        published_at=None,
        source="twitter",
        extras={"timeline_item_kind": "original"},
    )
    detail_b = build_item(
        item_id="detail-b",
        kind="post",
        title="OpenAI Codex setup notes",
        url="https://x.com/example/status/3",
        text=(
            "OpenAI Codex setup notes on 2026-04-11 cut triage time by 37% for "
            "12 reviewers after the v2.1 update."
        ),
        author="example",
        published_at=None,
        source="twitter",
        extras={"timeline_item_kind": "original"},
    )
    result = _result(
        channel="twitter",
        operation="search",
        items=[thin, detail_a, detail_b],
        input_value="OpenAI Codex",
        meta={"query_tokens": ["openai", "codex"]},
    )
    _write_jsonl(path, [build_ledger_record(result, run_id="run-1")])

    payload = build_candidates_payload(path, by="post", limit=20, sort_by="quality_score")

    assert payload["sort_by"] == "quality_score"
    assert [candidate["id"] for candidate in payload["candidates"]] == [
        "detail-a",
        "detail-b",
        "thin",
    ]
    assert payload["candidates"][0]["quality_score"] == payload["candidates"][1]["quality_score"]

    projected = build_candidates_payload(
        path,
        by="post",
        limit=2,
        sort_by="quality_score",
        fields="id,quality_score,quality_reasons",
    )
    assert [candidate["id"] for candidate in projected["candidates"]] == ["detail-a", "detail-b"]
    assert sorted(projected["candidates"][0]) == ["id", "quality_reasons", "quality_score"]


def test_candidates_rank_specific_first_hand_post_above_high_engagement_promo_cta(tmp_path):
    path = tmp_path / "evidence.jsonl"
    result = _result(
        channel="twitter",
        operation="search",
        items=[
            _post(
                "promo",
                "OpenAI Codex plugin sale: shop now with coupon code DEV20, order today, link in bio.",
                author="brand",
                likes=500_000,
            ),
            _post(
                "generic",
                "OpenAI Codex workflow now available. Check out our launch and follow for more updates.",
                author="brand",
                likes=50_000,
            ),
            _post(
                "specific",
                (
                    "OpenAI Codex: I tested 12 review runs on 2026-04-10 and measured p95 triage "
                    "time 37% lower after changing the workflow."
                ),
                author="alice",
                likes=2,
            ),
        ],
        input_value="OpenAI Codex",
        meta={"query_tokens": ["openai", "codex"]},
    )
    _write_jsonl(path, [build_ledger_record(result, run_id="run-1")])

    payload = build_candidates_payload(path, by="post", limit=20, sort_by="quality_score")
    by_id = {candidate["id"]: candidate for candidate in payload["candidates"]}

    assert payload["candidates"][0]["id"] == "specific"
    assert by_id["specific"]["quality_score"] > by_id["promo"]["quality_score"]
    assert "first_hand_signal" in by_id["specific"]["quality_reasons"]
    assert "process_evidence" in by_id["specific"]["quality_reasons"]
    assert "concrete_detail" in by_id["specific"]["quality_reasons"]
    for reason in {"promo_language", "commerce_language", "cta_language", "low_evidence_promo"}:
        assert reason in by_id["promo"]["quality_reasons"]
    assert payload["summary"]["quality_diagnostics"]["negative_reason_counts"]["promo_language"] == 1


def test_candidates_media_only_post_does_not_get_observable_boost(tmp_path):
    path = tmp_path / "evidence.jsonl"
    result = _result(
        channel="twitter",
        operation="search",
        items=[
            _post(
                "media-only",
                "OpenAI Codex launch image",
                author="brand",
                likes=100_000,
                media_references=[{"kind": "image", "url": "https://example.com/image.png"}],
            ),
            _post(
                "measured",
                (
                    "OpenAI Codex: we tested 9 repository reviews on 2026-04-11 and measured "
                    "p95 review time 28% lower after changing the setup."
                ),
                author="alice",
                likes=1,
            ),
        ],
        input_value="OpenAI Codex",
        meta={"query_tokens": ["openai", "codex"]},
    )
    _write_jsonl(path, [build_ledger_record(result, run_id="run-1")])

    payload = build_candidates_payload(path, by="post", limit=20, sort_by="quality_score")
    by_id = {candidate["id"]: candidate for candidate in payload["candidates"]}

    assert payload["candidates"][0]["id"] == "measured"
    assert "media" in by_id["media-only"]["quality_reasons"]
    assert "media_only" in by_id["media-only"]["quality_reasons"]
    assert "observable_signal" not in by_id["media-only"]["quality_reasons"]
    assert "observable_signal" in by_id["measured"]["quality_reasons"]


def test_candidates_coverage_topic_only_is_auxiliary_to_evidence_density(tmp_path):
    path = tmp_path / "evidence.jsonl"
    coverage_topic = {"topic_id": "codex", "label": "codex"}
    result = _result(
        channel="twitter",
        operation="search",
        items=[
            _post(
                "coverage-only",
                "OpenAI Codex topic match update",
                author="brand",
                likes=100_000,
                extras={"coverage_topics": [coverage_topic]},
            ),
            _post(
                "field-note",
                (
                    "OpenAI Codex field note: I ran 14 reviews on 2026-04-12, compared before/after "
                    "latency, and changed one workflow step."
                ),
                author="alice",
                likes=2,
            ),
        ],
        input_value="OpenAI Codex",
        meta={"query_tokens": ["openai", "codex"]},
    )
    _write_jsonl(path, [build_ledger_record(result, run_id="run-1")])

    payload = build_candidates_payload(path, by="post", limit=20, sort_by="quality_score")
    by_id = {candidate["id"]: candidate for candidate in payload["candidates"]}

    assert payload["candidates"][0]["id"] == "field-note"
    assert "novel_signal" in by_id["coverage-only"]["quality_reasons"]
    assert "coverage_topic_only" in by_id["coverage-only"]["quality_reasons"]
    assert "weak_evidence_density" in by_id["coverage-only"]["quality_reasons"]
    assert "evidence_dense" not in by_id["coverage-only"]["quality_reasons"]
    assert "evidence_dense" in by_id["field-note"]["quality_reasons"]


def test_evidence_scoring_strengthens_process_measurement_first_hand_signals():
    score, reasons = score_candidate(
        {
            "id": "process",
            "title": "Field recipe note",
            "text": (
                "I brewed 18g with 280ml water, dialed the grind twice, tasted both batches, "
                "and compared the 4 minute result against yesterday."
            ),
            "url": "https://x.com/alice/status/process",
            "extras": {"timeline_item_kind": "original", "query_tokens": ["recipe"]},
        }
    )

    assert score > 0
    for reason in {"first_hand_signal", "process_evidence", "concrete_detail", "comparison_signal"}:
        assert reason in reasons


def test_candidates_downrank_near_duplicate_promo_templates(tmp_path):
    path = tmp_path / "evidence.jsonl"
    result = _result(
        channel="twitter",
        operation="search",
        items=[
            _post(
                "promo-a",
                "OpenAI Codex plugin launch: shop now with coupon code DEV20, order today, link in bio.",
                author="brand",
                likes=200_000,
            ),
            _post(
                "promo-b",
                "OpenAI Codex plugin launch: shop now with coupon code DEV25, order today, link in bio.",
                author="brand",
                likes=150_000,
            ),
            _post(
                "promo-c",
                "OpenAI Codex plugin launch: shop now with coupon code DEV30, order today, link in bio.",
                author="brand",
                likes=100_000,
            ),
            _post(
                "specific-a",
                (
                    "OpenAI Codex plugin: I tested install on 2026-04-10 across 12 repos and "
                    "measured 37% less review time after a workflow change."
                ),
                author="alice",
                likes=3,
            ),
            _post(
                "specific-b",
                (
                    "OpenAI Codex plugin: we measured CLI configuration on 2026-04-11; "
                    "p95 task time fell 18% across 9 runs."
                ),
                author="bob",
                likes=2,
            ),
        ],
        input_value="OpenAI Codex plugin",
        meta={"query_tokens": ["openai", "codex", "plugin"]},
    )
    _write_jsonl(path, [build_ledger_record(result, run_id="run-1")])

    payload = build_candidates_payload(path, by="post", limit=20, sort_by="quality_score")
    top_three_ids = [candidate["id"] for candidate in payload["candidates"][:3]]
    by_id = {candidate["id"]: candidate for candidate in payload["candidates"]}

    assert top_three_ids[:2] == ["specific-a", "specific-b"]
    assert sum(1 for candidate_id in top_three_ids if candidate_id.startswith("promo-")) <= 1
    assert "near_duplicate_downrank" in by_id["promo-b"]["quality_reasons"]
    assert "near_duplicate_downrank" in by_id["promo-c"]["quality_reasons"]
    diagnostics = payload["summary"]["quality_diagnostics"]
    assert diagnostics["downrank_reason_counts"]["near_duplicate_downrank"] == 2
    assert diagnostics["downrank_reason_counts"]["near_duplicate_promo_cluster"] == 2
    assert [sample["id"] for sample in diagnostics["downrank_samples"]] == ["promo-b", "promo-c"]


def test_candidates_reject_unknown_sort_by(tmp_path):
    path = tmp_path / "evidence.jsonl"
    _write_jsonl(path, [build_ledger_record(_result(), run_id="run-1")])

    with pytest.raises(CandidatePlanError):
        build_candidates_payload(path, sort_by="importance")


def test_candidates_invalid_jsonl_reports_error(tmp_path):
    path = tmp_path / "evidence.jsonl"
    path.write_text("{broken\n", encoding="utf-8")

    with pytest.raises(CandidatePlanError):
        build_candidates_payload(path)


def test_candidates_handles_unicode_line_separator_in_record(tmp_path):
    path = tmp_path / "evidence.jsonl"
    item = _item("1", "https://example.com/1", "One")
    item["text"] = "alpha\u2028beta"
    result = _result(items=[item])
    _write_jsonl(path, [build_ledger_record(result, run_id="run-1")])

    payload = build_candidates_payload(path, by="url", limit=20)

    assert payload["summary"]["candidate_count"] == 1
    assert payload["candidates"][0]["text"] == "alpha\u2028beta"


def test_candidates_accept_raw_collection_result_jsonl(tmp_path):
    path = tmp_path / "raw-results.jsonl"
    result = _result(items=[_item("raw-1", "https://example.com/raw", "Raw")])
    _write_jsonl(path, [{"record_type": "other"}, result])

    payload = build_candidates_payload(path, by="url", limit=20)

    assert payload["summary"]["records"] == 2
    assert payload["summary"]["collection_results"] == 1
    assert payload["summary"]["skipped_records"] == 1
    assert payload["candidates"][0]["title"] == "Raw"
    assert payload["candidates"][0]["extras"]["seen_in"][0]["run_id"] is None


def test_candidates_summary_only_omits_candidate_bodies(tmp_path):
    path = tmp_path / "evidence.jsonl"
    result = _result(items=[_item("1", "https://example.com/1", "One")])
    _write_jsonl(path, [build_ledger_record(result, run_id="run-1")])

    payload = build_candidates_payload(path, by="url", limit=20, summary_only=True)

    assert payload["summary_only"] is True
    assert payload["summary"]["candidate_count"] == 1
    assert payload["candidates"] == []


def test_candidates_summary_includes_channel_and_source_role_counts(tmp_path):
    path = tmp_path / "evidence.jsonl"
    exa_result = _result(
        channel="exa_search",
        operation="search",
        items=[_item("exa-1", "https://example.com/post", "Post", source="exa_search")],
        input_value="topic",
    )
    web_result = _result(
        channel="web",
        operation="read",
        items=[_item("web-1", "https://example.com/post", "Post", source="web")],
        input_value="https://example.com/post",
    )
    github_result = _result(
        channel="github",
        operation="read",
        items=[_item("repo-1", None, "Repo", source="github")],
        input_value="owner/repo",
    )
    _write_jsonl(
        path,
        [
            build_ledger_record(
                exa_result,
                run_id="run-1",
                intent="official_docs",
                query_id="q01",
                source_role="article_discovery",
            ),
            build_ledger_record(
                web_result,
                run_id="run-1",
                intent="followup_read",
                query_id="q02",
                source_role="followup_read",
            ),
            build_ledger_record(
                github_result,
                run_id="run-1",
                intent="oss_candidates",
                query_id="q03",
                source_role="repo_discovery",
            ),
        ],
    )

    payload = build_candidates_payload(path, by="url", limit=20, summary_only=True)

    assert payload["summary"]["candidate_count"] == 2
    assert payload["summary"]["channel_counts"] == {
        "exa_search": 1,
        "github": 1,
        "web": 1,
    }
    assert payload["summary"]["source_role_counts"] == {
        "article_discovery": 1,
        "followup_read": 1,
        "repo_discovery": 1,
    }
    assert payload["summary"]["intent_counts"] == {
        "followup_read": 1,
        "official_docs": 1,
        "oss_candidates": 1,
    }


def test_candidates_fields_filter_and_relevance_metadata(tmp_path):
    path = tmp_path / "evidence.jsonl"
    result = _result(items=[_item("1", "https://example.com/1", "One")])
    _write_jsonl(
        path,
        [
            build_ledger_record(
                result,
                run_id="run-1",
                input_value="topic",
                intent="official_docs",
                query_id="q01",
                source_role="web_discovery",
            )
        ],
    )

    payload = build_candidates_payload(
        path,
        by="url",
        limit=20,
        fields="title,url,intent,query_id,source_role",
    )

    assert payload["fields"] == ["title", "url", "intent", "query_id", "source_role"]
    assert payload["candidates"] == [
        {
            "title": "One",
            "url": "https://example.com/1",
            "intent": "official_docs",
            "query_id": "q01",
            "source_role": "web_discovery",
        }
    ]


def test_candidates_unknown_field_reports_error(tmp_path):
    path = tmp_path / "evidence.jsonl"
    _write_jsonl(path, [build_ledger_record(_result(), run_id="run-1")])

    with pytest.raises(CandidatePlanError):
        build_candidates_payload(path, fields="title,nope")


def test_candidates_records_alternate_urls_for_duplicate(tmp_path):
    path = tmp_path / "evidence.jsonl"
    first = _result(
        items=[_item("1", "https://example.com/post/", "One")],
    )
    second = _result(
        items=[_item("2", "https://example.com/post#section", "Two")],
    )
    _write_jsonl(
        path,
        [
            build_ledger_record(first, run_id="run-1"),
            build_ledger_record(second, run_id="run-1"),
        ],
    )

    payload = build_candidates_payload(path, by="url", limit=20)

    assert payload["summary"]["candidate_count"] == 1
    assert payload["candidates"][0]["extras"]["candidate_key"] == "url:https://example.com/post"
    assert payload["candidates"][0]["extras"]["alternate_urls"] == [
        "https://example.com/post#section"
    ]


def test_candidates_supports_x_identifier_dedupe_modes(tmp_path):
    path = tmp_path / "evidence.jsonl"
    twitter_item = build_item(
        item_id="tweet-api-id",
        kind="post",
        title="X Reach",
        url="https://x.com/iwachacha/status/123",
        text=None,
        author="iwachacha",
        published_at=None,
        source="twitter",
        extras={"author_handle": "iwachacha", "post_id": "123", "likes": 10},
        source_item_id="123",
    )
    web_item = _item("web-1", "https://example.com/post#intro", "Post")
    _write_jsonl(
        path,
        [
            build_ledger_record(_result(channel="twitter", operation="tweet", items=[twitter_item]), run_id="run-1"),
            build_ledger_record(_result(channel="web", operation="read", items=[web_item]), run_id="run-1"),
        ],
    )

    by_author = build_candidates_payload(path, by="author", limit=20)
    by_post = build_candidates_payload(path, by="post", limit=20)
    by_domain = build_candidates_payload(path, by="domain", limit=20)
    by_source_item_id = build_candidates_payload(path, by="source_item_id", limit=20)
    by_normalized_url = build_candidates_payload(path, by="normalized_url", limit=20)

    assert by_author["summary"]["candidate_count"] == 1
    assert by_author["candidates"][0]["extras"]["candidate_key"] == "author:twitter:iwachacha"
    assert by_post["summary"]["candidate_count"] == 2
    assert by_post["candidates"][0]["extras"]["candidate_key"] == "post:twitter:123"
    assert by_domain["summary"]["candidate_count"] == 2
    assert by_source_item_id["candidates"][0]["extras"]["candidate_key"] == "source_item_id:twitter:123"
    assert by_source_item_id["candidates"][0]["engagement"] == {"likes": 10}
    assert by_normalized_url["candidates"][1]["extras"]["candidate_key"] == "normalized_url:https://example.com/post"


def test_candidates_can_prefer_original_posts_for_duplicate_keys(tmp_path):
    path = tmp_path / "evidence.jsonl"
    quoted = build_item(
        item_id="quote-1",
        kind="post",
        title="Quote",
        url="https://x.com/openai/status/123",
        text="Quoted OpenAI update",
        author="alice",
        published_at=None,
        source="twitter",
        extras={"timeline_item_kind": "quote"},
    )
    original = build_item(
        item_id="orig-1",
        kind="post",
        title="Original",
        url="https://x.com/openai/status/123",
        text="Original OpenAI update",
        author="openai",
        published_at=None,
        source="twitter",
        extras={"timeline_item_kind": "original"},
    )
    _write_jsonl(
        path,
        [
            build_ledger_record(_result(channel="twitter", operation="search", items=[quoted]), run_id="run-1"),
            build_ledger_record(_result(channel="twitter", operation="search", items=[original]), run_id="run-1"),
        ],
    )

    payload = build_candidates_payload(path, by="url", limit=20, prefer_originals=True)

    assert payload["candidates"][0]["title"] == "Original"
    assert payload["candidates"][0]["author"] == "openai"
    assert len(payload["candidates"][0]["extras"]["seen_in"]) == 2


def test_candidates_can_drop_noise_require_query_match_and_cap_authors(tmp_path):
    path = tmp_path / "evidence.jsonl"
    records = [
        build_ledger_record(
            _result(
                channel="twitter",
                operation="search",
                items=[
                    build_item(
                        item_id="good-1",
                        kind="post",
                        title="Useful",
                        url="https://x.com/alice/status/1",
                        text="OpenAI shipped a useful update",
                        author="alice",
                        published_at=None,
                        source="twitter",
                        extras={"timeline_item_kind": "original"},
                    )
                ],
                input_value="OpenAI",
                meta={"query_tokens": ["openai"]},
            ),
            run_id="run-1",
        ),
        build_ledger_record(
            _result(
                channel="twitter",
                operation="search",
                items=[
                    build_item(
                        item_id="good-2",
                        kind="post",
                        title="Second",
                        url="https://x.com/alice/status/2",
                        text="OpenAI second useful update",
                        author="alice",
                        published_at=None,
                        source="twitter",
                        extras={"timeline_item_kind": "original"},
                    )
                ],
                input_value="OpenAI",
                meta={"query_tokens": ["openai"]},
            ),
            run_id="run-1",
        ),
        build_ledger_record(
            _result(
                channel="twitter",
                operation="search",
                items=[
                    build_item(
                        item_id="spam-1",
                        kind="post",
                        title="Spam",
                        url="https://x.com/spam/status/1",
                        text="OpenAI giveaway whitelist now live",
                        author="spam",
                        published_at=None,
                        source="twitter",
                        extras={"timeline_item_kind": "original"},
                    )
                ],
                input_value="OpenAI",
                meta={"query_tokens": ["openai"]},
            ),
            run_id="run-1",
        ),
        build_ledger_record(
            _result(
                channel="twitter",
                operation="search",
                items=[
                    build_item(
                        item_id="offtopic-1",
                        kind="post",
                        title="Off topic",
                        url="https://x.com/bob/status/1",
                        text="Completely unrelated post",
                        author="bob",
                        published_at=None,
                        source="twitter",
                        extras={"timeline_item_kind": "original"},
                    )
                ],
                input_value="OpenAI",
                meta={"query_tokens": ["openai"]},
            ),
            run_id="run-1",
        ),
    ]
    _write_jsonl(path, records)

    payload = build_candidates_payload(
        path,
        by="url",
        limit=20,
        max_per_author=1,
        drop_noise=True,
        require_query_match=True,
    )

    assert [candidate["id"] for candidate in payload["candidates"]] == ["good-1"]
    assert payload["summary"]["filter_drop_counts"] == {
        "author_cap": 1,
        "promo_phrase": 1,
        "query_miss": 1,
    }


def test_candidates_apply_topic_fit_filtering_and_projection(tmp_path):
    path = tmp_path / "evidence.jsonl"
    result = _result(
        channel="twitter",
        operation="search",
        items=[
            build_item(
                item_id="keep",
                kind="post",
                title="OpenAI Codex CLI notes",
                url="https://x.com/alice/status/1",
                text="OpenAI Codex CLI notes from a practical command line workflow",
                author="alice",
                published_at=None,
                source="twitter",
                extras={"timeline_item_kind": "original"},
            ),
            build_item(
                item_id="synonym",
                kind="post",
                title="OpenAI coding agent notes",
                url="https://x.com/bob/status/2",
                text="OpenAI coding agent workflow for command line review",
                author="bob",
                published_at=None,
                source="twitter",
                extras={"timeline_item_kind": "original"},
            ),
            build_item(
                item_id="negative",
                kind="post",
                title="OpenAI Codex giveaway",
                url="https://x.com/spam/status/3",
                text="OpenAI Codex giveaway airdrop",
                author="spam",
                published_at=None,
                source="twitter",
                extras={"timeline_item_kind": "original"},
            ),
            build_item(
                item_id="miss",
                kind="post",
                title="OpenAI platform news",
                url="https://x.com/carol/status/4",
                text="OpenAI platform news without the declared topic",
                author="carol",
                published_at=None,
                source="twitter",
                extras={"timeline_item_kind": "original"},
            ),
        ],
        input_value="OpenAI",
        meta={"query_tokens": ["openai"]},
    )
    _write_jsonl(path, [build_ledger_record(result, run_id="run-1")])

    payload = build_candidates_payload(
        path,
        by="post",
        limit=20,
        topic_fit={
            "required_any_terms": ["codex"],
            "required_all_terms": ["openai"],
            "preferred_terms": ["cli"],
            "excluded_terms": ["airdrop"],
            "exact_phrases": ["OpenAI Codex"],
            "synonym_groups": [["codex", "coding agent"], ["cli", "command line"]],
        },
        fields="id,quality_score,quality_reasons,topic_fit",
    )

    assert [candidate["id"] for candidate in payload["candidates"]] == ["keep", "synonym"]
    assert payload["topic_fit"]["enabled"] is True
    assert payload["topic_fit"]["query_match_fallback_used"] is False
    assert payload["summary"]["filter_drop_counts"] == {
        "topic_fit_excluded_term": 1,
        "topic_fit_missing_required_any": 1,
    }
    assert payload["summary"]["topic_fit"]["dropped"] == 2
    assert payload["summary"]["topic_fit_reason_counts"]["topic_fit_required_any"] == 2
    assert payload["summary"]["topic_fit_reason_counts"]["topic_fit_synonym_group"] == 2
    assert sorted(payload["candidates"][0]) == ["id", "quality_reasons", "quality_score", "topic_fit"]
    assert "topic_fit_exact_phrase" in payload["candidates"][0]["quality_reasons"]
    assert payload["candidates"][1]["topic_fit"]["matched_terms"]["required_any_terms"] == ["codex"]


def test_candidates_topic_fit_takes_priority_over_query_match_fallback(tmp_path):
    path = tmp_path / "evidence.jsonl"
    result = _result(
        channel="twitter",
        operation="search",
        items=[
            build_item(
                item_id="keep",
                kind="post",
                title="Coding agent workflow",
                url="https://x.com/alice/status/1",
                text="Coding agent workflow from the command line",
                author="alice",
                published_at=None,
                source="twitter",
                extras={"timeline_item_kind": "original"},
            ),
        ],
        input_value="OpenAI",
        meta={"query_tokens": ["openai"]},
    )
    _write_jsonl(path, [build_ledger_record(result, run_id="run-1")])

    payload = build_candidates_payload(
        path,
        by="post",
        limit=20,
        require_query_match=True,
        topic_fit={"required_any_terms": ["coding agent"]},
    )

    assert [candidate["id"] for candidate in payload["candidates"]] == ["keep"]
    assert payload["summary"]["filter_drop_counts"] == {}
    assert payload["summary"]["topic_fit"]["query_match_fallback_used"] is False


def test_candidates_can_drop_low_content_quote_posts(tmp_path):
    path = tmp_path / "evidence.jsonl"
    records = [
        build_ledger_record(
            _result(
                channel="twitter",
                operation="search",
                items=[
                    build_item(
                        item_id="thin-quote",
                        kind="post",
                        title="Build macOS apps with our Codex plugin:",
                        url="https://x.com/alice/status/1",
                        text="Build macOS apps with our Codex plugin:",
                        author="alice",
                        published_at=None,
                        source="twitter",
                        extras={"timeline_item_kind": "quote"},
                    ),
                    build_item(
                        item_id="useful-1",
                        kind="post",
                        title="Codex plugin notes",
                        url="https://x.com/bob/status/2",
                        text="OpenAI Codex plugin helps developers build macOS apps with clear setup notes",
                        author="bob",
                        published_at=None,
                        source="twitter",
                        extras={"timeline_item_kind": "original"},
                    ),
                ],
                input_value="Codex plugin",
                meta={"query_tokens": ["codex", "plugin"]},
            ),
            run_id="run-1",
        )
    ]
    _write_jsonl(path, records)

    payload = build_candidates_payload(path, by="post", limit=20, drop_noise=True)

    assert [candidate["id"] for candidate in payload["candidates"]] == ["useful-1"]
    assert payload["summary"]["filter_drop_counts"] == {"low_content": 1}


def test_candidates_can_require_multiple_sightings(tmp_path):
    path = tmp_path / "evidence.jsonl"
    repeated_url = "https://x.com/alice/status/1"
    records = [
        build_ledger_record(
            _result(
                channel="twitter",
                operation="search",
                items=[
                    build_item(
                        item_id="repeat-1",
                        kind="post",
                        title="Repeated lead",
                        url=repeated_url,
                        text="A repeated high-signal post",
                        author="alice",
                        published_at=None,
                        source="twitter",
                        extras={"timeline_item_kind": "original"},
                    )
                ],
                input_value="MCP AI",
                meta={"query_tokens": ["mcp", "ai"]},
            ),
            run_id="run-1",
        ),
        build_ledger_record(
            _result(
                channel="twitter",
                operation="search",
                items=[
                    build_item(
                        item_id="repeat-2",
                        kind="post",
                        title="Repeated lead duplicate",
                        url=repeated_url,
                        text="The same post surfaced again",
                        author="alice",
                        published_at=None,
                        source="twitter",
                        extras={"timeline_item_kind": "original"},
                    )
                ],
                input_value="Model Context Protocol",
                meta={"query_tokens": ["model", "context", "protocol"]},
            ),
            run_id="run-2",
        ),
        build_ledger_record(
            _result(
                channel="twitter",
                operation="search",
                items=[
                    build_item(
                        item_id="single-1",
                        kind="post",
                        title="Singleton",
                        url="https://x.com/bob/status/2",
                        text="Only seen once",
                        author="bob",
                        published_at=None,
                        source="twitter",
                        extras={"timeline_item_kind": "original"},
                    )
                ],
                input_value="MCP AI",
                meta={"query_tokens": ["mcp", "ai"]},
            ),
            run_id="run-1",
        ),
    ]
    _write_jsonl(path, records)

    payload = build_candidates_payload(path, by="url", limit=20, min_seen_in=2)

    assert [candidate["id"] for candidate in payload["candidates"]] == ["repeat-1"]
    assert payload["candidates"][0]["seen_in_count"] == 2
    assert len(payload["candidates"][0]["extras"]["seen_in"]) == 2
    assert payload["summary"]["candidate_count"] == 2
    assert payload["summary"]["multi_seen_candidates"] == 1
    assert payload["summary"]["max_seen_in"] == 2
    assert payload["summary"]["filter_drop_counts"] == {"seen_in": 1}


def test_candidates_can_drop_exact_title_duplicates_across_authors(tmp_path):
    path = tmp_path / "evidence.jsonl"
    duplicate_title = "Anthropic just introduced the Claude Architect Certification — and it’s not easy"
    records = [
        build_ledger_record(
            _result(
                channel="twitter",
                operation="search",
                items=[
                    build_item(
                        item_id="lead",
                        kind="post",
                        title=duplicate_title,
                        url="https://x.com/alice/status/1",
                        text="Detailed thread about the certification",
                        author="alice",
                        published_at=None,
                        source="twitter",
                        extras={"timeline_item_kind": "original"},
                    )
                ],
                input_value="Claude MCP",
                meta={"query_tokens": ["claude", "mcp"]},
            ),
            run_id="run-1",
        ),
        build_ledger_record(
            _result(
                channel="twitter",
                operation="search",
                items=[
                    build_item(
                        item_id="copy-1",
                        kind="post",
                        title=duplicate_title,
                        url="https://x.com/bob/status/2",
                        text="Another account reposted the same headline",
                        author="bob",
                        published_at=None,
                        source="twitter",
                        extras={"timeline_item_kind": "original"},
                    )
                ],
                input_value="Claude MCP",
                meta={"query_tokens": ["claude", "mcp"]},
            ),
            run_id="run-1",
        ),
        build_ledger_record(
            _result(
                channel="twitter",
                operation="search",
                items=[
                    build_item(
                        item_id="distinct",
                        kind="post",
                        title="How to use MCP with Claude Code in practice",
                        url="https://x.com/carol/status/3",
                        text="A distinct post should remain",
                        author="carol",
                        published_at=None,
                        source="twitter",
                        extras={"timeline_item_kind": "original"},
                    )
                ],
                input_value="Claude MCP",
                meta={"query_tokens": ["claude", "mcp"]},
            ),
            run_id="run-1",
        ),
    ]
    _write_jsonl(path, records)

    payload = build_candidates_payload(path, by="post", limit=20, drop_title_duplicates=True)

    assert [candidate["id"] for candidate in payload["candidates"]] == ["lead", "distinct"]
    assert payload["summary"]["filter_drop_counts"] == {"title_duplicate": 1}

