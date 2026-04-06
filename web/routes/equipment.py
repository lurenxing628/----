"""
设备管理路由入口文件（保持对外 bp/URL 不变）。

说明：为了降低单文件复杂度，将原 `web/routes/equipment.py` 按职责拆分：
- `equipment_bp.py`：bp + 通用中文显示 + Excel 解析工具
- `equipment_pages.py`：设备页面/CRUD/关联
- `equipment_downtimes.py`：停机计划（批量/单机）
- `equipment_excel_machines.py`：设备信息 Excel
- `equipment_excel_links.py`：设备人员关联 Excel
"""

from __future__ import annotations

from . import equipment_downtimes as _downtimes  # noqa: F401
from . import equipment_excel_links as _excel_links  # noqa: F401
from . import equipment_excel_machines as _excel_machines  # noqa: F401

# 导入子模块以注册路由（side-effect）
from . import equipment_pages as _pages  # noqa: F401
from .equipment_bp import bp

__all__ = ["bp"]

