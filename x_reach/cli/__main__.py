# -*- coding: utf-8 -*-
"""Allow `python -m x_reach.cli` to keep working after package refactor."""

from __future__ import annotations

from x_reach.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
