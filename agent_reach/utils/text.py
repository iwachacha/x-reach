# -*- coding: utf-8 -*-
# Compatibility wrapper around x_reach.utils.text.

from importlib import import_module
import sys

sys.modules[__name__] = import_module('x_reach.utils.text')

