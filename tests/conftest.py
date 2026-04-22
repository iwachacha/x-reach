# -*- coding: utf-8 -*-
"""Pytest test-path bootstrap for local package imports."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_TEXT = str(ROOT)
if ROOT_TEXT in sys.path:
    sys.path.remove(ROOT_TEXT)
sys.path.insert(0, ROOT_TEXT)
