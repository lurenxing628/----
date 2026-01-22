"""
排产调度路由入口文件（保持对外 bp/URL 不变）。

说明：为了降低单文件复杂度，把原 `web/routes/scheduler.py` 按职责拆分：
- `scheduler_bp.py`：bp + 通用中文显示
- `scheduler_pages.py`：页面与非 Excel 路由
- `scheduler_excel_calendar.py`：工作日历 Excel
- `scheduler_excel_batches.py`：批次 Excel
"""

from .scheduler_bp import bp

# 导入子模块以注册路由（side-effect）
from . import scheduler_pages as _pages  # noqa: F401
from . import scheduler_excel_calendar as _excel_calendar  # noqa: F401
from . import scheduler_excel_batches as _excel_batches  # noqa: F401

__all__ = ["bp"]

