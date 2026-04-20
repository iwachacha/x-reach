# -*- coding: utf-8 -*-
"""Tests for batch execution pacing and throttle guards."""

from __future__ import annotations

import json
import threading

import pytest

from x_reach.batch import BatchPlanError, run_batch_plan, validate_batch_plan
from x_reach.results import build_error, build_result


def _write_plan(path, inputs):
    path.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "channel": "twitter",
                        "operation": "search",
                        "input": value,
                        "limit": 1,
                    }
                    for value in inputs
                ]
            }
        ),
        encoding="utf-8",
    )


class _FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []
        self._lock = threading.Lock()

    def now(self) -> float:
        with self._lock:
            return self.value

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self.sleeps.append(seconds)
            self.value += seconds


def _ok_result(channel, operation, value, kwargs):
    return build_result(
        ok=True,
        channel=channel,
        operation=operation,
        items=[],
        raw={"value": value, "kwargs": kwargs},
        meta={
            "input": value,
            "requested_limit": kwargs.get("limit"),
            "quality_profile": kwargs.get("quality_profile"),
        },
        error=None,
    )


def _throttle_error_result(channel, operation, value):
    return build_result(
        ok=False,
        channel=channel,
        operation=operation,
        items=[],
        raw="Twitter API error (HTTP 409): conflict",
        meta={"input": value, "requested_limit": 1, "quality_profile": "balanced"},
        error=build_error(
            code="http_409",
            message="Twitter API error (HTTP 409): conflict",
            details={"http_status": 409},
        ),
    )


def test_batch_validate_normalizes_pacing_from_plan(tmp_path):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "pacing": {
                    "query_delay_seconds": 1.5,
                    "query_jitter_seconds": 0.25,
                    "throttle_cooldown_seconds": 10,
                    "throttle_error_limit": 2,
                },
                "queries": [
                    {"channel": "twitter", "operation": "search", "input": "OpenAI", "limit": 1}
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = validate_batch_plan(plan_path)

    assert payload["pacing"]["query_delay_seconds"] == 1.5
    assert payload["pacing"]["query_jitter_seconds"] == 0.25
    assert payload["pacing"]["throttle_cooldown_seconds"] == 10.0
    assert payload["pacing"]["throttle_error_limit"] == 2


def test_batch_rejects_invalid_pacing(tmp_path):
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path, ["OpenAI"])

    with pytest.raises(BatchPlanError, match="query_delay_seconds"):
        validate_batch_plan(plan_path, query_delay_seconds=-1)


def test_batch_user_posts_allows_metric_filters_and_topic_fit(tmp_path):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "channel": "twitter",
                        "operation": "user_posts",
                        "input": "OpenAI",
                        "limit": 2,
                        "min_likes": 10,
                        "min_retweets": 5,
                        "min_views": 1000,
                        "topic_fit": {"required_any_terms": ["codex"]},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = validate_batch_plan(plan_path)

    assert payload["valid"] is True
    assert payload["summary"]["operation_counts"] == {"user_posts": 1}


def test_batch_user_posts_still_rejects_search_only_options(tmp_path):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "channel": "twitter",
                        "operation": "user_posts",
                        "input": "OpenAI",
                        "search_type": "latest",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(BatchPlanError, match="search_type is not supported"):
        validate_batch_plan(plan_path)


def test_batch_execution_passes_user_posts_topic_fit(tmp_path):
    plan_path = tmp_path / "plan.json"
    save_path = tmp_path / "ledger.jsonl"
    plan_path.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "channel": "twitter",
                        "operation": "user_posts",
                        "input": "OpenAI",
                        "limit": 2,
                        "topic_fit": {"required_any_terms": ["codex"]},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    calls = []

    class _FakeClient:
        def collect(self, channel, operation, value, **kwargs):
            calls.append({"channel": channel, "operation": operation, "value": value, "kwargs": kwargs})
            return _ok_result(channel, operation, value, kwargs)

    payload, exit_code = run_batch_plan(
        plan_path,
        save_path=save_path,
        client_factory=_FakeClient,
    )

    assert exit_code == 0
    assert payload["summary"]["ok"] == 1
    assert calls[0]["kwargs"]["topic_fit"] == {"required_any_terms": ["codex"]}


