# -*- coding: utf-8 -*-
"""Thin main entrypoint for the CLI package."""

from __future__ import annotations

from collections.abc import Sequence

from x_reach.cli.common import configure_logging, ensure_utf8_console
from x_reach.cli.dispatch import dispatch
from x_reach.cli.parser import build_parser


def main(argv: Sequence[str] | None = None) -> int:
    ensure_utf8_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(getattr(args, "verbose", False))
    return dispatch(args, parser)
