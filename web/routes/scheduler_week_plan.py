from __future__ import annotations

import importlib
import sys

importlib.import_module('.scheduler', __package__)
_impl = importlib.import_module(".domains.scheduler.scheduler_week_plan", __package__)
sys.modules[__name__] = _impl
