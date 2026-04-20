# -*- coding: utf-8 -*-
"""Human-readable renderers for install planning."""

from __future__ import annotations

from collections.abc import Sequence


def render_install_plan(commands: Sequence[str], *, dry_run: bool = False) -> str:
    prefix = "[dry-run] Would run:" if dry_run else "Manual Windows commands:"
    lines = [prefix]
    lines.extend(f"  {command}" for command in commands)
    if dry_run:
        lines.extend(["", "Dry run complete. No changes were made."])
    return "\n".join(lines)
