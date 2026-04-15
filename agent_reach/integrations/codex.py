# -*- coding: utf-8 -*-
"""Codex-oriented integration exports for the Twitter-only fork."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agent_reach import __version__
from agent_reach.channels import get_all_channel_contracts
from agent_reach.schemas import SCHEMA_VERSION, utc_timestamp

PACKAGED_SKILL_NAMES = (
    "agent-reach",
    "agent-reach-shape-brief",
    "agent-reach-budgeted-research",
    "agent-reach-orchestrate",
    "agent-reach-propose-improvements",
    "agent-reach-maintain-proposals",
    "agent-reach-maintain-release",
)
INTEGRATION_PROFILES = ("full", "runtime-minimal")
FORK_REPO_URL = "https://github.com/iwachacha/twitter-reach.git"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def packaged_skill_source() -> Path:
    return Path(__file__).resolve().parents[1] / "skills"


def _current_working_dir() -> Path:
    return Path.cwd()


def _candidate_skill_roots() -> list[Path]:
    roots: list[Path] = []
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        roots.append(Path(codex_home) / "skills")
    roots.append(Path.home() / ".codex" / "skills")
    roots.append(Path.home() / ".agents" / "skills")
    return roots


def _candidate_skill_targets() -> list[Path]:
    targets: list[Path] = []
    for root in _candidate_skill_roots():
        for skill_name in PACKAGED_SKILL_NAMES:
            targets.append(root / skill_name)
    return targets


def _required_commands(channels: list[dict]) -> list[str]:
    commands = set()
    for channel in channels:
        commands.update(channel.get("required_commands", []))
    return sorted(commands)


def _artifact_paths(repo_root: Path) -> dict[str, Path]:
    return {
        "plugin_manifest": repo_root / ".codex-plugin" / "plugin.json",
        "mcp_config": repo_root / ".mcp.json",
        "docs_install": repo_root / "docs" / "install.md",
        "docs_codex_integration": repo_root / "docs" / "codex-integration.md",
        "docs_downstream_usage": repo_root / "docs" / "downstream-usage.md",
        "docs_python_sdk": repo_root / "docs" / "python-sdk.md",
        "docs_troubleshooting": repo_root / "docs" / "troubleshooting.md",
    }


def _execution_context(repo_root: Path) -> str:
    return "checkout" if _artifact_paths(repo_root)["plugin_manifest"].exists() else "tool_install"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _existing_path(path: Path) -> str | None:
    return str(path) if path.exists() else None


def _recommended_docs(repo_root: Path) -> list[str]:
    docs = [
        _artifact_paths(repo_root)["docs_install"],
        _artifact_paths(repo_root)["docs_codex_integration"],
        _artifact_paths(repo_root)["docs_downstream_usage"],
        _artifact_paths(repo_root)["docs_python_sdk"],
        _artifact_paths(repo_root)["docs_troubleshooting"],
    ]
    return [str(path) for path in docs if path.exists()]


def _suggested_destinations(execution_context: str, repo_root: Path) -> dict[str, str]:
    base_dir = repo_root if execution_context == "checkout" else _current_working_dir()
    return {
        "plugin_manifest": str(base_dir / ".codex-plugin" / "plugin.json"),
        "mcp_config": str(base_dir / ".mcp.json"),
    }


def _default_plugin_manifest(skill_source: str) -> dict[str, Any]:
    return {
        "name": "agent-reach",
        "version": __version__,
        "description": "Twitter-only Windows research integration and orchestration suite for Codex.",
        "author": {"name": "Neo Reid"},
        "license": "MIT",
        "keywords": [
            "codex",
            "windows",
            "research",
            "twitter",
            "diagnostics",
            "integration",
        ],
        "skills": skill_source,
        "interface": {
            "displayName": "Agent Reach",
            "shortDescription": "Twitter-only Agent Reach integration for Codex",
            "longDescription": (
                "Bootstraps, documents, diagnoses, and exposes thin read-only "
                "Twitter/X collection plus in-session orchestration skills for Codex."
            ),
            "developerName": "Neo Reid",
            "category": "Developer Tools",
            "capabilities": ["Readiness", "Registry", "Collection", "Orchestration"],
            "defaultPrompt": [
                "Using Agent Reach, show me whether Twitter/X collection is ready on this Windows machine.",
                "Using Agent Reach, turn this Twitter/X research request into a bounded execution plan that keeps artifacts small.",
                "Using Agent Reach, turn this rough Twitter/X research request into a structured brief.",
                "Using Agent Reach, take this rough Twitter/X research ask and start the collection workflow.",
            ],
            "brandColor": "#0F766E",
        },
    }


def _plugin_manifest_inline(
    repo_root: Path,
    execution_context: str,
    skill_source: str,
) -> dict[str, Any]:
    payload = _read_json(_artifact_paths(repo_root)["plugin_manifest"])
    if payload is not None and execution_context == "checkout":
        return payload
    return _default_plugin_manifest(skill_source)


def _documentation_summary() -> list[str]:
    return [
        f"Install the latest Twitter-only fork from `{FORK_REPO_URL}` or pin a commit/ref when reproducibility matters.",
        "`agent-reach skill --install` installs the bundled Codex skill suite for Twitter/X diagnostics, shaping, planning, orchestration, and maintainer workflows.",
        "Use Agent Reach only when the user explicitly asks for Agent Reach or one of its bundled skills; otherwise prefer the model's native browsing/search for lightweight lookups.",
        "Use `agent-reach collect --json` as the primary external interface in arbitrary projects.",
        "Let the caller choose request scale, ranking, summarization, and posting; Agent Reach exposes a Twitter/X collection capability but does not choose scope for the caller.",
        "Inspect `agent-reach channels --json` operation contracts before choosing `since` or `until` for Twitter/X search.",
        "Use `agent-reach doctor --json --probe` when downstream automation needs live Twitter/X operation readiness rather than authenticated-only status.",
        "Use `agent-reach ledger validate`, `ledger summarize`, `ledger query`, and `plan candidates` for evidence-ledger workflows.",
        "Use `agent-reach check-update --json` as an upstream Agent Reach release check; this fork can intentionally diverge from upstream.",
    ]


def _inline_payload_notes() -> list[str]:
    return [
        "Write `plugin_manifest_inline` to `suggested_destinations.plugin_manifest` when downstream tooling needs a repo-local Codex plugin manifest.",
        "This Twitter-only fork does not require a repo-local `.mcp.json` payload.",
    ]


def _readiness_controls() -> dict[str, Any]:
    return {
        "doctor_args": [
            "--require-channel <name>",
            "--require-channels <a,b>",
            "--require-all",
        ],
        "summary_fields": [
            "required_channels",
            "required_not_ready",
            "informational_not_ready",
            "probe_attention",
        ],
        "notes": [
            "Agent Reach does not impose a fixed required-channel set.",
            "Downstream tools choose whether Twitter/X must be ready for a given run.",
            "Without `--require-*`, doctor stays in diagnostic-only mode.",
        ],
    }


def _external_project_usage() -> dict[str, Any]:
    return {
        "copy_files_required": False,
        "preferred_interface": "agent-reach collect --json",
        "codex_global_install": {
            "commands": [
                f"uv tool install --force git+{FORK_REPO_URL}",
                "agent-reach skill --install",
                "agent-reach doctor --json --probe",
            ],
            "notes": [
                "Use Agent Reach only when the user explicitly asks for Agent Reach or one of its bundled skills.",
                "The skill install writes the bundled skill suite to the user's Codex skill home, not to the downstream project.",
                "Downstream projects do not need `.codex-plugin`, `.mcp.json`, or `agent_reach/skills` files when using the CLI.",
            ],
        },
        "github_actions": {
            "uses": "iwachacha/twitter-reach/.github/actions/setup-agent-reach@main",
            "notes": [
                "Use the composite action to install the CLI in the workflow without vendoring repo files.",
                "Pin `uses` to a tag or commit for reproducible automation.",
            ],
        },
        "discord_bot": {
            "recommended_pattern": "subprocess collector",
            "notes": [
                "Call `agent-reach collect --json` and map Twitter/X items into the bot's normalized item type.",
                "Use `--save .agent-reach/evidence.jsonl` when the bot or CI job needs a raw evidence artifact.",
                "Use `agent-reach plan candidates` when the bot or CI job wants a no-model dedupe pass before deeper reads.",
            ],
        },
    }


def _request_scale_policy() -> dict[str, Any]:
    return {
        "principle": (
            "Agent Reach exposes a Twitter/X collection capability. The calling workflow chooses "
            "scope, time windows, ranking, summarization, and posting."
        ),
        "rules": [
            "Agent Reach does not choose request scale, collection routes, ranking, summarization, or posting.",
            "Keep light requests light; do not auto-escalate a narrow ask into large-scale research.",
            "`collect --json` remains the default interface for thin downstream collection.",
            "`batch` and `scout` are explicit opt-in helpers, not the default route for everyday collection.",
            "`plan candidates` keeps its default `--limit 20`; raise it only when the caller explicitly wants a wider review set.",
            "Large-scale research is explicit opt-in and should be requested by the caller or host workflow.",
        ],
        "single_collect": {
            "intent": "narrow asks and lightweight verification",
            "pattern": "single normalized collect or read",
            "recommended_commands": [
                "Run one `agent-reach collect --json` command, or a very small caller-chosen set of Twitter/X collection commands.",
                "Do not reach for `batch`, `scout`, or evidence-ledger fan-out unless the caller explicitly asks for a broader run.",
            ],
        },
        "bounded_multi_source": {
            "intent": "small timeline slices and targeted cross-checks",
            "pattern": "caller-chosen small multi-collect run",
            "recommended_commands": [
                "Use a small number of `collect --json` calls across Twitter/X operations that match the task.",
                "Choose `since` and `until` from the live operation contract only when the caller wants them.",
            ],
        },
        "large_scale_research": {
            "intent": "explicit opt-in broad Twitter/X collection runs",
            "pattern": "bounded fan-out with normalized JSON handoff",
            "explicit_opt_in": True,
            "steps": [
                "Start with 2-4 caller-chosen discovery queries at small limits such as 5-10.",
                "Inspect `channels --json` operation contracts and choose any `since` or `until` bounds downstream instead of relying on a fixed route.",
                "Run `agent-reach batch --plan PLAN.json --validate-only --json` before executing a saved batch plan.",
                "Append raw collection envelopes with `--save .agent-reach/evidence.jsonl` when traceability matters.",
                "Run `agent-reach ledger summarize --input .agent-reach/evidence.jsonl --json` when downstream automation needs neutral artifact health counts.",
                "Run `agent-reach plan candidates --input .agent-reach/evidence.jsonl --by normalized_url --limit 20 --json` for no-model dedupe.",
            ],
            "recommended_limits": {
                "discovery": 10,
                "source_specific_search": 20,
                "deep_reads_per_round": 10,
            },
        },
    }


def _codex_runtime_policy() -> dict[str, Any]:
    request_scale_policy = _request_scale_policy()
    return {
        "default_interface": "agent-reach collect --json",
        "activation_policy": {
            "explicit_user_opt_in_only": True,
            "rule": "Use Agent Reach only when the user explicitly asks for Agent Reach or names one of its bundled skills.",
            "light_search_fallback": "Use the model's native browsing/search for ordinary lightweight lookups instead of Agent Reach.",
        },
        "no_copy_rule": (
            "Use the globally installed CLI and skill suite. Do not copy `.codex-plugin`, `.mcp.json`, "
            "or Agent Reach source files into a downstream repository unless the user explicitly asks for repo-local artifacts."
        ),
        "decision_order": [
            "Before invoking Agent Reach, confirm that the user explicitly asked for Agent Reach or one of its bundled skills.",
            "If readiness is unknown, run `agent-reach channels --json` and `agent-reach doctor --json` first.",
            "Read `doctor.summary.required_not_ready`, `doctor.summary.informational_not_ready`, and `doctor.summary.probe_attention`; let the caller choose `--require-channel`, `--require-channels`, or `--require-all` for the run.",
            "Let the caller choose request scale first: keep narrow asks as `collect`, use bounded multi-collect runs only when needed, and treat large-scale research as explicit opt-in.",
            "Inspect the live channel contract and let the calling workflow choose Twitter/X operations for the task.",
            "Inspect `operation_contracts` and let the calling workflow choose `since` or `until` when Twitter/X search needs bounded windows.",
            "Use Twitter/X only when configured credentials and `doctor --json --probe` show the required operation is ready.",
            "Keep ranking, summarization, scheduling, publishing, and state in the downstream project.",
        ],
        "request_scale_policy": request_scale_policy,
        "large_scale_research": request_scale_policy["large_scale_research"],
        "failure_policy": [
            "Do not fall back to backend-specific CLIs unless debugging a failed Agent Reach operation.",
            "If `doctor --json` marks Twitter/X warn or off and that channel is required, surface the readiness gap clearly.",
            "Inspect `doctor.summary.probe_attention` before assuming probe coverage is complete.",
            "For Twitter/X, authenticated-but-unprobed `warn` means collection may work but operation readiness is unverified until `doctor --json --probe`.",
        ],
    }


def _verification_commands(profile: str) -> list[str]:
    if profile == "runtime-minimal":
        return [
            "agent-reach channels --json",
            "agent-reach doctor --json",
            'agent-reach collect --channel twitter --operation search --input "OpenAI" --limit 3 --json',
            "agent-reach export-integration --client codex --format json --profile runtime-minimal",
        ]
    return [
        "agent-reach channels --json",
        "agent-reach doctor --json",
        "agent-reach doctor --json --probe",
        'agent-reach collect --channel twitter --operation search --input "OpenAI" --limit 3 --json',
        'agent-reach collect --channel twitter --operation user --input "openai" --json',
        'agent-reach collect --channel twitter --operation tweet --input "https://x.com/OpenAI/status/2042296046009626989" --limit 20 --json',
        "agent-reach export-integration --client codex --format json",
        "agent-reach export-integration --client codex --format json --profile runtime-minimal",
    ]


def _runtime_minimal_export(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload["schema_version"],
        "generated_at": payload["generated_at"],
        "client": payload["client"],
        "platform": payload["platform"],
        "profile": "runtime-minimal",
        "execution_context": payload["execution_context"],
        "positioning": ["integration_helper", "runtime_policy"],
        "channel_names": [channel["name"] for channel in payload["channels"]],
        "required_commands": payload["required_commands"],
        "skill": {
            "source": payload["skill"]["source"],
            "names": list(payload["skill"]["names"]),
        },
        "readiness_controls": payload["readiness_controls"],
        "codex_runtime_policy": payload["codex_runtime_policy"],
        "verification_commands": _verification_commands("runtime-minimal"),
        "notes": [
            "runtime-minimal omits full channel contracts, inline Codex artifact payloads, and doc path lists to keep downstream runtime guidance compact.",
            "Use the default full profile when bootstrap tooling needs repo artifact paths or the complete channel contract.",
        ],
    }


def export_codex_integration(profile: str = "full") -> dict[str, Any]:
    """Return the stable integration payload for Codex on Windows."""

    if profile not in INTEGRATION_PROFILES:
        raise ValueError(f"Unsupported Codex integration profile: {profile}")

    repo_root = _repo_root()
    execution_context = _execution_context(repo_root)
    artifact_paths = _artifact_paths(repo_root)
    channels = get_all_channel_contracts()
    skill_source = str(packaged_skill_source())
    suggested_destinations = _suggested_destinations(execution_context, repo_root)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "client": "codex",
        "platform": "windows",
        "profile": "full",
        "execution_context": execution_context,
        "positioning": [
            "bootstrapper",
            "channel_registry",
            "readiness_layer",
            "integration_helper",
        ],
        "channels": channels,
        "required_commands": _required_commands(channels),
        "skill": {
            "source": skill_source,
            "names": list(PACKAGED_SKILL_NAMES),
            "targets": [str(path) for path in _candidate_skill_targets()],
        },
        "plugin_manifest": _existing_path(artifact_paths["plugin_manifest"]),
        "plugin_manifest_inline": _plugin_manifest_inline(repo_root, execution_context, skill_source),
        "mcp_config": _existing_path(artifact_paths["mcp_config"]),
        "mcp_config_inline": None,
        "suggested_destinations": suggested_destinations,
        "inline_payload_notes": _inline_payload_notes(),
        "readiness_controls": _readiness_controls(),
        "external_project_usage": _external_project_usage(),
        "codex_runtime_policy": _codex_runtime_policy(),
        "verification_commands": _verification_commands("full"),
        "python_sdk": {
            "availability": "project_env_only",
            "import": "from agent_reach import AgentReachClient",
            "install_examples": [
                "uv pip install -e C:\\path\\to\\twitter-reach",
                "uv pip install C:\\path\\to\\dist\\agent_reach-<version>-py3-none-any.whl",
            ],
            "quickstart": [
                "from agent_reach import AgentReachClient",
                "client = AgentReachClient()",
                'client.twitter.user_posts("openai", limit=5)',
                'client.collect("twitter", "search", "OpenAI", limit=5, since="2026-01-01", until="2026-12-31")',
            ],
            "notes": [
                "Use namespace helpers for simple default operations.",
                "Use `client.collect(...)` when the caller wants to choose per-operation options from the live contract.",
            ],
        },
        "recommended_docs": _recommended_docs(repo_root),
        "documentation_summary": _documentation_summary(),
    }
    if profile == "runtime-minimal":
        return _runtime_minimal_export(payload)
    return payload


def render_codex_integration_text(payload: dict[str, Any]) -> str:
    """Render a human-readable integration summary."""

    channel_names = [channel["name"] for channel in payload.get("channels", [])]
    if not channel_names:
        channel_names = list(payload.get("channel_names", []))

    lines = [
        "Agent Reach integration export for Codex on Windows",
        "========================================",
        "",
        f"Execution context: {payload['execution_context']}",
        f"Profile: {payload['profile']}",
        f"Channels: {', '.join(channel_names) if channel_names else 'none'}",
        "",
    ]
    plugin_manifest = payload.get("plugin_manifest")
    suggested_destinations = payload.get("suggested_destinations", {})
    if plugin_manifest:
        lines.append(f"Plugin manifest: {plugin_manifest}")
    elif suggested_destinations.get("plugin_manifest"):
        lines.append("Plugin manifest: not bundled in this install")
        lines.append(f"Suggested destination: {suggested_destinations['plugin_manifest']}")
    else:
        lines.append("Plugin manifest: unavailable")

    lines.append(f"Skill source: {payload['skill']['source']}")
    lines.append("Skill targets:")
    for target in payload["skill"].get("targets", []):
        lines.append(f"  {target}")

    recommended_docs = payload.get("recommended_docs", [])
    if recommended_docs:
        lines.extend(["", "Recommended docs:"])
        for path in recommended_docs:
            lines.append(f"  {path}")
    else:
        lines.extend(["", "Documentation summary:"])
        for line in payload.get("documentation_summary", []):
            lines.append(f"  {line}")

    lines.extend(["", "Required commands:"])
    for command in payload.get("required_commands", []):
        lines.append(f"  {command}")

    lines.extend(["", "Verification commands:"])
    for command in payload.get("verification_commands", []):
        lines.append(f"  {command}")
    return "\n".join(lines)


def render_codex_integration_powershell(payload: dict[str, Any]) -> str:
    """Render a PowerShell-oriented export snippet."""

    skill_targets = ",\n".join(f'  "{target}"' for target in payload["skill"].get("targets", []))
    plugin_manifest_json = json.dumps(payload.get("plugin_manifest_inline"), indent=2, ensure_ascii=False)
    plugin_manifest_path = payload.get("plugin_manifest") or payload["suggested_destinations"]["plugin_manifest"]
    return "\n".join(
        [
            "# Agent Reach integration export for Codex on Windows",
            f'$executionContext = "{payload["execution_context"]}"',
            f'$profile = "{payload["profile"]}"',
            f'$pluginManifestPath = "{plugin_manifest_path}"',
            f'$skillSource = "{payload["skill"]["source"]}"',
            "$skillTargets = @(",
            skill_targets,
            ")",
            "",
            "# Write the inline plugin manifest if the file does not exist yet.",
            "$pluginManifestJson = @'",
            plugin_manifest_json,
            "'@",
            "",
            "# This Twitter-only fork does not ship a repo-local .mcp.json payload.",
            "$mcpConfigJson = $null",
            "",
            "# Verification commands",
            *payload.get("verification_commands", []),
        ]
    )


__all__ = [
    "FORK_REPO_URL",
    "INTEGRATION_PROFILES",
    "PACKAGED_SKILL_NAMES",
    "export_codex_integration",
    "render_codex_integration_powershell",
    "render_codex_integration_text",
    "packaged_skill_source",
]
