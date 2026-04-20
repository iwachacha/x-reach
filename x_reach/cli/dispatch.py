# -*- coding: utf-8 -*-
"""Command dispatch for the CLI package."""

from __future__ import annotations

import argparse


def dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)