def test_batch_query_delay_records_planned_waits_with_concurrency(tmp_path):
    plan_path = tmp_path / "plan.json"
    save_path = tmp_path / "ledger.jsonl"
    _write_plan(plan_path, ["q1", "q2", "q3"])

    class _FakeClient:
        def collect(self, channel, operation, value, **kwargs):
            return _ok_result(channel, operation, value, kwargs)

    payload, exit_code = run_batch_plan(
        plan_path,
        save_path=save_path,
        concurrency=3,
        query_delay_seconds=1,
        throttle_error_limit=0,
        client_factory=_FakeClient,
        _sleep_func=lambda _seconds: None,
        _time_func=lambda: 0.0,
        _random_func=lambda: 0.0,
    )

    assert exit_code == 0
    planned_waits = sorted(query["planned_wait_seconds"] for query in payload["queries"])
    assert planned_waits == [0.0, 1.0, 2.0]
    assert payload["pacing"]["query_delay_seconds"] == 1.0


def test_batch_throttle_sensitive_error_applies_cooldown(tmp_path):
    plan_path = tmp_path / "plan.json"
    save_path = tmp_path / "ledger.jsonl"
    _write_plan(plan_path, ["q1", "q2"])
    clock = _FakeClock()
    starts = []

    class _FakeClient:
        def collect(self, channel, operation, value, **kwargs):
            starts.append((value, clock.now()))
            if value == "q1":
                return _throttle_error_result(channel, operation, value)
            return _ok_result(channel, operation, value, kwargs)

    payload, exit_code = run_batch_plan(
        plan_path,
        save_path=save_path,
        concurrency=1,
        throttle_cooldown_seconds=5,
        throttle_error_limit=0,
        client_factory=_FakeClient,
        _sleep_func=clock.sleep,
        _time_func=clock.now,
        _random_func=lambda: 0.0,
    )

    assert exit_code == 0
    assert starts == [("q1", 0.0), ("q2", 5.0)]
    assert payload["queries"][0]["throttle_sensitive"] is True
    assert payload["queries"][1]["applied_wait_seconds"] == 5.0
    assert payload["pacing"]["throttle_sensitive_errors"] == 1
    assert payload["pacing"]["total_wait_seconds"] == 5.0


def test_batch_throttle_error_limit_skips_unstarted_queries(tmp_path):
    plan_path = tmp_path / "plan.json"
    save_path = tmp_path / "ledger.jsonl"
    _write_plan(plan_path, ["q1", "q2", "q3"])
    calls = []

    class _FakeClient:
        def collect(self, channel, operation, value, **kwargs):
            calls.append(value)
            return _throttle_error_result(channel, operation, value)

    payload, exit_code = run_batch_plan(
        plan_path,
        save_path=save_path,
        concurrency=1,
        throttle_cooldown_seconds=0,
        throttle_error_limit=1,
        client_factory=_FakeClient,
        _sleep_func=lambda _seconds: None,
        _time_func=lambda: 0.0,
        _random_func=lambda: 0.0,
    )

    assert exit_code == 0
    assert calls == ["q1"]
    assert payload["summary"]["errors"] == 1
    assert payload["summary"]["skipped"] == 2
    assert payload["summary"]["throttle_guard_triggered"] is True
    assert [query.get("reason") for query in payload["queries"][1:]] == [
        "throttle_guard",
        "throttle_guard",
    ]


def test_batch_resume_ignores_pacing_changes(tmp_path):
    plan_path = tmp_path / "plan.json"
    save_path = tmp_path / "ledger.jsonl"
    _write_plan(plan_path, ["OpenAI"])

    class _InitialClient:
        def collect(self, channel, operation, value, **kwargs):
            return _ok_result(channel, operation, value, kwargs)

    first_payload, first_exit = run_batch_plan(
        plan_path,
        save_path=save_path,
        client_factory=_InitialClient,
    )
    assert first_exit == 0
    assert first_payload["summary"]["ok"] == 1

    class _FailingClient:
        def collect(self, channel, operation, value, **kwargs):
            raise AssertionError("resume should not replay completed queries")

    resumed_payload, resumed_exit = run_batch_plan(
        plan_path,
        save_path=save_path,
        resume=True,
        query_delay_seconds=99,
        client_factory=_FailingClient,
    )

    assert resumed_exit == 0
    assert resumed_payload["queries"][0]["status"] == "skipped"
    assert resumed_payload["queries"][0]["reason"] == "resume_existing"
