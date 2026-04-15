# -*- coding: utf-8 -*-
"""External-facing collection adapters."""

from __future__ import annotations

from typing import Type

from x_reach.config import Config

from .base import BaseAdapter
from .twitter import TwitterAdapter

ADAPTERS: dict[str, Type[BaseAdapter]] = {
    "twitter": TwitterAdapter,
}


def get_adapter(name: str, config: Config | None = None) -> BaseAdapter | None:
    """Return a configured adapter for the requested channel."""

    adapter_cls = ADAPTERS.get(name)
    if adapter_cls is None:
        return None
    return adapter_cls(config=config)


__all__ = [
    "ADAPTERS",
    "BaseAdapter",
    "TwitterAdapter",
    "get_adapter",
]

