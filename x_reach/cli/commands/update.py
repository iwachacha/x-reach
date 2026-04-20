# -*- coding: utf-8 -*-
"""Update-check command handler."""

from __future__ import annotations

import argparse
import time
import warnings

from x_reach import __version__
from x_reach.cli.common import print_json
from x_reach.cli.renderers.update import render_update_payload
from x_reach.schemas import SCHEMA_VERSION, utc_timestamp

UPSTREAM_REPO = "Panniantong/Agent-Reach"


def register_update_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("check-update", help="Check the upstream project for new releases")
    parser.add_argument("--json", action="store_true", help="Print machine-readable update data")
    parser.set_defaults(handler=handle_check_update)


def _import_requests():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"urllib3 .* doesn't match a supported version!",
        )
        import requests

    return requests


def _classify_update_error(exc) -> str:
    requests = _import_requests()

    if isinstance(exc, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(exc, requests.exceptions.ConnectionError):
        text = str(exc).lower()
        markers = [
            "name or service not known",
            "temporary failure in name resolution",
            "nodename nor servname",
            "getaddrinfo failed",
            "dns",
        ]
        if any(marker in text for marker in markers):
            return "dns"
        return "connection"
    if isinstance(exc, requests.exceptions.HTTPError):
        return "http"
    return "unknown"


def _classify_github_response_error(resp) -> str | None:
    if resp is None:
        return "unknown"
    if resp.status_code == 429:
        return "rate_limit"
    if resp.status_code == 403:
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining == "0":
            return "rate_limit"
        try:
            message = resp.json().get("message", "").lower()
        except Exception:
            message = ""
        if "rate limit" in message:
            return "rate_limit"
    if 500 <= resp.status_code < 600:
        return "server_error"
    return None


def _update_error_text(kind: str) -> str:
    mapping = {
        "timeout": "request timed out",
        "dns": "DNS resolution failed",
        "rate_limit": "GitHub API rate limit reached",
        "connection": "connection failed",
        "server_error": "GitHub returned a server error",
        "http": "HTTP request failed",
        "unknown": "unknown error",
    }
    return mapping.get(kind, "unknown error")


def _github_get_with_retry(url: str, timeout: int = 10, retries: int = 3, sleeper=time.sleep):
    requests = _import_requests()

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            if attempt >= retries:
                return None, _classify_update_error(exc), attempt
            sleeper(2 ** (attempt - 1))
            continue

        err = _classify_github_response_error(response)
        if err in {"rate_limit", "server_error"}:
            if attempt >= retries:
                return None, err, attempt
            delay = 2 ** (attempt - 1)
            retry_after = response.headers.get("Retry-After")
            if err == "rate_limit" and retry_after:
                try:
                    delay = max(delay, float(retry_after))
                except Exception:
                    pass
            sleeper(delay)
            continue

        return response, None, attempt

    return None, "unknown", retries


def _build_update_payload() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "command": "check-update",
        "current_version": __version__,
        "upstream_repo": UPSTREAM_REPO,
        "comparison_target": "upstream_release",
        "status": "error",
    }
    release_url = f"https://api.github.com/repos/{UPSTREAM_REPO}/releases/latest"
    commit_url = f"https://api.github.com/repos/{UPSTREAM_REPO}/commits/main"

    response, err, attempts = _github_get_with_retry(release_url, timeout=10, retries=3)
    if err:
        payload.update(
            {
                "status": "error",
                "error": _update_error_text(err),
                "error_kind": err,
                "attempts": attempts,
            }
        )
        return payload

    if response is not None and response.status_code == 200:
        release_payload = response.json()
        latest = release_payload.get("tag_name", "").lstrip("v")
        payload["latest_version"] = latest or __version__
        comparison = _compare_versions(__version__, latest)
        if latest and comparison < 0:
            payload["status"] = "update_available"
            body = release_payload.get("body", "").strip()
            payload["release_notes_preview"] = body.splitlines()[:20] if body else []
        elif latest and comparison > 0:
            payload["status"] = "ahead_of_upstream_release"
        else:
            payload["status"] = "up_to_date"
        return payload

    response, err, attempts = _github_get_with_retry(commit_url, timeout=10, retries=2)
    if err:
        payload.update(
            {
                "status": "error",
                "error": _update_error_text(err),
                "error_kind": err,
                "attempts": attempts,
            }
        )
        return payload

    if response is not None and response.status_code == 200:
        commit_payload = response.json()
        payload.update(
            {
                "status": "unknown",
                "latest_main_commit": {
                    "sha": commit_payload.get("sha", "")[:7],
                    "date": commit_payload.get("commit", {})
                    .get("committer", {})
                    .get("date", "")[:10],
                    "message": commit_payload.get("commit", {}).get("message", "").splitlines()[0],
                },
            }
        )
        return payload

    payload.update(
        {
            "status": "error",
            "error": f"GitHub returned HTTP {response.status_code if response is not None else 'unknown'}",
            "error_kind": "http",
        }
    )
    return payload


def _parse_version_parts(value: str) -> tuple[int, ...] | None:
    text = (value or "").strip()
    if not text:
        return None
    parts = text.split(".")
    parsed: list[int] = []
    for part in parts:
        if not part.isdigit():
            return None
        parsed.append(int(part))
    return tuple(parsed)


def _compare_versions(current: str, latest: str) -> int:
    current_parts = _parse_version_parts(current)
    latest_parts = _parse_version_parts(latest)
    if current_parts is not None and latest_parts is not None:
        width = max(len(current_parts), len(latest_parts))
        current_parts += (0,) * (width - len(current_parts))
        latest_parts += (0,) * (width - len(latest_parts))
        if current_parts < latest_parts:
            return -1
        if current_parts > latest_parts:
            return 1
        return 0
    if current == latest:
        return 0
    return -1


def handle_check_update(args) -> int:
    payload = _build_update_payload()
    if args.json:
        print_json(payload)
    else:
        print(render_update_payload(payload))
    return 1 if payload["status"] == "error" else 0
