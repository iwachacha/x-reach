# -*- coding: utf-8 -*-
"""Human-readable renderers for collection output."""

from __future__ import annotations

from x_reach.results import CollectionResult


def compact_text_snippet(text: str | None, max_chars: int | None) -> str | None:
    if max_chars is None or not text:
        return None
    snippet = " ".join(text.split())
    if not snippet:
        return None
    if len(snippet) > max_chars:
        return f"{snippet[:max_chars]}..."
    return snippet


def render_collect_text(payload: CollectionResult, max_text_chars: int | None = None) -> str:
    lines = [
        "X Reach Collection",
        "========================================",
        f"Channel: {payload['channel']}",
        f"Operation: {payload['operation']}",
        f"OK: {'yes' if payload['ok'] else 'no'}",
    ]
    if payload["ok"]:
        lines.append(f"Items: {len(payload['items'])}")
        for item in payload["items"][:5]:
            title = item.get("title") or item.get("id")
            url = item.get("url") or ""
            lines.append(f"  - {title} {url}".rstrip())
            snippet = compact_text_snippet(item.get("text"), max_text_chars)
            if snippet:
                lines.append(f"    {snippet}")
    else:
        error = payload["error"]
        code = error["code"] if error else "unknown"
        message = error["message"] if error else ""
        lines.append(f"Error: {code} - {message}".rstrip())
    return "\n".join(lines)
