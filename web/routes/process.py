"""
工艺管理路由入口文件（保持对外 bp/URL 不变）。

说明：为了降低单文件复杂度，将原 `web/routes/process.py` 按职责拆分：
- `process_bp.py`：bp + 通用中文显示 + Excel 解析工具
- `process_parts.py`：零件/工序模板/外部组
- `process_op_types.py`：工种配置页面
- `process_suppliers.py`：供应商配置页面
- `process_excel_op_types.py`：工种配置 Excel
- `process_excel_suppliers.py`：供应商配置 Excel
- `process_excel_routes.py`：零件工艺路线 Excel
- `process_excel_part_operations.py`：零件工序模板导出
"""

from .process_bp import bp

# 导入子模块以注册路由（side-effect）
from . import process_parts as _parts  # noqa: F401
from . import process_op_types as _op_types  # noqa: F401
from . import process_suppliers as _suppliers  # noqa: F401
from . import process_excel_op_types as _excel_op_types  # noqa: F401
from . import process_excel_suppliers as _excel_suppliers  # noqa: F401
from . import process_excel_routes as _excel_routes  # noqa: F401
from . import process_excel_part_operations as _excel_part_ops  # noqa: F401

__all__ = ["bp"]

