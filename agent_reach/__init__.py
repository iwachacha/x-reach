# -*- coding: utf-8 -*-
"""Legacy compatibility surface for agent_reach imports."""

from x_reach._version import __version__
from x_reach.core import XReach, XReachClient

AgentReachClient = XReachClient
AgentReach = XReach

__all__ = ["AgentReach", "AgentReachClient", "XReach", "XReachClient", "__version__"]
