"""
工艺管理模块（Process）。

说明：
- 服务层只依赖 repositories，不在路由里写复杂业务逻辑
- 用户可见 message 尽量中文（便于 Win7 单机用户排障）
"""

from __future__ import annotations

from .deletion_validator import DeletionCheckResult, DeletionValidator, ValidationResult
from .external_group_service import ExternalGroupService
from .op_type_service import OpTypeService
from .part_service import PartService
from .route_parser import ParseResult, ParseStatus, RouteParser
from .supplier_service import SupplierService
from .unit_excel_converter import ConvertedTemplates, UnitExcelConverter

__all__ = [
    "OpTypeService",
    "SupplierService",
    "PartService",
    "ExternalGroupService",
    "RouteParser",
    "ParseResult",
    "ParseStatus",
    "DeletionValidator",
    "DeletionCheckResult",
    "ValidationResult",
    "UnitExcelConverter",
    "ConvertedTemplates",
]

