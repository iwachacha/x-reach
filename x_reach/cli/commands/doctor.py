# -*- coding: utf-8 -*-
"""Doctor command handler."""

from __future__ import annotations

import argparse

from x_reach.cli.channel_selection import resolve_doctor_requirements
from x_reach.cli.common import print_json


def register_doctor_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "doctor",
        help="Check supported channel availability; exit-code readiness is diagnostic unless channels are required",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable readiness diagnostics")
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Run lightweight live probes after readiness checks",
    )
    parser.add_argument(
        "--require-channel",
        action="append",
        default=[],
        help="Require this channel to be ready for exit-code/readiness purposes. Repeatable.",
    )
    parser.add_argument(
        "--require-channels",
        help="Comma-separated channel names to require ready for exit-code/readiness purposes",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Require every registered channel to be ready for exit-code/readiness purposes",
    )
    parser.set_defaults(handler=handle_doctor)


def handle_doctor(args) -> int:
    from x_reach.config import Config
    from x_reach.doctor import check_all, doctor_exit_code, format_report, make_doctor_payload

    config = Config()
    required_channels, require_all = resolve_doctor_requirements(args)
    results = check_all(config, probe=args.probe)
    if args.json:
        print_json(
            make_doctor_payload(
                results,
                probe=args.probe,
                required_channels=required_channels,
                require_all=require_all,
            )
        )
    else:
        print(
            format_report(
                results,
                probe=args.probe,
                required_channels=required_channels,
                require_all=require_all,
            )
        )
    return doctor_exit_code(
        results,
        required_channels=required_channels,
        require_all=require_all,
    )
