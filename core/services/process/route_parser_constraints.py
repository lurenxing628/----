from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from core.models.enums import SupplierStatus
from core.services.common.enum_normalizers import normalize_supplier_status
from core.services.common.safe_logging import safe_warning
from core.services.process.route_parser_errors import (
    supplier_blank_days_warning,
    supplier_invalid_days_warning,
    supplier_missing_days_warning,
    supplier_unparseable_days_warning,
)


class SupplierConstraintResolver:
    def __init__(self, op_types_repo, suppliers_repo, logger=None) -> None:
        self.op_types_repo = op_types_repo
        self.suppliers_repo = suppliers_repo
        self.logger = logger

    def build_supplier_map(self) -> Tuple[Dict[str, Tuple[str, float]], Dict[str, List[str]]]:
        """
        构建 工种名 -> (supplier_id, default_days) 映射。
        规则：仅使用 Suppliers.op_type_id 有值且能映射到 OpTypes 的记录；
        若同一工种存在多条供应商记录，则按 supplier_id 字典序取最后一条
        （即 supplier_id 最大者）作为有效供应商，与预览基线保持一致。
        """
        supplier_map: Dict[str, Tuple[str, float]] = {}
        issues: Dict[str, List[str]] = {}
        try:
            suppliers = self.suppliers_repo.list(status=SupplierStatus.ACTIVE.value) or []
        except TypeError:
            suppliers = self.suppliers_repo.list() or []
        for supplier in suppliers:
            supplier_status = normalize_supplier_status(getattr(supplier, "status", SupplierStatus.ACTIVE.value))
            if supplier_status != SupplierStatus.ACTIVE.value:
                continue
            if not getattr(supplier, "op_type_id", None):
                continue
            supplier_id = str(getattr(supplier, "supplier_id", "") or "").strip() or "?"
            op_type_name = self._resolve_supplier_op_type_name(supplier, supplier_id)
            if not op_type_name:
                continue
            default_days, issue_messages = self._resolve_supplier_default_days(
                supplier,
                supplier_id=supplier_id,
                op_type_name=op_type_name,
                has_default_days=hasattr(supplier, "default_days"),
            )
            current = supplier_map.get(op_type_name)
            current_supplier_id = None if current is None else str(current[0] or "").strip()
            if not self._candidate_supplier_should_replace_current(current_supplier_id, supplier_id):
                continue
            supplier_map[op_type_name] = (supplier_id, float(default_days))
            if issue_messages:
                issues[op_type_name] = list(issue_messages)
            else:
                # 同一工种按 supplier_id 取“有效供应商”时，必须同步清掉旧候选供应商遗留的错误信息；
                # 否则 strict_mode 可能因为已被淘汰的低优先级供应商而误报/误拒绝。
                issues.pop(op_type_name, None)

        return supplier_map, issues

    def _resolve_supplier_op_type_name(self, supplier: Any, supplier_id: str) -> Optional[str]:
        try:
            op_type = self.op_types_repo.get(supplier.op_type_id)
        except Exception as exc:
            safe_warning(self.logger, f"供应商“{supplier_id}”工种映射加载失败（op_type_id={supplier.op_type_id!r}）：{exc}")
            return None
        name = getattr(op_type, "name", None) if op_type else None
        return str(name) if name else None

    @staticmethod
    def _resolve_supplier_default_days(
        supplier: Any,
        *,
        supplier_id: str,
        op_type_name: str,
        has_default_days: bool,
    ) -> Tuple[float, List[str]]:
        raw_default_days: Any = getattr(supplier, "default_days", None)
        if not has_default_days:
            return 1.0, [supplier_missing_days_warning(supplier_id, op_type_name)]
        if raw_default_days is None or (isinstance(raw_default_days, str) and raw_default_days.strip() == ""):
            return 1.0, [supplier_blank_days_warning(supplier_id, op_type_name)]
        try:
            parsed_default_days = float(raw_default_days)
        except Exception:
            return 1.0, [supplier_unparseable_days_warning(supplier_id, op_type_name)]
        if not math.isfinite(parsed_default_days) or parsed_default_days <= 0:
            return 1.0, [supplier_invalid_days_warning(supplier_id, op_type_name)]
        return float(parsed_default_days), []

    @staticmethod
    def _effective_supplier_order_key(supplier_id: str) -> Tuple[str]:
        return (str(supplier_id or "").strip(),)

    @classmethod
    def _candidate_supplier_should_replace_current(
        cls,
        current_supplier_id: Optional[str],
        candidate_supplier_id: str,
    ) -> bool:
        """
        当前冻结规则：
        - 同一工种出现多个候选供应商时，按 supplier_id 字典序取最大者作为“有效供应商”；
        - 该规则是为了让路线解析、预览基线与确认导入保持同口径；
        - 它表达的是当前兼容排序规则，不等价于更广义的业务优先级。
        """
        if current_supplier_id is None:
            return True
        return cls._effective_supplier_order_key(candidate_supplier_id) > cls._effective_supplier_order_key(current_supplier_id)
