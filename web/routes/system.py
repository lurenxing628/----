"""
系统管理路由入口文件（保持对外 bp/URL 不变）。

说明：为了降低单文件复杂度，将原 `web/routes/system.py` 按职责拆分：
- `system_bp.py`：bp
- `system_utils.py`：纯工具函数（安全跳转、时间解析、备份文件名校验等）
- `system_ui_mode.py`：UI 模式切换
- `system_backup.py`：备份/恢复相关页面与操作
- `system_plugins.py`：插件开关
- `system_logs.py`：操作日志查询/清理
- `system_history.py`：排产历史查询
"""

from __future__ import annotations

from . import system_backup as _backup  # noqa: F401
from . import system_history as _history  # noqa: F401
from . import system_logs as _logs  # noqa: F401
from . import system_plugins as _plugins  # noqa: F401

# 导入子模块以注册路由（side-effect）
from . import system_ui_mode as _ui_mode  # noqa: F401
from .system_bp import bp

__all__ = ["bp"]

