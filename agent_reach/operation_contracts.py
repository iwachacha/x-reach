# -*- coding: utf-8 -*-
# Compatibility wrapper around x_reach.operation_contracts.

import sys
from importlib import import_module

sys.modules[__name__] = import_module('x_reach.operation_contracts')

