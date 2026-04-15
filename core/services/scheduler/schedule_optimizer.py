from __future__ import annotations

import importlib
import sys

_impl = importlib.import_module(".run.schedule_optimizer", __package__)
sys.modules[__name__] = _impl
