# -*- coding: utf-8 -*-
"""Public CLI package surface."""

from x_reach.cli.commands.configure import _parse_twitter_cookie_input
from x_reach.cli.commands.install import _candidate_skill_roots, _install_skill, _uninstall_skill
from x_reach.cli.main import main
from x_reach.cli.parser import build_parser

_build_parser = build_parser

__all__ = [
    "main",
    "build_parser",
    "_build_parser",
    "_candidate_skill_roots",
    "_install_skill",
    "_uninstall_skill",
    "_parse_twitter_cookie_input",
]
