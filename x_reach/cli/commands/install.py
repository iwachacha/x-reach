# -*- coding: utf-8 -*-
"""Install, skill, and uninstall command handlers."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from x_reach.cli.channel_selection import parse_requested_channels
from x_reach.cli.common import print_json, run
from x_reach.cli.renderers.install import render_install_plan
from x_reach.integrations.codex import (
    LEGACY_PACKAGED_SKILL_NAMES,
    PACKAGED_SKILL_NAMES,
    packaged_skill_source,
)
from x_reach.schemas import SCHEMA_VERSION, utc_timestamp
from x_reach.utils.commands import find_command

CHANNEL_SPECIFIC_INSTALL_CHANNELS = ("twitter",)


def register_install_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p_install = subparsers.add_parser("install", help="Install and configure the supported research stack")
    p_install.add_argument(
        "--env",
        choices=["local", "server", "auto"],
        default="auto",
        help="Environment classification for messaging only",
    )
    p_install.add_argument(
        "--safe",
        action="store_true",
        help="Show the Windows commands that would be run without changing anything",
    )
    p_install.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the install plan without changing anything",
    )
    p_install.add_argument(
        "--channels",
        default="",
        help="Comma-separated channel names to prepare for this environment, or all",
    )
    p_install.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable install plan. Requires --dry-run or --safe",
    )
    p_install.set_defaults(handler=handle_install)

    p_uninstall = subparsers.add_parser("uninstall", help="Remove local X Reach state and skill files")
    p_uninstall.add_argument("--dry-run", action="store_true", help="Preview what would be removed")
    p_uninstall.add_argument(
        "--keep-config",
        action="store_true",
        help="Remove skill files only and keep ~/.x-reach",
    )
    p_uninstall.set_defaults(handler=handle_uninstall)

    p_skill = subparsers.add_parser("skill", help="Install or remove the bundled skill suite")
    skill_group = p_skill.add_mutually_exclusive_group(required=True)
    skill_group.add_argument("--install", action="store_true", help="Install the bundled skill")
    skill_group.add_argument("--uninstall", action="store_true", help="Remove the bundled skill")
    p_skill.set_defaults(handler=handle_skill)


def _build_install_plan_payload(
    env: str,
    requested_channels: list[str],
    dry_run: bool = False,
    safe: bool = False,
) -> dict:
    from x_reach.integrations.codex import export_codex_integration

    integration = export_codex_integration()
    mode = "dry-run" if dry_run else "safe"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "command": "install",
        "mode": mode,
        "environment": env,
        "platform": sys.platform,
        "selected_channels": list(requested_channels),
        "channel_specific_setup_channels": [
            channel for channel in requested_channels if channel in CHANNEL_SPECIFIC_INSTALL_CHANNELS
        ],
        "commands": _manual_install_commands(requested_channels),
        "skill_targets": [str(root / skill_name) for root in _candidate_skill_roots() for skill_name in PACKAGED_SKILL_NAMES],
        "execution_context": integration["execution_context"],
        "plugin_manifest": integration["plugin_manifest"],
        "plugin_manifest_inline": integration["plugin_manifest_inline"],
        "mcp_config": integration["mcp_config"],
        "mcp_config_inline": integration["mcp_config_inline"],
        "suggested_destinations": integration["suggested_destinations"],
        "safe": safe,
        "dry_run": dry_run,
    }


def handle_install(args) -> int:
    from x_reach.config import Config
    from x_reach.doctor import check_all, format_report

    if args.json and not (args.safe or args.dry_run):
        raise SystemExit("install --json is only supported with --dry-run or --safe")

    config = Config()
    requested_channels = parse_requested_channels(args.channels)
    env = args.env if args.env != "auto" else _detect_environment()

    if args.safe or args.dry_run:
        if args.json:
            print_json(
                _build_install_plan_payload(
                    env,
                    requested_channels,
                    dry_run=bool(args.dry_run),
                    safe=bool(args.safe),
                )
            )
        else:
            print(render_install_plan(_manual_install_commands(requested_channels), dry_run=args.dry_run))
        return 0

    print()
    print("X Reach Installer")
    print("========================================")
    print(f"Environment: {env}")
    print(f"Selected channels: {', '.join(requested_channels) if requested_channels else 'none'}")
    print()

    failures: list[str] = []

    if sys.platform != "win32":
        print("This fork is Windows-first, but only the Twitter/X backend install is automated here.")

    if "twitter" in requested_channels and not _install_twitter_deps():
        failures.append("twitter-cli")

    installed_paths = _install_skill()
    print()
    if installed_paths:
        print("Installed skill targets:")
        for path in installed_paths:
            print(f"  {path}")

    print()
    print("Health check:")
    print(format_report(check_all(config)))

    if "twitter" in requested_channels:
        print()
        print("Next step for Twitter/X:")
        print('  x-reach configure twitter-cookies "auth_token=...; ct0=..."')
        print("  Or: x-reach configure --from-browser chrome")

    if failures:
        print()
        print("Some steps still need attention:")
        for item in failures:
            print(f"  - {item}")
        print("Run `x-reach install --safe` to print the exact Windows commands again.")
        return 1

    print()
    print("Install complete.")
    return 0


def _manual_install_commands(requested_channels: list[str]) -> list[str]:
    commands: list[str] = []
    if "twitter" in requested_channels and not find_command("twitter"):
        commands.append("uv tool install twitter-cli")
    commands.append("x-reach skill --install")
    return commands


def _detect_environment() -> str:
    if sys.platform == "win32":
        return "local"
    indicators = [
        os.environ.get("CI"),
        os.environ.get("GITHUB_ACTIONS"),
        os.environ.get("SSH_CONNECTION"),
    ]
    return "server" if any(indicators) else "local"


def _install_twitter_deps() -> bool:
    if find_command("twitter"):
        print("  [OK] twitter-cli already installed")
        return True
    uv = shutil.which("uv")
    if not uv:
        print("  [WARN] uv is missing, so twitter-cli cannot be installed automatically")
        return False
    print("  Installing twitter-cli with uv tool...")
    try:
        run([uv, "tool", "install", "twitter-cli"], timeout=600)
    except Exception as exc:
        print(f"  [WARN] twitter-cli install failed: {exc}")
        return False
    if find_command("twitter"):
        print("  [OK] twitter-cli is ready")
        return True
    print("  [WARN] twitter-cli is still missing after uv tool install")
    return False


def _candidate_skill_roots() -> list[Path]:
    roots: list[Path] = []
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        roots.append(Path(codex_home) / "skills")
    roots.append(Path.home() / ".codex" / "skills")
    roots.append(Path.home() / ".agents" / "skills")

    deduped: list[Path] = []
    seen = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            deduped.append(root)
            seen.add(key)
    return deduped


def _install_skill() -> list[Path]:
    source_dir = packaged_skill_source()
    installed_paths: list[Path] = []
    known_skill_names = [*LEGACY_PACKAGED_SKILL_NAMES, *PACKAGED_SKILL_NAMES]

    existing_roots = [root for root in _candidate_skill_roots() if root.exists()]
    if not existing_roots:
        existing_roots = [_candidate_skill_roots()[0]]

    for root in existing_roots:
        root.mkdir(parents=True, exist_ok=True)
        for skill_name in known_skill_names:
            target = root / skill_name
            if target.exists():
                shutil.rmtree(target)
        for skill_name in PACKAGED_SKILL_NAMES:
            target = root / skill_name
            shutil.copytree(source_dir / skill_name, target)
            installed_paths.append(target)

    return installed_paths


def _uninstall_skill() -> list[Path]:
    removed: list[Path] = []
    known_skill_names = [*LEGACY_PACKAGED_SKILL_NAMES, *PACKAGED_SKILL_NAMES]
    for root in _candidate_skill_roots():
        for skill_name in known_skill_names:
            target = root / skill_name
            if target.exists():
                shutil.rmtree(target)
                removed.append(target)
    return removed


def handle_skill(args) -> int:
    if args.install:
        installed = _install_skill()
        if installed:
            for path in installed:
                print(f"Installed skill: {path}")
        else:
            print("No skill targets were written.")
    elif args.uninstall:
        removed = _uninstall_skill()
        if removed:
            for path in removed:
                print(f"Removed skill: {path}")
        else:
            print("No skill installations found.")
    return 0


def handle_uninstall(args) -> int:
    from x_reach.config import Config

    config_path = Config.CONFIG_FILE
    config_dir = Config.CONFIG_DIR
    legacy_config_path = Config.LEGACY_CONFIG_FILE
    legacy_config_dir = Config.LEGACY_CONFIG_DIR
    skill_names = [*LEGACY_PACKAGED_SKILL_NAMES, *PACKAGED_SKILL_NAMES]
    skill_paths = [root / skill_name for root in _candidate_skill_roots() for skill_name in skill_names]

    if args.dry_run:
        print("Dry-run uninstall plan:")
        if not args.keep_config:
            print(f"  Remove config dir: {config_dir}")
            if legacy_config_dir != config_dir:
                print(f"  Remove legacy config dir: {legacy_config_dir}")
        for path in skill_paths:
            if path.exists():
                print(f"  Remove skill: {path}")
        print("  Optional tool cleanup: uv tool uninstall twitter-cli")
        return 0

    removed_any = False
    if not args.keep_config and config_dir.exists():
        shutil.rmtree(config_dir)
        print(f"Removed config dir: {config_dir}")
        removed_any = True
    elif not args.keep_config and config_path.exists():
        config_path.unlink(missing_ok=True)

    if not args.keep_config and legacy_config_dir != config_dir and legacy_config_dir.exists():
        shutil.rmtree(legacy_config_dir)
        print(f"Removed legacy config dir: {legacy_config_dir}")
        removed_any = True
    elif not args.keep_config and legacy_config_path != config_path and legacy_config_path.exists():
        legacy_config_path.unlink(missing_ok=True)

    for path in skill_paths:
        if path.exists():
            shutil.rmtree(path)
            print(f"Removed skill: {path}")
            removed_any = True

    if not removed_any:
        print("Nothing to remove.")
        return 0

    print()
    print("Optional tool cleanup:")
    print("  uv tool uninstall twitter-cli")
    return 0
