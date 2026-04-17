# -*- coding: utf-8 -*-
"""Batch collection runner for research plans."""

from __future__ import annotations

import json
import math
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from x_reach import __version__
from x_reach.client import AgentReachClient
from x_reach.high_signal import is_broad_operation
from x_reach.ledger import (
    default_run_id,
    iter_ledger_records,
    save_collection_result,
    save_collection_result_sharded,
)
from x_reach.operation_contracts import (
    OperationContractError,
    batch_option_values,
    validate_operation_options,
)
from x_reach.schemas import SCHEMA_VERSION, utc_timestamp


class BatchPlanError(Exception):
    """Raised when a batch plan cannot be executed."""


_DEFAULT_PACING = {
    "query_delay_seconds": 0.0,
    "query_jitter_seconds": 0.0,
    "throttle_cooldown_seconds": 30.0,
    "throttle_error_limit": 3,
}


def normalize_pacing_config(
    raw_pacing: Any = None,
    *,
    query_delay_seconds: float | None = None,
    query_jitter_seconds: float | None = None,
    throttle_cooldown_seconds: float | None = None,
    throttle_error_limit: int | None = None,
) -> dict[str, Any]:
    """Normalize explicit batch/mission pacing controls."""

    if raw_pacing is None:
        pacing: dict[str, Any] = {}
    elif isinstance(raw_pacing, dict):
        pacing = raw_pacing
    else:
        raise BatchPlanError("pacing must be a JSON object")

    config = dict(_DEFAULT_PACING)
    raw_values = {
        "query_delay_seconds": _first_present(
            pacing,
            "query_delay_seconds",
            "query_delay",
        ),
        "query_jitter_seconds": _first_present(
            pacing,
            "query_jitter_seconds",
            "query_jitter",
        ),
        "throttle_cooldown_seconds": _first_present(
            pacing,
            "throttle_cooldown_seconds",
            "throttle_cooldown",
        ),
        "throttle_error_limit": _first_present(pacing, "throttle_error_limit"),
    }
    for key, value in raw_values.items():
        if value is not None:
            config[key] = value

    overrides = {
        "query_delay_seconds": query_delay_seconds,
        "query_jitter_seconds": query_jitter_seconds,
        "throttle_cooldown_seconds": throttle_cooldown_seconds,
        "throttle_error_limit": throttle_error_limit,
    }
    for key, value in overrides.items():
        if value is not None:
            config[key] = value

    return {
        "query_delay_seconds": _nonnegative_float(
            config["query_delay_seconds"],
            "pacing.query_delay_seconds",
        ),
        "query_jitter_seconds": _nonnegative_float(
            config["query_jitter_seconds"],
            "pacing.query_jitter_seconds",
        ),
        "throttle_cooldown_seconds": _nonnegative_float(
            config["throttle_cooldown_seconds"],
            "pacing.throttle_cooldown_seconds",
        ),
        "throttle_error_limit": _nonnegative_int(
            config["throttle_error_limit"],
            "pacing.throttle_error_limit",
        ),
    }


def validate_batch_plan(
    plan_path: str | Path,
    *,
    quality: str | None = None,
    query_delay_seconds: float | None = None,
    query_jitter_seconds: float | None = None,
    throttle_cooldown_seconds: float | None = None,
    throttle_error_limit: int | None = None,
) -> dict[str, Any]:
    """Validate a JSON batch plan without collecting or writing ledger data."""

    path, _plan, normalized_queries, failure_policy, requested_quality, pacing_config = _prepare_batch_plan(
        plan_path,
        quality=quality,
        query_delay_seconds=query_delay_seconds,
        query_jitter_seconds=query_jitter_seconds,
        throttle_cooldown_seconds=throttle_cooldown_seconds,
        throttle_error_limit=throttle_error_limit,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "command": "batch",
        "cli_version": __version__,
        "validate_only": True,
        "valid": True,
        "plan": str(path),
        "failure_policy": failure_policy,
        "quality_profile": requested_quality,
        "pacing": _pacing_payload(pacing_config, []),
        "summary": _plan_summary(normalized_queries),
    }


