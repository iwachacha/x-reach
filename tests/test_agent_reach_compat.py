# -*- coding: utf-8 -*-
"""Focused regression coverage for the legacy agent_reach shim."""

from importlib import import_module

import agent_reach
import x_reach


def test_agent_reach_package_aliases_primary_sdk_surface():
    assert agent_reach.__version__ == x_reach.__version__
    assert agent_reach.XReachClient is x_reach.XReachClient
    assert agent_reach.AgentReachClient is x_reach.XReachClient
    assert agent_reach.XReach is x_reach.XReach
    assert agent_reach.AgentReach is x_reach.XReach


def test_agent_reach_wrapper_modules_resolve_to_x_reach_modules():
    assert import_module("agent_reach.cli") is import_module("x_reach.cli")
    assert import_module("agent_reach.results") is import_module("x_reach.results")
    assert import_module("agent_reach.channels") is import_module("x_reach.channels")


def test_agent_reach_cli_main_still_runs_primary_entrypoint(capsys):
    legacy_cli = import_module("agent_reach.cli")
    primary_cli = import_module("x_reach.cli")

    assert legacy_cli.main is primary_cli.main
    assert legacy_cli.main(["version"]) == 0
    assert "X Reach v" in capsys.readouterr().out
