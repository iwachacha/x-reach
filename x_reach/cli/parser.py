# -*- coding: utf-8 -*-
"""Parser construction and command registration for the CLI package."""

from __future__ import annotations

import argparse

from x_reach import __version__
from x_reach.cli.commands.batch import register_batch_parser
from x_reach.cli.commands.collect import register_collect_parsers
from x_reach.cli.commands.configure import register_configure_parser
from x_reach.cli.commands.doctor import register_doctor_parser
from x_reach.cli.commands.install import register_install_parsers
from x_reach.cli.commands.ledger import register_ledger_parser
from x_reach.cli.commands.metadata import register_metadata_parsers
from x_reach.cli.commands.plan import register_plan_parser
from x_reach.cli.commands.scout import register_scout_parser
from x_reach.cli.commands.update import register_update_parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="x-reach",
        description="Windows-first X/Twitter research tooling for Codex and compatible agents",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show debug logs")
    parser.add_argument("--version", action="version", version=f"X Reach v{__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    register_install_parsers(subparsers)
    register_configure_parser(subparsers)
    register_doctor_parser(subparsers)
    register_collect_parsers(subparsers)
    register_plan_parser(subparsers)
    register_scout_parser(subparsers)
    register_batch_parser(subparsers)
    register_metadata_parsers(subparsers)
    register_ledger_parser(subparsers)
    register_update_parser(subparsers)
    return parser
