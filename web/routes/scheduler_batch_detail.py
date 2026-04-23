from __future__ import annotations

import sys

from ._scheduler_compat import load_scheduler_route_module

_impl = load_scheduler_route_module(".domains.scheduler.scheduler_batch_detail")
sys.modules[__name__] = _impl