def run_batch_plan(
    plan_path: str | Path,
    *,
    save_path: str | Path | None = None,
    save_dir: str | Path | None = None,
    shard_by: str = "channel",
    concurrency: int = 1,
    resume: bool = False,
    checkpoint_every: int = 100,
    quality: str | None = None,
    query_delay_seconds: float | None = None,
    query_jitter_seconds: float | None = None,
    throttle_cooldown_seconds: float | None = None,
    throttle_error_limit: int | None = None,
    client_factory: Callable[[], AgentReachClient] | None = None,
    _sleep_func: Callable[[float], None] | None = None,
    _time_func: Callable[[], float] | None = None,
    _random_func: Callable[[], float] | None = None,
) -> tuple[dict[str, Any], int]:
    """Run a JSON research plan and append results to a ledger."""

    if bool(save_path) == bool(save_dir):
        raise BatchPlanError("Provide exactly one of save_path or save_dir")
    if concurrency < 1:
        raise BatchPlanError("concurrency must be greater than or equal to 1")
    if checkpoint_every < 1:
        raise BatchPlanError("checkpoint-every must be greater than or equal to 1")
    if save_dir is not None:
        save_dir_path = Path(save_dir)
        if save_dir_path.exists() and not save_dir_path.is_dir():
            raise BatchPlanError("save_dir must point to a directory")

    path, plan, normalized_queries, failure_policy, requested_quality, pacing_config = _prepare_batch_plan(
        plan_path,
        quality=quality,
        query_delay_seconds=query_delay_seconds,
        query_jitter_seconds=query_jitter_seconds,
        throttle_cooldown_seconds=throttle_cooldown_seconds,
        throttle_error_limit=throttle_error_limit,
    )
    run_id = str(plan.get("run_id") or default_run_id())
    save_target = save_dir or save_path
    completed_keys = _completed_query_keys(save_target) if resume and save_target is not None else set()
    statuses: list[dict[str, Any] | None] = [None] * len(normalized_queries)
    checkpoints: list[dict[str, Any]] = []
    written_targets: set[str] = set()
    started_at = utc_timestamp()
    make_client = client_factory or AgentReachClient
    pacing = _PacingController(
        pacing_config,
        sleep_func=_sleep_func or time.sleep,
        time_func=_time_func or time.monotonic,
        random_func=_random_func or random.random,
    )

    def execute(index: int, query: dict[str, Any]) -> dict[str, Any]:
        base_status = _query_status_base(query, requested_quality=requested_quality)
        resume_query = {
            **query,
            "quality_profile": requested_quality if is_broad_operation(query["operation"]) else None,
        }
        key = _query_key(resume_query)
        if resume and key in completed_keys:
            return {
                **base_status,
                "status": "skipped",
                "reason": "resume_existing",
                "ok": True,
                "count": 0,
                **_empty_execution_diagnostics(),
            }

        start_wait = pacing.wait_for_start()
        if start_wait["skipped"]:
            return {
                **base_status,
                "status": "skipped",
                "reason": "throttle_guard",
                "ok": True,
                "count": 0,
                **_empty_execution_diagnostics(start_wait),
            }

        client = make_client()
        kwargs: dict[str, Any] = {}
        if query.get("limit") is not None:
            kwargs["limit"] = int(query["limit"])
        for option_name in (
            "since",
            "until",
            "from_user",
            "to_user",
            "lang",
            "search_type",
            "has",
            "exclude",
            "min_likes",
            "min_retweets",
            "min_views",
            "originals_only",
            "raw_mode",
            "raw_max_bytes",
            "item_text_mode",
            "item_text_max_chars",
        ):
            if query.get(option_name) is not None:
                kwargs[option_name] = query[option_name]
        if requested_quality is not None and is_broad_operation(query["operation"]):
            kwargs["quality_profile"] = requested_quality
        started_at_query = utc_timestamp()
        started_monotonic = pacing.now()
        payload = client.collect(query["channel"], query["operation"], query["input"], **kwargs)
        finished_monotonic = pacing.now()
        finished_at_query = utc_timestamp()
        error = payload.get("error")
        error_category = error.get("category") if isinstance(error, dict) else None
        retryable = error.get("retryable") if isinstance(error, dict) else None
        throttle_sensitive = _is_throttle_sensitive_error(error, payload=payload)
        throttle_diagnostics = pacing.record_result(throttle_sensitive)
        return {
            "_payload": payload,
            "_query": query,
            **base_status,
            "status": "ok" if payload.get("ok") else "error",
            "ok": bool(payload.get("ok")),
            "count": len(payload.get("items") or []),
            "urls": [item.get("url") for item in payload.get("items") or [] if item.get("url")],
            "error_code": error["code"] if isinstance(error, dict) else None,
            "error_category": error_category,
            "error_retryable": retryable,
            "error_message": error["message"] if isinstance(error, dict) else None,
            "started_at": started_at_query,
            "finished_at": finished_at_query,
            "duration_seconds": _round_seconds(finished_monotonic - started_monotonic),
            "planned_wait_seconds": start_wait["planned_wait_seconds"],
            "applied_wait_seconds": start_wait["applied_wait_seconds"],
            "throttle_sensitive": throttle_sensitive,
            "throttle_cooldown_applied_seconds": throttle_diagnostics[
                "throttle_cooldown_applied_seconds"
            ],
        }

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(execute, index, query): index
            for index, query in enumerate(normalized_queries)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                status = future.result()
            except Exception as exc:
                status = {
                    "query_id": f"q{index + 1:02d}",
                    "status": "error",
                    "ok": False,
                    "count": 0,
                    **_empty_execution_diagnostics(),
                    "error_code": "batch_error",
                    "error_category": "unknown",
                    "error_retryable": False,
                    "error_message": str(exc),
                }
            payload = status.pop("_payload", None)
            query = status.pop("_query", None)
            if payload is not None and query is not None:
                try:
                    if save_path is not None:
                        save_collection_result(
                            save_path,
                            payload,
                            run_id=run_id,
                            input_value=query["input"],
                            intent=query.get("intent"),
                            query_id=query["query_id"],
                            source_role=query.get("source_role"),
                        )
                        written_targets.add(str(Path(save_path)))
                    elif save_dir is not None:
                        _record, shard_path = save_collection_result_sharded(
                            save_dir,
                            payload,
                            run_id=run_id,
                            shard_by=shard_by,
                            input_value=query["input"],
                            intent=query.get("intent"),
                            query_id=query["query_id"],
                            source_role=query.get("source_role"),
                        )
                        written_targets.add(str(shard_path))
                except (OSError, TypeError, ValueError) as exc:
                    status.update(
                        {
                            "status": "error",
                            "ok": False,
                            "error_code": "ledger_error",
                            "error_category": "unknown",
                            "error_retryable": False,
                            "error_message": str(exc),
                        }
                    )
            statuses[index] = status
            completed = len([item for item in statuses if item is not None])
            if completed % checkpoint_every == 0:
                checkpoints.append(_checkpoint_summary(statuses, completed=completed))

    final_statuses = [status for status in statuses if status is not None]
    finished_at = utc_timestamp()
    summary = _summary(final_statuses)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": finished_at,
        "command": "batch",
        "cli_version": __version__,
        "plan": str(path),
        "save_mode": "sharded" if save_dir is not None else "file",
        "save": str(save_path) if save_path is not None else None,
        "save_dir": str(save_dir) if save_dir is not None else None,
        "shard_by": shard_by if save_dir is not None else None,
        "save_targets": sorted(written_targets),
        "run_id": run_id,
        "quality_profile": requested_quality,
        "failure_policy": failure_policy,
        "concurrency": concurrency,
        "resume": resume,
        "pacing": _pacing_payload(pacing_config, final_statuses),
        "started_at": started_at,
        "finished_at": finished_at,
        "summary": summary,
        "queries": final_statuses,
        "checkpoints": checkpoints,
    }
    exit_code = 1 if failure_policy == "strict" and summary["errors"] else 0
    return payload, exit_code


