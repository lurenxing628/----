"""
人员管理路由入口文件（保持对外 bp/URL 不变）。

说明：为了降低单文件复杂度，将原 `web/routes/personnel.py` 按职责拆分：
- `personnel_bp.py`：bp + 通用显示/规范化 + Excel 解析工具
- `personnel_pages.py`：人员页面/CRUD/关联
- `personnel_calendar_pages.py`：个人工作日历页面
- `personnel_excel_operators.py`：人员基本信息 Excel
- `personnel_excel_links.py`：人员设备关联 Excel
- `personnel_excel_operator_calendar.py`：人员专属工作日历 Excel
"""

from .personnel_bp import bp

# 导入子模块以注册路由（side-effect）
from . import personnel_pages as _pages  # noqa: F401
from . import personnel_calendar_pages as _calendar_pages  # noqa: F401
from . import personnel_excel_operators as _excel_ops  # noqa: F401
from . import personnel_excel_links as _excel_links  # noqa: F401
from . import personnel_excel_operator_calendar as _excel_op_cal  # noqa: F401

__all__ = ["bp"]

