from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import Supplier
from core.services.common.normalize import normalize_text
from data.repositories import OpTypeRepository, SupplierRepository


class SupplierService:
    """供应商服务（Suppliers）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self.repo = SupplierRepository(conn, logger=logger)
        self.op_type_repo = OpTypeRepository(conn, logger=logger)

    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    @staticmethod
    def _normalize_float(value: Any, default: float = 0.0) -> float:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return float(default)
        try:
            return float(value)
        except Exception:
            return float(default)

    def _resolve_op_type_id(self, value: Any) -> Optional[str]:
        """
        解析“对应工种”输入：
        - 允许填写 op_type_id 或 工种名称
        - 允许为空（不绑定）
        """
        v = self._normalize_text(value)
        if not v:
            return None
        ot = self.op_type_repo.get(v)
        if not ot:
            ot = self.op_type_repo.get_by_name(v)
        if not ot:
            raise ValidationError(f"工种“{v}”不存在，请先在工艺管理-工种配置中维护。", field="对应工种")
        return ot.op_type_id

    def _validate_fields(
        self,
        supplier_id: Any,
        name: Any,
        default_days: Any,
        status: Any,
        allow_partial: bool = False,
    ) -> Tuple[Optional[str], Optional[str], Optional[float], Optional[str]]:
        sid = self._normalize_text(supplier_id)
        sname = self._normalize_text(name)
        sstatus = self._normalize_text(status)
        if sstatus is not None:
            sstatus = sstatus.lower()
        sdays = None if default_days is None and allow_partial else self._normalize_float(default_days, default=1.0)

        if not allow_partial:
            if not sid:
                raise ValidationError("“供应商ID”不能为空", field="供应商ID")
            if not sname:
                raise ValidationError("“名称”不能为空", field="名称")
            if sstatus is None:
                sstatus = "active"

        if sstatus is not None and sstatus not in ("active", "inactive"):
            raise ValidationError("“状态”不合法（允许：active / inactive）", field="状态")
        if sdays is not None and sdays <= 0:
            raise ValidationError("“默认周期”必须大于 0", field="默认周期")

        return sid, sname, sdays, sstatus

    def _get_or_raise(self, supplier_id: str) -> Supplier:
        s = self.repo.get(supplier_id)
        if not s:
            raise BusinessError(ErrorCode.NOT_FOUND, f"供应商“{supplier_id}”不存在")
        return s

    def list(self, status: Optional[str] = None, op_type_id: Optional[str] = None) -> List[Supplier]:
        filter_status = None
        if status:
            _, _, _, filter_status = self._validate_fields(None, None, None, status, allow_partial=True)
            if filter_status is None:
                raise ValidationError("缺少状态参数", field="状态")
        if op_type_id:
            ot = self.op_type_repo.get(op_type_id)
            if not ot:
                raise BusinessError(ErrorCode.NOT_FOUND, f"工种“{op_type_id}”不存在")
        return self.repo.list(status=filter_status, op_type_id=op_type_id)

    def get(self, supplier_id: str) -> Supplier:
        sid, _, _, _ = self._validate_fields(supplier_id, None, None, None, allow_partial=True)
        if not sid:
            raise ValidationError("“供应商ID”不能为空", field="供应商ID")
        return self._get_or_raise(sid)

    def get_optional(self, supplier_id: Any) -> Optional[Supplier]:
        """
        宽松查询：找不到返回 None（用于页面回显“已删除/已停用”资源）。
        """
        sid, _, _, _ = self._validate_fields(supplier_id, None, None, None, allow_partial=True)
        if not sid:
            return None
        return self.repo.get(sid)

    def create(
        self,
        supplier_id: Any,
        name: Any,
        op_type_value: Any = None,
        default_days: Any = 1.0,
        status: Any = "active",
        remark: Any = None,
    ) -> Supplier:
        sid, sname, sdays, sstatus = self._validate_fields(supplier_id, name, default_days, status)
        op_type_id = self._resolve_op_type_id(op_type_value) if op_type_value is not None else None
        sremark = self._normalize_text(remark)

        if self.repo.get(sid):
            raise BusinessError(ErrorCode.DUPLICATE_ENTRY, f"供应商ID“{sid}”已存在，不能重复添加。")

        with self.tx_manager.transaction():
            self.repo.create(
                {
                    "supplier_id": sid,
                    "name": sname,
                    "op_type_id": op_type_id,
                    "default_days": float(sdays or 1.0),
                    "status": sstatus or "active",
                    "remark": sremark,
                }
            )
        return self._get_or_raise(sid)

    def update(
        self,
        supplier_id: Any,
        name: Any = None,
        op_type_value: Any = None,
        default_days: Any = None,
        status: Any = None,
        remark: Any = None,
    ) -> Supplier:
        sid, sname, sdays, sstatus = self._validate_fields(supplier_id, name, default_days, status, allow_partial=True)
        if not sid:
            raise ValidationError("“供应商ID”不能为空", field="供应商ID")
        self._get_or_raise(sid)

        updates: Dict[str, Any] = {}
        if sname is not None:
            if not sname:
                raise ValidationError("“名称”不能为空", field="名称")
            updates["name"] = sname
        if status is not None:
            updates["status"] = sstatus
        if default_days is not None:
            updates["default_days"] = float(sdays or 1.0)
        if op_type_value is not None:
            # 允许显式清空：传空字符串/None
            updates["op_type_id"] = self._resolve_op_type_id(op_type_value)
        if remark is not None:
            updates["remark"] = self._normalize_text(remark)

        with self.tx_manager.transaction():
            self.repo.update(sid, updates)
        return self._get_or_raise(sid)

    def delete(self, supplier_id: Any) -> None:
        sid, _, _, _ = self._validate_fields(supplier_id, None, None, None, allow_partial=True)
        if not sid:
            raise ValidationError("“供应商ID”不能为空", field="供应商ID")
        self._get_or_raise(sid)

        # 若被引用，则禁止删除（模板/批次工序）
        if self.repo.has_part_operation_reference(sid):
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "该供应商已被零件工序模板引用，不能删除。建议改为“停用”。")
        if self.repo.has_batch_operation_reference(sid):
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "该供应商已被批次工序引用，不能删除。建议改为“停用”。")
        if self.repo.has_external_group_reference(sid):
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "该供应商已被外部工序组引用，不能删除。建议改为“停用”。")

        with self.tx_manager.transaction():
            self.repo.delete(sid)

    # -------------------------
    # Excel 辅助
    # -------------------------
    def build_existing_for_excel(self) -> Dict[str, Dict[str, Any]]:
        op_types = {ot.op_type_id: ot for ot in self.op_type_repo.list()}
        existing: Dict[str, Dict[str, Any]] = {}
        for s in self.repo.list():
            ot = op_types.get(s.op_type_id or "")
            existing[s.supplier_id] = {
                "供应商ID": s.supplier_id,
                "名称": s.name,
                "对应工种": (ot.name if ot else None),
                "默认周期": s.default_days,
                "状态": s.status,
                "备注": s.remark,
            }
        return existing

    def list_for_export_rows(self) -> List[Dict[str, Any]]:
        """
        供 Excel 导出使用的扁平行（含 op_type_name）。

        返回字段由 SupplierRepository.list_for_export() 定义：
        - supplier_id, name, default_days, status, remark, op_type_name
        """
        return self.repo.list_for_export()

    def ensure_replace_allowed(self) -> None:
        """
        REPLACE（清空后导入）保护：
        若已被零件模板/批次工序/外部组引用，则禁止清空。
        """
        if self.repo.has_any_part_operation_reference():
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "已有零件工序模板引用了供应商，不能执行“替换（清空后导入）”。请先解除引用或改用“覆盖/追加”。")
        if self.repo.has_any_batch_operation_reference():
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "已有批次工序引用了供应商，不能执行“替换（清空后导入）”。请先解除引用或改用“覆盖/追加”。")
        if self.repo.has_any_external_group_reference():
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "已有外部工序组绑定了供应商，不能执行“替换（清空后导入）”。请先解除引用或改用“覆盖/追加”。")

