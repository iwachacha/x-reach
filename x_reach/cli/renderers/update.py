# -*- coding: utf-8 -*-
"""Human-readable renderers for update checks."""

from __future__ import annotations


def render_update_payload(payload: dict[str, object]) -> str:
    lines = [f"Current version: v{payload['current_version']}"]
    status = payload["status"]

    if status == "error":
        attempts = payload.get("attempts")
        detail = payload.get("error", "unknown error")
        if attempts:
            lines.append(f"[WARN] Could not check releases: {detail} after {attempts} attempt(s)")
        else:
            lines.append(f"[WARN] Could not check releases: {detail}")
        return "\n".join(lines)

    if status == "update_available":
        lines.append(f"Update available: v{payload.get('latest_version', 'unknown')}")
        notes = payload.get("release_notes_preview", [])
        if isinstance(notes, list) and notes:
            lines.append("")
            for line in notes:
                lines.append(f"  {line}")
        return "\n".join(lines)

    if status == "up_to_date":
        lines.append("Already up to date.")
        return "\n".join(lines)

    if status == "ahead_of_upstream_release":
        lines.append(
            "This fork is ahead of the latest upstream release: "
            f"v{payload.get('latest_version', 'unknown')}"
        )
        return "\n".join(lines)

    if status == "unknown":
        commit = payload.get("latest_main_commit", {})
        if not isinstance(commit, dict):
            commit = {}
        lines.append(
            "Latest main commit: "
            f"{commit.get('sha', '')} ({commit.get('date', '')}) {commit.get('message', '')}"
        )
        return "\n".join(lines)

    lines.append("[WARN] Unknown update status")
    return "\n".join(lines)
