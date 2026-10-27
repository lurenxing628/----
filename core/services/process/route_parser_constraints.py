from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.infrastructure.logging import safe_log
from core.models.resource_capabilities import supports_source


@dataclass(frozen=True)
class SupplierGlobalIssue:
    op_type_id: Optional[str]


class SupplierConstraintResolver:
    def __init__(self, op_types_by_id, capabilities, logger=None) -> None:
        self.capabilities = capabilities
        self.logger = logger
        self.global_issues: List[SupplierGlobalIssue] = []
        self._op_types_by_id = op_types_by_id

    def build_supplier_map(self) -> Dict[str, str]:
        """
        构建 工种名 -> supplier_id 映射。
        规则：使用供应商单独设置的工种关系（WorkbenchSupplierOpTypes）；
        若同一工种存在多条供应商记录，则按 supplier_id 字典序取最后一条
        （即 supplier_id 最大者）作为有效供应商，与预览基线保持一致。
        """
        supplier_map: Dict[str, str] = {}
        for row in self.capabilities:
            if row["missing_supplier"]:
                self.global_issues.append(SupplierGlobalIssue(op_type_id=row["op_type_id"]))
                continue
            supplier_id = str(row["supplier_id"] or "").strip() or "?"
            op_type_name = self._resolve_supplier_op_type_name(row, supplier_id)
            if not op_type_name:
                continue
            current = supplier_map.get(op_type_name)
            if current is not None and supplier_id <= current:
                continue
            supplier_map[op_type_name] = supplier_id

        return supplier_map

    def _resolve_supplier_op_type_name(self, row: Dict[str, Any], supplier_id: str) -> Optional[str]:
        op_type_id = row["op_type_id"]
        op_type = self._op_types_by_id.get(op_type_id)
        name = op_type.name if op_type is not None else None
        if not name:
            message = (
                f"供应商“{supplier_id}”工种映射加载失败（op_type_id={op_type_id!r}），"
                "没有找到对应工种，请检查供应商对应工种。"
            )
            self.global_issues.append(SupplierGlobalIssue(op_type_id=op_type_id))
            safe_log(self.logger, "warning", message)
            return None
        if not supports_source(op_type.category, "external"):
            message = f"供应商“{supplier_id}”工种映射加载失败（op_type_id={op_type_id!r}），关联的工种不是外协工种。"
            self.global_issues.append(SupplierGlobalIssue(op_type_id=op_type_id))
            safe_log(self.logger, "warning", message)
            return None
        return str(name)
