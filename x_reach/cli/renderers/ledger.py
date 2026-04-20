# -*- coding: utf-8 -*-
"""Human-readable renderers for ledger commands."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence


def render_ledger_merge_text(payload: dict[str, object]) -> str:
    return "\n".join(
        [
            "X Reach Ledger Merge",
            "========================================",
            f"Input: {payload['input']}",
            f"Output: {payload['output']}",
            f"Files merged: {payload['files_merged']}",
            f"Records written: {payload['records_written']}",
        ]
    )


def render_ledger_validate_text(payload: dict[str, object]) -> str:
    large_text_fields = _object_sequence(payload.get("large_text_fields"))
    return "\n".join(
        [
            "X Reach Ledger Validate",
            "========================================",
            f"Input: {payload['input']}",
            f"Valid: {'yes' if payload['valid'] else 'no'}",
            f"Require metadata: {'yes' if payload['require_metadata'] else 'no'}",
            f"Files checked: {payload['files_checked']}",
            f"Records: {payload['records']}",
            f"Collection results: {payload['collection_results']}",
            f"Items seen: {payload['items_seen']}",
            f"Invalid lines: {payload['invalid_lines']}",
            f"Invalid records: {payload['invalid_records']}",
            f"Large text fields: {len(large_text_fields)}",
        ]
    )


def render_ledger_summarize_text(payload: dict[str, object]) -> str:
    filters = _object_sequence(payload.get("filters"))
    rendered_filters = (
        ", ".join(
            str(item.get("expression"))
            for item in filters
            if isinstance(item, Mapping) and item.get("expression")
        )
        if filters
        else "none"
    )
    missing_metadata = _object_mapping(payload.get("missing_metadata"))
    return "\n".join(
        [
            "X Reach Ledger Summary",
            "========================================",
            f"Input: {payload['input']}",
            f"Filters: {rendered_filters}",
            f"Records: {payload['records']}",
            f"Records scanned: {payload['records_scanned']}",
            f"Collection results: {payload['collection_results']}",
            f"Items seen: {payload['items_seen']}",
            f"Errors: {payload['error_records']}",
            f"Metadata missing records: {missing_metadata.get('records')}",
        ]
    )


def render_ledger_query_text(payload: dict[str, object]) -> str:
    lines = [
        "X Reach Ledger Query",
        "========================================",
        f"Input: {payload['input']}",
        f"Files checked: {payload['files_checked']}",
        f"Records scanned: {payload['records_scanned']}",
        f"Matched: {payload['matched_records']}",
        f"Returned: {payload['returned_records']}",
    ]
    raw_filters = payload.get("filters")
    filters = raw_filters if isinstance(raw_filters, list) else []
    if filters:
        lines.append(
            "Filters: "
            + "; ".join(
                str(filter_payload.get("expression"))
                for filter_payload in filters
                if isinstance(filter_payload, dict) and filter_payload.get("expression")
            )
        )
    raw_fields = payload.get("fields")
    fields = raw_fields if isinstance(raw_fields, list) else None
    if fields:
        lines.append(f"Fields: {', '.join(str(field) for field in fields)}")
    raw_matches = payload.get("matches")
    matches = raw_matches if isinstance(raw_matches, list) else []
    for match in matches[:5]:
        lines.append(json.dumps(match, ensure_ascii=False))
    return "\n".join(lines)


def render_ledger_append_text(payload: dict[str, object]) -> str:
    return "\n".join(
        [
            "X Reach Ledger Append",
            "========================================",
            f"Input: {payload['input']}",
            f"Output: {payload['output']}",
            f"Channel: {payload['channel']}",
            f"Operation: {payload['operation']}",
            f"OK: {'yes' if payload['ok'] else 'no'}",
            f"Items: {payload['count']}",
        ]
    )


def _object_sequence(value: object) -> Sequence[object]:
    return value if isinstance(value, Sequence) and not isinstance(value, str) else []


def _object_mapping(value: object) -> Mapping[object, object]:
    return value if isinstance(value, Mapping) else {}
