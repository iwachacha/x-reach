# -*- coding: utf-8 -*-
"""Legacy core aliases kept for internal compatibility."""

from x_reach.core import XReach, XReachClient

AgentReach = XReach
AgentReachClient = XReachClient

__all__ = ["AgentReach", "AgentReachClient", "XReach", "XReachClient"]