def render_batch_text(payload: dict[str, Any]) -> str:
    """Render a batch manifest for humans."""

    summary = payload["summary"]
    if payload.get("validate_only"):
        pacing = payload.get("pacing") or {}
        lines = [
            "X Reach Batch Validation",
            "========================================",
            f"Plan: {payload['plan']}",
            f"Valid: {'yes' if payload.get('valid') else 'no'}",
            f"Failure policy: {payload['failure_policy']}",
            f"Quality profile: {payload['quality_profile']}",
            f"Pacing: {_render_pacing(pacing)}",
            f"Queries: {summary['query_count']}",
        ]
        if summary["channel_counts"]:
            lines.append(f"Channels: {_render_counts(summary['channel_counts'])}")
        if summary["operation_counts"]:
            lines.append(f"Operations: {_render_counts(summary['operation_counts'])}")
        if summary["intent_counts"]:
            lines.append(f"Intents: {_render_counts(summary['intent_counts'])}")
        if summary["source_role_counts"]:
            lines.append(f"Source roles: {_render_counts(summary['source_role_counts'])}")
        return "\n".join(lines)

    lines = [
        "X Reach Batch",
        "========================================",
        f"Plan: {payload['plan']}",
        (
            f"Save dir: {payload['save_dir']} (shard_by={payload['shard_by']})"
            if payload.get("save_mode") == "sharded"
            else f"Save: {payload['save']}"
        ),
        f"Run ID: {payload['run_id']}",
        f"Queries: {summary['total']} total, {summary['ok']} ok, {summary['errors']} errors, {summary['skipped']} skipped",
        f"Items: {summary['items']}",
        f"Pacing: {_render_pacing(payload.get('pacing') or {})}",
    ]
    return "\n".join(lines)


