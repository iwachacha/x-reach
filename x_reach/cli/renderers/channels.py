# -*- coding: utf-8 -*-
"""Human-readable renderers for channel contract output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def render_channels_text(contracts: Sequence[dict[str, object]]) -> str:
    lines = [
        "X Reach Channels",
        "========================================",
        "",
    ]
    for contract in contracts:
        lines.append(str(contract["name"]))
        lines.append(f"  {contract['description']}")
        backends = _object_sequence(contract.get("backends"))
        lines.append(f"  backends: {', '.join(str(item) for item in backends) or 'none'}")
        lines.append(
            f"  auth: {contract['auth_kind']} | entrypoint: {contract['entrypoint_kind']}"
        )
        operations = _object_sequence(contract.get("operations"))
        if operations:
            lines.append(f"  operations: {', '.join(str(item) for item in operations)}")
        operation_contracts = _object_mapping(contract.get("operation_contracts"))
        if operation_contracts:
            for operation in operations:
                details = _object_mapping(operation_contracts.get(operation))
                options = _object_sequence(details.get("options"))
                option_names = [option.get("name") for option in options if isinstance(option, dict) and option.get("name")]
                option_suffix = f" | options: {', '.join(str(item) for item in option_names)}" if option_names else ""
                lines.append(
                    "  "
                    f"- {operation}: input={details.get('input_kind', 'text')} "
                    f"| limit={'yes' if details.get('accepts_limit', False) else 'no'}"
                    f"{option_suffix}"
                )
        probe_line = f"  probe: {'yes' if contract['supports_probe'] else 'no'}"
        if contract.get("supports_probe"):
            coverage = contract.get("probe_coverage") or "full"
            probe_operations = _object_sequence(contract.get("probe_operations"))
            probe_line += f" | coverage: {coverage}"
            if probe_operations:
                probe_line += f" | probe ops: {', '.join(str(item) for item in probe_operations)}"
        lines.append(probe_line)
        required_commands = _object_sequence(contract.get("required_commands"))
        if required_commands:
            lines.append(f"  commands: {', '.join(str(item) for item in required_commands)}")
        host_patterns = _object_sequence(contract.get("host_patterns"))
        if host_patterns:
            lines.append(f"  hosts: {', '.join(str(item) for item in host_patterns)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _object_sequence(value: object) -> Sequence[object]:
    return value if isinstance(value, Sequence) and not isinstance(value, str) else []


def _object_mapping(value: object) -> Mapping[object, object]:
    return value if isinstance(value, Mapping) else {}
