# -*- coding: utf-8 -*-
"""Legacy SDK aliases kept for internal compatibility."""

from x_reach.client import XReach, XReachClient

AgentReachClient = XReachClient
AgentReach = XReach

__all__ = ["AgentReach", "AgentReachClient", "XReach", "XReachClient"]
