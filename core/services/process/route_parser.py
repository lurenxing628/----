from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from core.services.process.route_parser_constraints import SupplierConstraintResolver, SupplierGlobalIssue
from core.services.process.route_parser_tokens import build_numeric_names


@dataclass
class RouteParseContext:
    """一次解析所需的纯数据快照：工种名映射 + 供应商映射/全局问题。

    工艺预览在批量解释工序前构建一次，复用相同工种与供应商事实；
    缓存纯数据，不保留 resolver 实例。
    """

    op_types: Dict[str, Any]
    suppliers: Dict[str, str]
    supplier_global_issues: List[SupplierGlobalIssue]
    numeric_names: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)


class RouteParser:
    """工艺路线解析器（构建工种与供应商解析上下文）。"""

    def __init__(self, op_types_by_id: Dict[str, Any], capabilities: List[Dict[str, Any]], logger=None):
        self.op_types_by_id = op_types_by_id
        self.capabilities = capabilities
        self.logger = logger

    def build_parse_context(self) -> RouteParseContext:
        """一次性构建解析纯数据（工种名映射 + 供应商映射/全局问题），供批量解析循环外复用。"""
        op_types = {ot.name: ot for ot in self.op_types_by_id.values()}
        resolver = SupplierConstraintResolver(
            self.op_types_by_id,
            self.capabilities,
            logger=self.logger,
        )
        suppliers = resolver.build_supplier_map()
        return RouteParseContext(
            op_types=op_types,
            suppliers=suppliers,
            supplier_global_issues=resolver.global_issues,
            numeric_names=build_numeric_names(op_types),
        )
