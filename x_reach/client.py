# -*- coding: utf-8 -*-
"""Public SDK for X Reach."""

from __future__ import annotations

from typing import Optional, Sequence

from agent_reach.adapters import get_adapter
from agent_reach.channels import get_all_channel_contracts
from agent_reach.config import Config
from agent_reach.operation_contracts import OperationContractError, validate_operation_options
from agent_reach.results import CollectionResult, build_error, build_result


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
    ) -> CollectionResult:
        """Run a user timeline lookup and optionally keep only authored posts."""

        return self._client.collect(
            self._channel,
            "user_posts",
            value,
            limit=limit,
            originals_only=originals_only or None,
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
        from agent_reach.doctor import check_all

        return check_all(self.config)

    def doctor_payload(
        self,
        probe: bool = False,
        *,
        required_channels: Sequence[str] | None = None,
        require_all: bool = False,
    ) -> dict:
        from agent_reach.doctor import check_all, make_doctor_payload

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
        from agent_reach.doctor import check_all, format_report

        return format_report(
            check_all(self.config, probe=probe),
            probe=probe,
            required_channels=required_channels,
            require_all=require_all,
        )

    def channels(self) -> list[dict]:
        """Return the stable channel registry contract."""

        return get_all_channel_contracts()

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
            return build_result(
                ok=False,
                channel=channel,
                operation=operation,
                meta={"input": text_value, "limit": limit},
                error=build_error(
                    code="invalid_input",
                    message="limit must be greater than or equal to 1",
                    details={"limit": limit},
                ),
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
            return method(text_value, **call_kwargs)
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


class XReach(XReachClient):
    """Primary compatibility surface for the X Reach SDK."""


__all__ = ["XReach", "XReachClient"]
