# -*- coding: utf-8 -*-
"""Public SDK for X Reach."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence

from x_reach.adapters import get_adapter
from x_reach.candidates import build_candidates_payload
from x_reach.channels import get_all_channel_contracts
from x_reach.config import Config
from x_reach.high_signal import (
    DEFAULT_BROAD_ITEM_TEXT_MAX_CHARS,
    DEFAULT_BROAD_ITEM_TEXT_MODE,
    DEFAULT_BROAD_RAW_MODE,
    is_broad_operation,
    normalize_quality_profile,
)
from x_reach.ledger import (
    merge_ledger_inputs,
    query_ledger_input,
    summarize_ledger_input,
    validate_ledger_input_with_filters,
)
from x_reach.operation_contracts import OperationContractError, validate_operation_options
from x_reach.results import (
    CollectionResult,
    apply_item_text_mode,
    apply_raw_mode,
    build_error,
    build_result,
)


class _Namespace:
    """Thin per-channel SDK namespace."""

    def __init__(self, client: "XReachClient", channel: str):
        self._client = client
        self._channel = channel

    def search(
        self,
        value: str,
        limit: int | None = None,
        *,
        since: str | None = None,
        until: str | None = None,
        from_user: str | None = None,
        to_user: str | None = None,
        lang: str | None = None,
        search_type: str | None = None,
        has: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
        min_likes: int | None = None,
        min_retweets: int | None = None,
        min_views: int | None = None,
        quality_profile: str | None = None,
        raw_mode: str | None = None,
        raw_max_bytes: int | None = None,
        item_text_mode: str | None = None,
        item_text_max_chars: int | None = None,
    ) -> CollectionResult:
        """Run the X search operation with optional quality filters."""

        return self._client.collect(
            self._channel,
            "search",
            value,
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
            raw_mode=raw_mode,
            raw_max_bytes=raw_max_bytes,
            item_text_mode=item_text_mode,
            item_text_max_chars=item_text_max_chars,
        )

    def hashtag(
        self,
        value: str,
        limit: int | None = None,
        *,
        since: str | None = None,
        until: str | None = None,
        from_user: str | None = None,
        to_user: str | None = None,
        lang: str | None = None,
        search_type: str | None = None,
        has: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
        min_likes: int | None = None,
        min_retweets: int | None = None,
        min_views: int | None = None,
        quality_profile: str | None = None,
        raw_mode: str | None = None,
        raw_max_bytes: int | None = None,
        item_text_mode: str | None = None,
        item_text_max_chars: int | None = None,
    ) -> CollectionResult:
        """Run a hashtag-centered X search with the same filter surface as search()."""

        return self._client.collect(
            self._channel,
            "hashtag",
            value,
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
            raw_mode=raw_mode,
            raw_max_bytes=raw_max_bytes,
            item_text_mode=item_text_mode,
            item_text_max_chars=item_text_max_chars,
        )

    def user(self, value: str, limit: int | None = None) -> CollectionResult:
        """Run a profile lookup operation when supported by this channel."""

        return self._client.collect(self._channel, "user", value, limit=limit)

    def user_posts(
        self,
        value: str,
        limit: int | None = None,
        *,
        originals_only: bool = False,
        quality_profile: str | None = None,
        raw_mode: str | None = None,
        raw_max_bytes: int | None = None,
        item_text_mode: str | None = None,
        item_text_max_chars: int | None = None,
    ) -> CollectionResult:
        """Run a user timeline lookup and optionally keep only authored posts."""

        return self._client.collect(
            self._channel,
            "user_posts",
            value,
            limit=limit,
            originals_only=originals_only or None,
            quality_profile=quality_profile,
            raw_mode=raw_mode,
            raw_max_bytes=raw_max_bytes,
            item_text_mode=item_text_mode,
            item_text_max_chars=item_text_max_chars,
        )

    def tweet(self, value: str, limit: int | None = None) -> CollectionResult:
        """Run a single tweet/thread lookup operation when supported by this channel."""

        return self._client.collect(self._channel, "tweet", value, limit=limit)


class XReachClient:
    """Public SDK for diagnostics, registry lookups, and read-only collection."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.twitter = _Namespace(self, "twitter")

    def doctor(self) -> dict[str, dict]:
        from x_reach.doctor import check_all

        return check_all(self.config)

    def doctor_payload(
        self,
        probe: bool = False,
        *,
        required_channels: Sequence[str] | None = None,
        require_all: bool = False,
    ) -> dict:
        from x_reach.doctor import check_all, make_doctor_payload

        return make_doctor_payload(
            check_all(self.config, probe=probe),
            probe=probe,
            required_channels=required_channels,
            require_all=require_all,
        )

    def doctor_report(
        self,
        probe: bool = False,
        *,
        required_channels: Sequence[str] | None = None,
        require_all: bool = False,
    ) -> str:
        from x_reach.doctor import check_all, format_report

        return format_report(
            check_all(self.config, probe=probe),
            probe=probe,
            required_channels=required_channels,
            require_all=require_all,
        )

    def channels(self) -> list[dict]:
        """Return the stable channel registry contract."""

        return get_all_channel_contracts()

    def plan_candidates(
        self,
        input_path: str | Path,
        *,
        by: str = "url",
        limit: int = 20,
        summary_only: bool = False,
        fields: Sequence[str] | str | None = None,
        max_per_author: int | None = None,
        prefer_originals: bool = False,
        drop_noise: bool = False,
        drop_title_duplicates: bool = False,
        require_query_match: bool = False,
        min_seen_in: int | None = None,
    ) -> dict[str, Any]:
        """Build lightweight follow-up candidates from an evidence ledger."""

        return build_candidates_payload(
            input_path,
            by=by,
            limit=limit,
            summary_only=summary_only,
            fields=fields,
            max_per_author=max_per_author,
            prefer_originals=prefer_originals,
            drop_noise=drop_noise,
            drop_title_duplicates=drop_title_duplicates,
            require_query_match=require_query_match,
            min_seen_in=min_seen_in,
        )

    def ledger_merge(self, input_path: str | Path, output_path: str | Path) -> dict[str, Any]:
        """Merge one ledger file or a shard directory into one JSONL file."""

        return merge_ledger_inputs(input_path, output_path)

    def ledger_validate(
        self,
        input_path: str | Path,
        *,
        require_metadata: bool = False,
        filters: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Validate an evidence ledger, optionally within a filtered subset."""

        return validate_ledger_input_with_filters(
            input_path,
            require_metadata=require_metadata,
            filters=list(filters or []),
        )

    def ledger_summarize(
        self,
        input_path: str | Path,
        *,
        filters: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Return compact ledger health counts for downstream automation."""

        return summarize_ledger_input(input_path, filters=list(filters or []))

    def ledger_query(
        self,
        input_path: str | Path,
        *,
        filters: Sequence[str] | None = None,
        limit: int | None = None,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Query ledger records with the same dotted-path surface as the CLI."""

        return query_ledger_input(
            input_path,
            filters=list(filters or []),
            limit=limit,
            fields=list(fields) if fields is not None else None,
        )

    def collect(
        self,
        channel: str,
        operation: str,
        value: str,
        limit: int | None = None,
        since: str | None = None,
        until: str | None = None,
        from_user: str | None = None,
        to_user: str | None = None,
        lang: str | None = None,
        search_type: str | None = None,
        has: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
        min_likes: int | None = None,
        min_retweets: int | None = None,
        min_views: int | None = None,
        originals_only: bool | None = None,
        quality_profile: str | None = None,
        raw_mode: str | None = None,
        raw_max_bytes: int | None = None,
        item_text_mode: str | None = None,
        item_text_max_chars: int | None = None,
    ) -> CollectionResult:
        """Run a supported collection operation and return a stable result envelope."""

        text_value = value.strip()
        if not text_value:
            return build_result(
                ok=False,
                channel=channel,
                operation=operation,
                meta={"input": value},
                error=build_error(
                    code="invalid_input",
                    message="Collection input must not be empty",
                    details={},
                ),
            )

        if limit is not None and limit < 1:
            return _invalid_input_result(
                channel=channel,
                operation=operation,
                input_value=text_value,
                limit=limit,
                message="limit must be greater than or equal to 1",
                details={"limit": limit},
            )
        try:
            effective_quality_profile = normalize_quality_profile(operation, quality_profile)
        except ValueError as exc:
            return _invalid_input_result(
                channel=channel,
                operation=operation,
                input_value=text_value,
                limit=limit,
                message=str(exc),
                details={"quality_profile": quality_profile},
            )

        quality_profile_defaulted = (
            quality_profile is None
            and effective_quality_profile is not None
            and is_broad_operation(operation)
        )

        options = {
            "since": since,
            "until": until,
            "from_user": from_user,
            "to_user": to_user,
            "lang": lang,
            "search_type": search_type,
            "has": list(has) if has is not None else None,
            "exclude": list(exclude) if exclude is not None else None,
            "min_likes": min_likes,
            "min_retweets": min_retweets,
            "min_views": min_views,
            "originals_only": originals_only,
            "quality_profile": effective_quality_profile,
        }
        adapter = get_adapter(channel, config=self.config)
        if adapter is None:
            return build_result(
                ok=False,
                channel=channel,
                operation=operation,
                meta={"input": text_value},
                error=build_error(
                    code="unknown_channel",
                    message=f"Unknown channel: {channel}",
                    details={},
                ),
            )

        supported_operations = list(adapter.supported_operations())
        if operation not in supported_operations:
            return build_result(
                ok=False,
                channel=channel,
                operation=operation,
                meta={
                    "input": text_value,
                    "supported_operations": supported_operations,
                },
                error=build_error(
                    code="unsupported_operation",
                    message=f"{channel} does not support operation: {operation}",
                    details={"supported_operations": supported_operations},
                ),
            )

        try:
            validate_operation_options(channel, operation, options)
        except OperationContractError as exc:
            return build_result(
                ok=False,
                channel=channel,
                operation=operation,
                meta={
                    "input": text_value,
                    **({"limit": limit} if limit is not None else {}),
                    **({key: value for key, value in options.items() if value is not None}),
                },
                error=build_error(code=exc.code, message=exc.message, details=exc.details),
            )

        method = getattr(adapter, operation)
        try:
            call_kwargs: dict[str, object] = {}
            if limit is not None:
                call_kwargs["limit"] = limit
            for option_name, option_value in options.items():
                if option_value is not None:
                    call_kwargs[option_name] = option_value
            payload = method(text_value, **call_kwargs)
        except Exception as exc:
            return build_result(
                ok=False,
                channel=channel,
                operation=operation,
                meta={"input": text_value, **({"limit": limit} if limit is not None else {})},
                error=build_error(
                    code="internal_error",
                    message=f"{channel} {operation} raised an unexpected error: {exc}",
                    details={"exception_type": type(exc).__name__},
                ),
            )
        return _shape_collection_result(
            payload,
            operation=operation,
            quality_profile=effective_quality_profile,
            quality_profile_defaulted=quality_profile_defaulted,
            raw_mode=raw_mode,
            raw_max_bytes=raw_max_bytes,
            item_text_mode=item_text_mode,
            item_text_max_chars=item_text_max_chars,
        )


class XReach(XReachClient):
    """Primary compatibility surface for the X Reach SDK."""


AgentReachClient = XReachClient
AgentReach = XReach


__all__ = ["AgentReach", "AgentReachClient", "XReach", "XReachClient"]


def _invalid_input_result(
    *,
    channel: str,
    operation: str,
    input_value: str,
    limit: int | None = None,
    message: str,
    details: dict[str, object] | None = None,
) -> CollectionResult:
    meta = {"input": input_value}
    if limit is not None:
        meta["limit"] = limit
    return build_result(
        ok=False,
        channel=channel,
        operation=operation,
        meta=meta,
        error=build_error(code="invalid_input", message=message, details=details or {}),
    )


def _shape_collection_result(
    payload: CollectionResult,
    *,
    operation: str,
    quality_profile: str | None,
    quality_profile_defaulted: bool,
    raw_mode: str | None,
    raw_max_bytes: int | None,
    item_text_mode: str | None,
    item_text_max_chars: int | None,
) -> CollectionResult:
    effective_raw_mode = raw_mode
    effective_item_text_mode = item_text_mode
    effective_item_text_max_chars = item_text_max_chars
    applied_defaults = dict(payload.get("meta") or {}).get("applied_defaults")
    normalized_applied_defaults = dict(applied_defaults) if isinstance(applied_defaults, dict) else {}

    if effective_raw_mode is None and raw_max_bytes is not None:
        effective_raw_mode = "full"
    if effective_item_text_mode is None and item_text_max_chars is not None:
        effective_item_text_mode = "snippet"

    if is_broad_operation(operation):
        if effective_raw_mode is None:
            effective_raw_mode = DEFAULT_BROAD_RAW_MODE
            normalized_applied_defaults.setdefault("raw_mode", effective_raw_mode)
        if effective_item_text_mode is None:
            effective_item_text_mode = DEFAULT_BROAD_ITEM_TEXT_MODE
            normalized_applied_defaults.setdefault("item_text_mode", effective_item_text_mode)
        if effective_item_text_mode == "snippet" and effective_item_text_max_chars is None:
            effective_item_text_max_chars = DEFAULT_BROAD_ITEM_TEXT_MAX_CHARS
            normalized_applied_defaults.setdefault(
                "item_text_max_chars",
                effective_item_text_max_chars,
            )
        if quality_profile_defaulted and quality_profile is not None:
            normalized_applied_defaults.setdefault("quality_profile", quality_profile)
    else:
        effective_raw_mode = effective_raw_mode or "full"
        effective_item_text_mode = effective_item_text_mode or "full"

    shaped = {
        **payload,
        "meta": dict(payload.get("meta") or {}),
    }
    if normalized_applied_defaults:
        shaped["meta"]["applied_defaults"] = normalized_applied_defaults
    if quality_profile is not None:
        shaped["meta"]["quality_profile"] = quality_profile
    try:
        shaped = apply_item_text_mode(
            shaped,
            item_text_mode=effective_item_text_mode,
            item_text_max_chars=effective_item_text_max_chars,
        )
        shaped = apply_raw_mode(
            shaped,
            raw_mode=effective_raw_mode,
            raw_max_bytes=raw_max_bytes,
        )
    except ValueError as exc:
        return build_result(
            ok=False,
            channel=payload["channel"],
            operation=payload["operation"],
            meta={
                "input": shaped["meta"].get("input"),
                **(
                    {"limit": shaped["meta"].get("requested_limit")}
                    if shaped["meta"].get("requested_limit") is not None
                    else {}
                ),
            },
            error=build_error(
                code="invalid_input",
                message=str(exc),
                details={
                    "raw_mode": raw_mode,
                    "raw_max_bytes": raw_max_bytes,
                    "item_text_mode": item_text_mode,
                    "item_text_max_chars": item_text_max_chars,
                },
            ),
        )
    return shaped

