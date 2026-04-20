# -*- coding: utf-8 -*-
"""Shared runtime helpers for the CLI package."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Sequence


def ensure_utf8_console() -> None:
    """Best-effort UTF-8 stdout/stderr on Windows terminals."""

    if sys.platform != "win32" or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    try:
        import io

        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


def configure_logging(verbose: bool = False) -> None:
    """Keep loguru quiet unless verbose output is explicitly requested."""

    from loguru import logger

    logger.remove()
    if verbose:
        logger.add(sys.stderr, level="INFO")


def print_json(payload: object) -> None:
    """Render a stable JSON payload."""

    print(json.dumps(payload, indent=2, ensure_ascii=False))


def run(
    command: Sequence[str],
    timeout: int = 120,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with stable text capture defaults."""

    return subprocess.run(
        list(command),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=check,
    )
