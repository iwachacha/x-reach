# -*- coding: utf-8 -*-
# Compatibility wrapper around x_reach.scout.

from importlib import import_module
import sys

sys.modules[__name__] = import_module('x_reach.scout')

