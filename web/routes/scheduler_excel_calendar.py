from __future__ import annotations

import sys

from ._scheduler_compat import load_scheduler_route_module

_impl = load_scheduler_route_module(".domains.scheduler.scheduler_excel_calendar")
sys.modules[__name__] = _impl
