"""
工艺管理模块（Process）。

说明：
- 服务层只依赖 repositories，不在路由里写复杂业务逻辑
- 用户可见 message 尽量中文（便于 Win7 单机用户排障）
"""

from .op_type_service import OpTypeService
from .supplier_service import SupplierService
from .part_service import PartService
from .external_group_service import ExternalGroupService
from .route_parser import RouteParser, ParseResult, ParseStatus
from .deletion_validator import DeletionValidator, DeletionCheckResult, ValidationResult

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
]

