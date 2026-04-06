from __future__ import annotations

from . import scheduler_analysis as _analysis  # noqa: F401
from . import scheduler_batch_detail as _batch_detail  # noqa: F401

# 拆分后的路由模块：通过 import side-effect 注册到同一个 bp
from . import scheduler_batches as _batches  # noqa: F401
from . import scheduler_calendar_pages as _calendar_pages  # noqa: F401
from . import scheduler_config as _config  # noqa: F401
from . import scheduler_ops as _ops  # noqa: F401
from . import scheduler_resource_dispatch as _resource_dispatch  # noqa: F401
from . import scheduler_run as _run  # noqa: F401
from .scheduler_bp import bp

__all__ = ["bp"]

