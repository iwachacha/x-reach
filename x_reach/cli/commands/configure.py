# -*- coding: utf-8 -*-
"""Configuration command handlers."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


def register_configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("configure", help="Save credentials or import them from a browser")
    parser.add_argument(
        "key",
        nargs="?",
        choices=["twitter-cookies"],
        help="Configuration key to set",
    )
    parser.add_argument("value", nargs="*", help="Value to store")
    parser.add_argument(
        "--from-browser",
        metavar="BROWSER",
        choices=["chrome", "firefox", "edge", "brave", "opera"],
        help="Import Twitter cookies from a local browser",
    )
    parser.set_defaults(handler=handle_configure)


def handle_configure(args) -> int:
    from x_reach.config import Config

    config = Config()

    if args.from_browser:
        _configure_from_browser(args.from_browser, config)
        return 0

    if not args.key:
        raise SystemExit("configure requires either a key or --from-browser")

    value = " ".join(args.value).strip()
    if args.key == "twitter-cookies":
        if not value:
            raise SystemExit("twitter-cookies requires a cookie header string or two values")
        auth_token, ct0 = _parse_twitter_cookie_input(value)
        config.set("twitter_auth_token", auth_token)
        config.set("twitter_ct0", ct0)
        _persist_twitter_env(auth_token, ct0)
        print("Saved Twitter/X cookies to config.")
        print("Verify with: twitter status")
        return 0

    raise SystemExit(f"Unsupported configure key: {args.key}")


def _parse_twitter_cookie_input(raw: str) -> tuple[str, str]:
    raw = raw.strip()
    if not raw:
        raise SystemExit("Twitter cookie input is empty")

    if "auth_token=" in raw or "ct0=" in raw:
        parts = {}
        for item in raw.split(";"):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            parts[key.strip()] = value.strip()
        auth_token = parts.get("auth_token")
        ct0 = parts.get("ct0")
        if auth_token and ct0:
            return auth_token, ct0
        raise SystemExit("Twitter cookie header must include both auth_token and ct0")

    values = raw.split()
    if len(values) == 2:
        return values[0], values[1]
    raise SystemExit("Provide either `auth_token=...; ct0=...` or `AUTH_TOKEN CT0`")


def _configure_from_browser(browser: str, config) -> None:
    try:
        from x_reach.cookie_extract import extract_all
    except Exception as exc:
        raise SystemExit(f"Browser import support is unavailable: {exc}")

    try:
        extracted = extract_all(browser)
    except Exception as exc:
        raise SystemExit(str(exc))

    twitter = extracted.get("twitter") or {}
    auth_token = twitter.get("auth_token")
    ct0 = twitter.get("ct0")
    if not auth_token or not ct0:
        raise SystemExit(f"No Twitter/X cookies were found in {browser}")

    config.set("twitter_auth_token", auth_token)
    config.set("twitter_ct0", ct0)
    _persist_twitter_env(auth_token, ct0)
    print(f"Imported Twitter/X cookies from {browser}.")
    print("Verify with: twitter status")


def _persist_twitter_env(auth_token: str, ct0: str) -> None:
    """Persist Twitter credentials for twitter-cli across future shells."""

    os.environ["TWITTER_AUTH_TOKEN"] = auth_token
    os.environ["TWITTER_CT0"] = ct0
    os.environ["AUTH_TOKEN"] = auth_token
    os.environ["CT0"] = ct0

    if sys.platform != "win32":
        return

    for key, value in (
        ("TWITTER_AUTH_TOKEN", auth_token),
        ("TWITTER_CT0", ct0),
        ("AUTH_TOKEN", auth_token),
        ("CT0", ct0),
    ):
        try:
            subprocess.run(
                ["setx", key, value],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except Exception:
            pass