def _load_batch_plan(path: Path) -> dict[str, Any]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise BatchPlanError(f"Could not read batch plan: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BatchPlanError(f"Invalid batch plan JSON: {exc.msg}") from exc
    if not isinstance(plan, dict):
        raise BatchPlanError("batch plan must be a JSON object")
    return plan


def _prepare_batch_plan(
    plan_path: str | Path,
    *,
    quality: str | None = None,
    query_delay_seconds: float | None = None,
    query_jitter_seconds: float | None = None,
    throttle_cooldown_seconds: float | None = None,
    throttle_error_limit: int | None = None,
) -> tuple[Path, dict[str, Any], list[dict[str, Any]], str, str, dict[str, Any]]:
    path = Path(plan_path)
    plan = _load_batch_plan(path)
    queries = plan.get("queries") or plan.get("pilot_queries") or []
    if not isinstance(queries, list):
        raise BatchPlanError("batch plan queries must be a list")
    metadata_defaults = _plan_metadata_defaults(plan)
    normalized_queries = [
        _normalize_query(
            query,
            index,
            metadata_defaults=metadata_defaults,
            total_queries=len(queries),
        )
        for index, query in enumerate(queries)
    ]
    failure_policy = str(plan.get("failure_policy") or "partial")
    requested_quality = str(quality or plan.get("quality_profile") or "balanced")
    pacing_config = normalize_pacing_config(
        plan.get("pacing"),
        query_delay_seconds=query_delay_seconds,
        query_jitter_seconds=query_jitter_seconds,
        throttle_cooldown_seconds=throttle_cooldown_seconds,
        throttle_error_limit=throttle_error_limit,
    )
    return path, plan, normalized_queries, failure_policy, requested_quality, pacing_config


def _normalize_query(
    raw_query: Any,
    index: int,
    *,
    metadata_defaults: dict[str, Any] | None = None,
    total_queries: int = 1,
) -> dict[str, Any]:
    if not isinstance(raw_query, dict):
        raise BatchPlanError(f"query {index + 1} must be a JSON object")
    missing = [field for field in ("channel", "operation", "input") if not raw_query.get(field)]
    if missing:
        raise BatchPlanError(f"query {index + 1} is missing required field(s): {', '.join(missing)}")
    query = dict(raw_query)
    defaults = metadata_defaults or {}
    query_id = query.get("query_id")
    if query_id is None and defaults.get("query_id") is not None and total_queries == 1:
        query_id = defaults.get("query_id")
    if query_id is None and defaults.get("query_id_prefix") is not None:
        query_id = f"{defaults['query_id_prefix']}-{index + 1:02d}"
    query["query_id"] = str(query_id or f"q{index + 1:02d}")
    for key in ("intent", "source_role"):
        if query.get(key) is None and defaults.get(key) is not None:
            query[key] = defaults[key]
    query["channel"] = str(query["channel"])
    query["operation"] = str(query["operation"])
    query["input"] = str(query["input"])
    removed_fields = [
        field
        for field in ("body_mode", "crawl_query", "query", "page_size", "max_pages", "cursor", "page")
        if query.get(field) is not None
    ]
    if removed_fields:
        raise BatchPlanError(
            f"query {index + 1} uses removed X Reach option(s): {', '.join(removed_fields)}"
        )
    try:
        validate_operation_options(
            query["channel"],
            query["operation"],
            batch_option_values(query),
            strict_contract=True,
        )
    except OperationContractError as exc:
        raise BatchPlanError(f"query {index + 1} is invalid: {exc.message}") from exc
    return query


def _plan_metadata_defaults(plan: dict[str, Any]) -> dict[str, Any]:
    raw_metadata = plan.get("metadata")
    metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    defaults: dict[str, Any] = {}
    for key in ("intent", "query_id", "query_id_prefix", "source_role"):
        value = plan.get(key) if plan.get(key) is not None else metadata.get(key)
        if value is not None:
            defaults[key] = value
    return defaults


class _PacingController:
    def __init__(
        self,
        config: dict[str, Any],
        *,
        sleep_func: Callable[[float], None],
        time_func: Callable[[], float],
        random_func: Callable[[], float],
    ) -> None:
        self._config = config
        self._sleep = sleep_func
        self._time = time_func
        self._random = random_func
        self._lock = threading.Lock()
        self._next_start = 0.0
        self._throttle_sensitive_errors = 0
        self._throttle_guard_triggered = False

    def now(self) -> float:
        return float(self._time())

    def wait_for_start(self) -> dict[str, Any]:
        with self._lock:
            if self._throttle_guard_triggered:
                return {
                    "skipped": True,
                    "planned_wait_seconds": 0.0,
                    "applied_wait_seconds": 0.0,
                }
            now = self.now()
            jitter = self._jitter_seconds()
            planned_start = max(now, self._next_start) + jitter
            planned_wait = max(planned_start - now, 0.0)
            self._next_start = planned_start + float(self._config["query_delay_seconds"])

        applied_wait = 0.0
        if planned_wait > 0:
            before_sleep = self.now()
            self._sleep(planned_wait)
            applied_wait = max(self.now() - before_sleep, 0.0)

        with self._lock:
            if self._throttle_guard_triggered:
                return {
                    "skipped": True,
                    "planned_wait_seconds": _round_seconds(planned_wait),
                    "applied_wait_seconds": _round_seconds(applied_wait),
                }
        return {
            "skipped": False,
            "planned_wait_seconds": _round_seconds(planned_wait),
            "applied_wait_seconds": _round_seconds(applied_wait),
        }

    def record_result(self, throttle_sensitive: bool) -> dict[str, Any]:
        cooldown_applied = 0.0
        if not throttle_sensitive:
            return {"throttle_cooldown_applied_seconds": cooldown_applied}

        with self._lock:
            self._throttle_sensitive_errors += 1
            cooldown = float(self._config["throttle_cooldown_seconds"])
            if cooldown > 0:
                self._next_start = max(self._next_start, self.now() + cooldown)
                cooldown_applied = cooldown
            limit = int(self._config["throttle_error_limit"])
            if limit > 0 and self._throttle_sensitive_errors >= limit:
                self._throttle_guard_triggered = True
        return {"throttle_cooldown_applied_seconds": _round_seconds(cooldown_applied)}

    def _jitter_seconds(self) -> float:
        jitter = float(self._config["query_jitter_seconds"])
        if jitter <= 0:
            return 0.0
        value = min(max(float(self._random()), 0.0), 1.0)
        return value * jitter


def _first_present(values: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if values.get(key) is not None:
            return values[key]
    return None


def _nonnegative_float(value: Any, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise BatchPlanError(f"{name} must be a number") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise BatchPlanError(f"{name} must be greater than or equal to 0")
    return parsed


def _nonnegative_int(value: Any, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise BatchPlanError(f"{name} must be an integer") from exc
    if parsed < 0:
        raise BatchPlanError(f"{name} must be greater than or equal to 0")
    return parsed


def _query_status_base(query: dict[str, Any], *, requested_quality: str | None) -> dict[str, Any]:
    return {
        "query_id": query["query_id"],
        "channel": query["channel"],
        "operation": query["operation"],
        "input": query["input"],
        "limit": query.get("limit"),
        "intent": query.get("intent"),
        "source_role": query.get("source_role"),
        "since": query.get("since"),
        "until": query.get("until"),
        "from_user": query.get("from_user"),
        "to_user": query.get("to_user"),
        "lang": query.get("lang"),
        "search_type": query.get("search_type"),
        "has": query.get("has"),
        "exclude": query.get("exclude"),
        "min_likes": query.get("min_likes"),
        "min_retweets": query.get("min_retweets"),
        "min_views": query.get("min_views"),
        "originals_only": query.get("originals_only"),
        "quality_profile": requested_quality if is_broad_operation(query["operation"]) else None,
        "raw_mode": query.get("raw_mode"),
        "raw_max_bytes": query.get("raw_max_bytes"),
        "item_text_mode": query.get("item_text_mode"),
        "item_text_max_chars": query.get("item_text_max_chars"),
    }


def _empty_execution_diagnostics(wait_info: dict[str, Any] | None = None) -> dict[str, Any]:
    wait = wait_info or {}
    return {
        "urls": [],
        "error_code": None,
        "error_category": None,
        "error_retryable": None,
        "error_message": None,
        "started_at": None,
        "finished_at": None,
        "duration_seconds": None,
        "planned_wait_seconds": wait.get("planned_wait_seconds", 0.0),
        "applied_wait_seconds": wait.get("applied_wait_seconds", 0.0),
        "throttle_sensitive": False,
        "throttle_cooldown_applied_seconds": 0.0,
    }


def _round_seconds(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return round(max(float(value), 0.0), 6)


def _pacing_payload(config: dict[str, Any], statuses: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _pacing_summary(statuses)
    return {
        **config,
        **summary,
    }


def _pacing_summary(statuses: list[dict[str, Any]]) -> dict[str, Any]:
    total_wait = sum(float(status.get("applied_wait_seconds") or 0.0) for status in statuses)
    return {
        "waits_applied": sum(1 for status in statuses if float(status.get("applied_wait_seconds") or 0.0) > 0),
        "total_wait_seconds": _round_seconds(total_wait),
        "throttle_sensitive_errors": sum(1 for status in statuses if status.get("throttle_sensitive")),
        "throttle_guard_triggered": any(status.get("reason") == "throttle_guard" for status in statuses),
    }


def _is_throttle_sensitive_error(error: Any, *, payload: dict[str, Any] | None = None) -> bool:
    if not isinstance(error, dict):
        return False
    if error.get("category") == "rate_limited":
        return True
    details = error.get("details") if isinstance(error.get("details"), dict) else {}
    raw = (payload or {}).get("raw") if isinstance(payload, dict) else None
    haystack = " ".join(
        [
            str(error.get("code") or ""),
            str(error.get("category") or ""),
            str(error.get("message") or ""),
            " ".join(str(value) for value in details.values() if value is not None),
            _scan_text(raw),
        ]
    ).casefold()
    return any(
        marker in haystack
        for marker in (
            "rate_limited",
            "rate limit",
            "too many requests",
            "http 429",
            "http_429",
            "429",
            "http 409",
            "http_409",
            "409",
            "conflict",
        )
    )


def _scan_text(value: Any, *, limit: int = 4000) -> str:
    if value is None:
        return ""
    try:
        text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    except (TypeError, ValueError):
        text = str(value)
    return text[:limit]


def _count_values(values: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if value is None or value == "":
            continue
        text = str(value)
        counts[text] = counts.get(text, 0) + 1
    return counts


def _plan_summary(queries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "query_count": len(queries),
        "channel_counts": _count_values([query.get("channel") for query in queries]),
        "operation_counts": _count_values([query.get("operation") for query in queries]),
        "intent_counts": _count_values([query.get("intent") for query in queries]),
        "source_role_counts": _count_values([query.get("source_role") for query in queries]),
    }


def _query_key(
    query: dict[str, Any],
) -> tuple[str | None, ...]:
    limit = query.get("limit")
    return (
        str(query.get("channel")),
        str(query.get("operation")),
        str(query.get("input")),
        str(limit) if limit is not None else None,
        str(query.get("intent")) if query.get("intent") is not None else None,
        str(query.get("since")) if query.get("since") is not None else None,
        str(query.get("until")) if query.get("until") is not None else None,
        str(query.get("from_user")) if query.get("from_user") is not None else None,
        str(query.get("to_user")) if query.get("to_user") is not None else None,
        str(query.get("lang")) if query.get("lang") is not None else None,
        str(query.get("search_type")) if query.get("search_type") is not None else None,
        json.dumps(query.get("has"), ensure_ascii=False) if query.get("has") is not None else None,
        json.dumps(query.get("exclude"), ensure_ascii=False) if query.get("exclude") is not None else None,
        str(query.get("min_likes")) if query.get("min_likes") is not None else None,
        str(query.get("min_retweets")) if query.get("min_retweets") is not None else None,
        str(query.get("min_views")) if query.get("min_views") is not None else None,
        str(query.get("originals_only")) if query.get("originals_only") is not None else None,
        str(query.get("quality_profile")) if query.get("quality_profile") is not None else None,
        str(query.get("raw_mode")) if query.get("raw_mode") is not None else None,
        str(query.get("raw_max_bytes")) if query.get("raw_max_bytes") is not None else None,
        str(query.get("item_text_mode")) if query.get("item_text_mode") is not None else None,
        str(query.get("item_text_max_chars")) if query.get("item_text_max_chars") is not None else None,
    )


def _completed_query_keys(
    path: str | Path | None,
) -> set[tuple[str | None, ...]]:
    if path is None:
        return set()

    completed: set[tuple[str | None, ...]] = set()
    for record in iter_ledger_records(path, allow_missing=True):
        if not isinstance(record, dict) or record.get("record_type") != "collection_result":
            continue
        raw_result = record.get("result")
        result: dict[str, Any] = raw_result if isinstance(raw_result, dict) else {}
        raw_meta = result.get("meta")
        meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
        query = {
            "channel": record.get("channel") or result.get("channel"),
            "operation": record.get("operation") or result.get("operation"),
            "input": record.get("input") if record.get("input") is not None else meta.get("input"),
            "limit": meta.get("requested_limit") if meta.get("requested_limit") is not None else meta.get("limit"),
            "intent": record.get("intent") if record.get("intent") is not None else meta.get("intent"),
            "since": meta.get("since"),
            "until": meta.get("until"),
            "from_user": meta.get("from_user"),
            "to_user": meta.get("to_user"),
            "lang": meta.get("lang"),
            "search_type": meta.get("search_type"),
            "has": meta.get("has"),
            "exclude": meta.get("exclude"),
            "min_likes": meta.get("min_likes"),
            "min_retweets": meta.get("min_retweets"),
            "min_views": meta.get("min_views"),
            "originals_only": meta.get("originals_only"),
            "quality_profile": meta.get("quality_profile"),
            "raw_mode": meta.get("raw_mode"),
            "raw_max_bytes": meta.get("raw_max_bytes"),
            "item_text_mode": meta.get("item_text_mode"),
            "item_text_max_chars": meta.get("item_text_max_chars"),
        }
        if query["channel"] and query["operation"] and query["input"]:
            completed.add(_query_key(query))
    return completed


def _checkpoint_summary(
    statuses: list[dict[str, Any] | None],
    *,
    completed: int,
) -> dict[str, Any]:
    current = [status for status in statuses if status is not None]
    return {"completed": completed, **_summary(current)}


def _summary(statuses: list[dict[str, Any]]) -> dict[str, Any]:
    urls = []
    source_roles: dict[str, int] = {}
    for status in statuses:
        role = status.get("source_role")
        if role:
            source_roles[str(role)] = source_roles.get(str(role), 0) + 1
        for url in status.get("urls") or []:
            urls.append(str(url))
    unique_urls = set(urls)
    pacing = _pacing_summary(statuses)
    return {
        "total": len(statuses),
        "ok": sum(1 for status in statuses if status.get("status") == "ok"),
        "errors": sum(1 for status in statuses if status.get("status") == "error"),
        "skipped": sum(1 for status in statuses if status.get("status") == "skipped"),
        "items": sum(int(status.get("count") or 0) for status in statuses),
        "unique_urls": len(unique_urls),
        "duplicate_urls": len(urls) - len(unique_urls),
        "source_roles": source_roles,
        **pacing,
    }


def _render_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def _render_pacing(pacing: dict[str, Any]) -> str:
    parts = [
        f"delay={pacing.get('query_delay_seconds', 0)}s",
        f"jitter={pacing.get('query_jitter_seconds', 0)}s",
        f"throttle_cooldown={pacing.get('throttle_cooldown_seconds', 0)}s",
        f"throttle_error_limit={pacing.get('throttle_error_limit', 0)}",
    ]
    if pacing.get("waits_applied") or pacing.get("throttle_sensitive_errors"):
        parts.extend(
            [
                f"waits={pacing.get('waits_applied', 0)}",
                f"throttle_sensitive_errors={pacing.get('throttle_sensitive_errors', 0)}",
                f"guard={'yes' if pacing.get('throttle_guard_triggered') else 'no'}",
            ]
        )
    return ", ".join(parts)

