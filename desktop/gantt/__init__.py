"""
PyQt 甘特图 PoC（只读）模块。

说明：
- 复用 `core.services.scheduler.gantt_contract` 契约；
- 不依赖 Web 路由，直接调用服务层数据。
"""

from .contract_client import GanttDesktopDataProvider
from .pyqt_poc import GanttPyQtUnavailableError, launch_gantt_poc

__all__ = ["GanttDesktopDataProvider", "launch_gantt_poc", "GanttPyQtUnavailableError"]

