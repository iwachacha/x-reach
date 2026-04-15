# -*- coding: utf-8 -*-
"""Twitter/X channel checks."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

from x_reach.adapters.twitter import TwitterAdapter
from x_reach.results import CollectionError, CollectionResult, build_error
from x_reach.utils.commands import find_command

from .base import Channel

PROBE_USER = "openai"
PROBE_SEARCH_QUERY = "OpenAI"

_SEARCH_OPERATION_OPTIONS = [
    {
        "name": "from",
        "type": "string",
        "required": False,
        "cli_flag": "--from",
        "sdk_kwarg": "from_user",
        "description": "Only include tweets from this account.",
    },
    {
        "name": "to",
        "type": "string",
        "required": False,
        "cli_flag": "--to",
        "sdk_kwarg": "to_user",
        "description": "Only include tweets directed at this account.",
    },
    {
        "name": "lang",
        "type": "string",
        "required": False,
        "cli_flag": "--lang",
        "sdk_kwarg": "lang",
        "description": "Restrict search to one language code such as en or ja.",
    },
    {
        "name": "type",
        "type": "string",
        "required": False,
        "cli_flag": "--type",
        "sdk_kwarg": "search_type",
        "choices": ["top", "latest", "photos", "videos"],
        "description": "Choose the twitter-cli search tab.",
    },
    {
        "name": "has",
        "type": "string",
        "required": False,
        "cli_flag": "--has",
        "repeatable": True,
        "choices": ["links", "images", "videos", "media"],
        "description": "Require one or more content types.",
    },
    {
        "name": "exclude",
        "type": "string",
        "required": False,
        "cli_flag": "--exclude",
        "repeatable": True,
        "choices": ["retweets", "replies", "links"],
        "description": "Exclude one or more content types.",
    },
    {
        "name": "since",
        "type": "string",
        "required": False,
        "cli_flag": "--since",
        "sdk_kwarg": "since",
        "description": "Lower date bound forwarded to twitter-cli search.",
    },
    {
        "name": "until",
        "type": "string",
        "required": False,
        "cli_flag": "--until",
        "sdk_kwarg": "until",
        "description": "Upper date bound forwarded to twitter-cli search.",
    },
    {
        "name": "min_likes",
        "type": "integer",
        "required": False,
        "cli_flag": "--min-likes",
        "sdk_kwarg": "min_likes",
        "minimum": 0,
        "description": "Minimum likes forwarded to twitter-cli search.",
    },
    {
        "name": "min_retweets",
        "type": "integer",
        "required": False,
        "cli_flag": "--min-retweets",
        "sdk_kwarg": "min_retweets",
        "minimum": 0,
        "description": "Minimum retweets forwarded to twitter-cli search.",
    },
    {
        "name": "min_views",
        "type": "integer",
        "required": False,
        "cli_flag": "--min-views",
        "sdk_kwarg": "min_views",
        "minimum": 0,
        "description": "Minimum views applied after search as a client-side post-filter.",
    },
    {
        "name": "quality_profile",
        "type": "string",
        "required": False,
        "cli_flag": "--quality-profile",
        "choices": ["precision", "balanced", "recall"],
        "description": "High-signal collection profile that controls oversampling and noise filtering.",
    },
]


class TwitterChannel(Channel):
    name = "twitter"
    description = "Twitter/X search, hashtags, profiles, posts, and tweet threads"
    backends = ["twitter-cli"]
    auth_kind = "cookie"
    entrypoint_kind = "cli"
    operations = ["search", "hashtag", "user", "user_posts", "tweet"]
    operation_inputs = {
        "search": "query",
        "hashtag": "hashtag",
        "user": "profile",
        "user_posts": "profile",
        "tweet": "post",
    }
    operation_options = {
        "search": list(_SEARCH_OPERATION_OPTIONS),
        "hashtag": list(_SEARCH_OPERATION_OPTIONS),
        "user_posts": [
            {
                "name": "originals_only",
                "type": "boolean",
                "required": False,
                "cli_flag": "--originals-only",
                "description": "Filter timeline results down to authored posts by removing retweets client-side.",
            },
            {
                "name": "quality_profile",
                "type": "string",
                "required": False,
                "cli_flag": "--quality-profile",
                "choices": ["precision", "balanced", "recall"],
                "description": "High-signal collection profile that controls oversampling and noise filtering.",
            }
        ],
    }
    required_commands = ["twitter"]
    host_patterns = ["https://x.com/*", "https://twitter.com/*"]
    example_invocations = [
        'x-reach hashtag "OpenAI" --limit 10 --json',
        'x-reach collect --operation search --input "gpt-5.4" --limit 10 --quality-profile balanced --json',
        'x-reach collect --operation search --input "OpenAI" --quality-profile precision --min-likes 100 --min-views 10000 --json',
        'x-reach collect --operation user --input "openai" --json',
        'x-reach collect --operation user_posts --input "openai" --limit 20 --quality-profile balanced --json',
        'x-reach collect --operation user_posts --input "openai" --limit 20 --json',
        'x-reach collect --operation tweet --input "https://x.com/OpenAI/status/2042296046009626989" --limit 20 --json',
        'twitter status',
    ]
    supports_probe = True
    probe_operations = ["search", "hashtag", "user", "user_posts", "tweet"]
    install_hints = [
        "Install twitter-cli with uv tool install twitter-cli.",
        'Configure cookies with x-reach configure twitter-cookies "auth_token=...; ct0=...".',
    ]

    def _all_operation_statuses(self, status: str, message: str) -> dict[str, dict[str, str]]:
        return {operation: {"status": status, "message": message} for operation in self.operations}

    def _authenticated_unprobed_statuses(self) -> dict[str, dict[str, str]]:
        message = (
            "Authenticated by twitter status, but this operation has not been live-probed. "
            "It may work; run x-reach doctor --json --probe for operation-level readiness."
        )
        return {
            operation: {
                "status": "unknown",
                "message": message,
                "diagnostic_basis": "twitter_status_authenticated",
                "usability_hint": "authenticated_but_unprobed",
                "recommended_probe_command": "x-reach doctor --json --probe",
            }
            for operation in self.operations
        }

    def _probe_state(self, *, probe_run_coverage: str) -> dict[str, Any]:
        probed_operations = list(self.probe_operations)
        unprobed_operations = [operation for operation in self.operations if operation not in probed_operations]
        return {
            "probed_operations": probed_operations if probe_run_coverage != "not_run" else [],
            "unprobed_operations": list(self.operations) if probe_run_coverage == "not_run" else unprobed_operations,
            "probe_run_coverage": probe_run_coverage,
        }

    def _operation_status_from_result(
        self,
        payload: CollectionResult,
        *,
        success_message: str,
        empty_message: str | None = None,
    ) -> dict[str, Any]:
        if payload.get("ok"):
            count = len(payload.get("items") or [])
            if count or empty_message is None:
                return {
                    "status": "ok",
                    "message": success_message,
                    "count": count,
                }
            return {
                "status": "warn",
                "message": empty_message,
                "count": count,
            }

        error: CollectionError = payload.get("error") or build_error(
            code="command_failed",
            message="operation failed",
            details={},
        )
        return {
            "status": "warn",
            "message": error.get("message") or "operation failed",
            "error_code": error.get("code") or "command_failed",
            "details": error.get("details") or {},
        }

    def can_handle(self, url: str) -> bool:
        from urllib.parse import urlparse

        host = urlparse(url).netloc.lower()
        return "x.com" in host or "twitter.com" in host

    def check(self, config=None):
        status, message, _extra = self.check_detailed(config)
        return status, message

    def check_detailed(self, config=None):
        twitter = find_command("twitter") or shutil.which("twitter")
        if not twitter:
            return "warn", "twitter-cli is missing. Install it with uv tool install twitter-cli", {
                "diagnostic_basis": "command_lookup",
                **self._probe_state(probe_run_coverage="not_run"),
                "operation_statuses": self._all_operation_statuses(
                    "off",
                    "twitter-cli is missing. Install it with uv tool install twitter-cli",
                ),
            }

        try:
            result = subprocess.run(
                [twitter, "status"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                env=_twitter_runtime_env(config),
            )
        except Exception:
            return "warn", "twitter-cli is installed but status could not be checked", {
                "diagnostic_basis": "twitter status",
                **self._probe_state(probe_run_coverage="not_run"),
                "operation_statuses": self._all_operation_statuses(
                    "unknown",
                    "twitter-cli status could not be checked. Run x-reach doctor --json --probe.",
                ),
            }

        output = f"{result.stdout}\n{result.stderr}".lower()
        if result.returncode == 0 and "ok: true" in output:
            return (
                "warn",
                "twitter-cli session is authenticated; collect may work, but live Twitter operations are unverified until x-reach doctor --json --probe",
                {
                    "diagnostic_basis": "twitter_status_authenticated",
                    "usability_hint": "authenticated_but_unprobed",
                    "recommended_probe_command": "x-reach doctor --json --probe",
                    **self._probe_state(probe_run_coverage="not_run"),
                    "operation_statuses": self._authenticated_unprobed_statuses(),
                },
            )
        if "not_authenticated" in output:
            return (
                "warn",
                "twitter-cli is installed but not authenticated. "
                "Run x-reach configure twitter-cookies \"auth_token=...; ct0=...\"",
                {
                    "diagnostic_basis": "twitter status",
                    **self._probe_state(probe_run_coverage="not_run"),
                    "operation_statuses": self._all_operation_statuses(
                        "off",
                        "Authentication is required. Run x-reach configure twitter-cookies \"auth_token=...; ct0=...\"",
                    ),
                },
            )
        return "warn", "twitter-cli is installed but did not report a healthy session", {
            "diagnostic_basis": "twitter status",
            **self._probe_state(probe_run_coverage="not_run"),
            "operation_statuses": self._all_operation_statuses(
                "unknown",
                "twitter-cli did not report a healthy session. Run x-reach doctor --json --probe.",
            ),
        }

    def probe(self, config=None):
        status, message, _extra = self.probe_detailed(config)
        return status, message

    def probe_detailed(self, config=None):
        twitter = find_command("twitter") or shutil.which("twitter")
        if not twitter:
            return "warn", "twitter-cli is missing. Install it with uv tool install twitter-cli", {
                **self._probe_state(probe_run_coverage="not_run"),
                "probe_inputs": {},
                "operation_statuses": self._all_operation_statuses(
                    "off",
                    "twitter-cli is missing. Install it with uv tool install twitter-cli",
                ),
            }

        adapter = TwitterAdapter(config=config)
        try:
            user_payload = adapter.user(PROBE_USER)
            search_payload = adapter.search(PROBE_SEARCH_QUERY, limit=1)
            user_posts_payload = adapter.user_posts(PROBE_USER, limit=1)
        except Exception as exc:
            return "warn", f"twitter-cli is installed but the live Twitter probes crashed: {exc}", {
                **self._probe_state(probe_run_coverage="not_run"),
                "probe_inputs": {
                    "user": PROBE_USER,
                    "search": PROBE_SEARCH_QUERY,
                    "hashtag": f"#{PROBE_SEARCH_QUERY}",
                    "user_posts": PROBE_USER,
                },
            }

        operation_statuses = self._all_operation_statuses(
            "unknown",
            "Not probed by x-reach doctor --json --probe.",
        )
        operation_statuses["user"] = self._operation_status_from_result(
            user_payload,
            success_message="Live user lookup succeeded via twitter-cli",
        )
        operation_statuses["search"] = self._operation_status_from_result(
            search_payload,
            success_message="Live search succeeded via twitter-cli",
            empty_message="Live search completed but returned zero items for the probe query",
        )
        search_status = operation_statuses["search"]
        operation_statuses["hashtag"] = {
            **search_status,
            "message": (
                "Live hashtag collection shares the twitter-cli search path; "
                + ("search probe succeeded" if search_status.get("status") == "ok" else "search probe did not succeed")
            ),
        }
        operation_statuses["user_posts"] = self._operation_status_from_result(
            user_posts_payload,
            success_message="Live user posts lookup succeeded via twitter-cli",
            empty_message="Live user posts lookup completed but returned zero items for the probe user",
        )

        probe_tweet_input = _probe_tweet_input(user_posts_payload)
        tweet_payload: CollectionResult | None = None
        if probe_tweet_input is None:
            operation_statuses["tweet"] = {
                "status": "warn",
                "message": "Tweet probe was skipped because user_posts did not return a probe tweet.",
                "error_code": "probe_dependency_failed",
            }
        else:
            try:
                tweet_payload = adapter.tweet(probe_tweet_input, limit=1)
            except Exception as exc:
                operation_statuses["tweet"] = {
                    "status": "warn",
                    "message": f"Live tweet probe crashed: {exc}",
                    "error_code": "probe_crashed",
                }
            else:
                operation_statuses["tweet"] = self._operation_status_from_result(
                    tweet_payload,
                    success_message="Live tweet lookup succeeded via twitter-cli",
                    empty_message="Live tweet lookup completed but returned zero items for the probe tweet",
                )

        if all(operation_statuses[operation]["status"] == "ok" for operation in self.operations):
            return "ok", "Live search, hashtag lookup, user lookup, user posts lookup, and tweet lookup all succeeded via twitter-cli", {
                **self._probe_state(probe_run_coverage="full"),
                "probe_inputs": {
                    "user": PROBE_USER,
                    "search": PROBE_SEARCH_QUERY,
                    "hashtag": f"#{PROBE_SEARCH_QUERY}",
                    "user_posts": PROBE_USER,
                    "tweet": probe_tweet_input,
                },
                "operation_statuses": operation_statuses,
            }

        user_error: CollectionError = user_payload.get("error") or build_error(
            code="",
            message="",
            details={},
        )
        search_error: CollectionError = search_payload.get("error") or build_error(
            code="",
            message="",
            details={},
        )
        user_code = user_error.get("code") or ""
        search_code = search_error.get("code") or ""
        user_posts_error: CollectionError = user_posts_payload.get("error") or build_error(
            code="",
            message="",
            details={},
        )
        user_posts_code = user_posts_error.get("code") or ""
        hashtag_code = search_code
        tweet_error: CollectionError = (
            tweet_payload.get("error")
            if isinstance(tweet_payload, dict)
            else build_error(code="", message="", details={})
        ) or build_error(code="", message="", details={})
        tweet_code = tweet_error.get("code") or ""
        auth_codes = {code for code in (user_code, search_code, hashtag_code, user_posts_code, tweet_code) if code}
        if auth_codes and auth_codes.issubset({"not_authenticated"}):
            return "warn", (
                "twitter-cli is installed but live Twitter probes are not authenticated. "
                "Run x-reach configure twitter-cookies \"auth_token=...; ct0=...\""
            ), {
                **self._probe_state(probe_run_coverage="full"),
                "probe_inputs": {
                    "user": PROBE_USER,
                    "search": PROBE_SEARCH_QUERY,
                    "hashtag": f"#{PROBE_SEARCH_QUERY}",
                    "user_posts": PROBE_USER,
                    "tweet": probe_tweet_input,
                },
                "operation_statuses": operation_statuses,
            }

        failed_operations = [
            f"{operation}={status.get('error_code') or status.get('status')}"
            for operation, status in operation_statuses.items()
            if status.get("status") != "ok"
        ]
        return "warn", (
            "twitter-cli is installed but one or more live Twitter probes failed. "
            + ", ".join(failed_operations)
        ), {
            **self._probe_state(probe_run_coverage="full"),
            "probe_inputs": {
                "user": PROBE_USER,
                "search": PROBE_SEARCH_QUERY,
                "hashtag": f"#{PROBE_SEARCH_QUERY}",
                "user_posts": PROBE_USER,
                "tweet": probe_tweet_input,
            },
            "operation_statuses": operation_statuses,
        }


def _probe_tweet_input(payload: CollectionResult) -> str | None:
    items = payload.get("items") or []
    if not items:
        return None
    item = items[0]
    if item.get("url"):
        return str(item["url"])
    if item.get("id"):
        return str(item["id"])
    return None


def _twitter_runtime_env(config=None) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    auth_token = env.get("TWITTER_AUTH_TOKEN") or env.get("AUTH_TOKEN")
    ct0 = env.get("TWITTER_CT0") or env.get("CT0")

    if config is not None:
        auth_token = auth_token or config.get("twitter_auth_token")
        ct0 = ct0 or config.get("twitter_ct0")

    if auth_token and ct0:
        env["TWITTER_AUTH_TOKEN"] = str(auth_token)
        env["TWITTER_CT0"] = str(ct0)
        env["AUTH_TOKEN"] = str(auth_token)
        env["CT0"] = str(ct0)
    return env


