# -*- coding: utf-8 -*-
# Compatibility wrapper around x_reach.batch.

from importlib import import_module
import sys

sys.modules[__name__] = import_module('x_reach.batch')

