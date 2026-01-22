from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import OpType
from data.repositories import OpTypeRepository


class OpTypeService:
    """工种服务（OpTypes）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self.repo = OpTypeRepository(conn, logger=logger)

    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            v = value.strip()
            return v if v != "" else None
        v = str(value).strip()
        return v if v != "" else None

    def _validate_fields(
        self,
        op_type_id: Any,
        name: Any,
        category: Any,
        allow_partial: bool = False,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        ot_id = self._normalize_text(op_type_id)
        ot_name = self._normalize_text(name)
        ot_category = self._normalize_text(category)

        if not allow_partial:
            if not ot_id:
                raise ValidationError("“工种ID”不能为空", field="工种ID")
            if not ot_name:
                raise ValidationError("“工种名称”不能为空", field="工种名称")
            if not ot_category:
                ot_category = "internal"

        if ot_category is not None and ot_category not in ("internal", "external"):
            raise ValidationError("“归属”不合法（允许：internal / external）", field="归属")

        return ot_id, ot_name, ot_category

    def _get_or_raise(self, op_type_id: str) -> OpType:
        ot = self.repo.get(op_type_id)
        if not ot:
            raise BusinessError(ErrorCode.NOT_FOUND, f"工种“{op_type_id}”不存在")
        return ot

    def list(self, category: Optional[str] = None) -> List[OpType]:
        if category:
            _id, _name, cat = self._validate_fields("DUMMY", "DUMMY", category, allow_partial=True)
            if cat is None:
                raise ValidationError("缺少归属参数", field="归属")
        return self.repo.list(category=category)

    def get(self, op_type_id: str) -> OpType:
        ot_id, _, _ = self._validate_fields(op_type_id, None, None, allow_partial=True)
        if not ot_id:
            raise ValidationError("“工种ID”不能为空", field="工种ID")
        return self._get_or_raise(ot_id)

    def create(self, op_type_id: Any, name: Any, category: Any = "internal", remark: Any = None) -> OpType:
        ot_id, ot_name, ot_category = self._validate_fields(op_type_id, name, category)
        ot_remark = self._normalize_text(remark)

        if self.repo.get(ot_id):
            raise BusinessError(ErrorCode.DUPLICATE_ENTRY, f"工种ID“{ot_id}”已存在，不能重复添加。")
        if self.repo.get_by_name(ot_name):
            raise BusinessError(ErrorCode.DUPLICATE_ENTRY, f"工种名称“{ot_name}”已存在，不能重复添加。")

        with self.tx_manager.transaction():
            self.repo.create({"op_type_id": ot_id, "name": ot_name, "category": ot_category or "internal", "remark": ot_remark})
        return self._get_or_raise(ot_id)

    def update(self, op_type_id: Any, name: Any = None, category: Any = None, remark: Any = None) -> OpType:
        ot_id, ot_name, ot_category = self._validate_fields(op_type_id, name, category, allow_partial=True)
        if not ot_id:
            raise ValidationError("“工种ID”不能为空", field="工种ID")
        self._get_or_raise(ot_id)

        updates: Dict[str, Any] = {}
        if ot_name is not None:
            if not ot_name:
                raise ValidationError("“工种名称”不能为空", field="工种名称")
            # 名称唯一性
            exist = self.repo.get_by_name(ot_name)
            if exist and exist.op_type_id != ot_id:
                raise BusinessError(ErrorCode.DUPLICATE_ENTRY, f"工种名称“{ot_name}”已存在，不能重复。")
            updates["name"] = ot_name
        if ot_category is not None:
            updates["category"] = ot_category
        if remark is not None:
            updates["remark"] = self._normalize_text(remark)

        with self.tx_manager.transaction():
            self.repo.update(ot_id, updates)
        return self._get_or_raise(ot_id)

    def delete(self, op_type_id: Any) -> None:
        ot_id, _, _ = self._validate_fields(op_type_id, None, None, allow_partial=True)
        if not ot_id:
            raise ValidationError("“工种ID”不能为空", field="工种ID")
        self._get_or_raise(ot_id)

        # 若被引用，禁止删除（避免断链）
        for table, col, zh in [
            ("Machines", "op_type_id", "设备"),
            ("Suppliers", "op_type_id", "供应商"),
            ("PartOperations", "op_type_id", "零件工序模板"),
            ("BatchOperations", "op_type_id", "批次工序"),
        ]:
            row = self.conn.execute(
                f"SELECT 1 FROM {table} WHERE {col} IS NOT NULL AND TRIM({col}) <> '' AND {col} = ? LIMIT 1",
                (ot_id,),
            ).fetchone()
            if row is not None:
                raise BusinessError(ErrorCode.PERMISSION_DENIED, f"该工种已被{zh}引用，不能删除。建议改为外部/内部归属或调整引用后再试。")

        with self.tx_manager.transaction():
            self.repo.delete(ot_id)

    # -------------------------
    # Excel 辅助
    # -------------------------
    def build_existing_for_excel(self) -> Dict[str, Dict[str, Any]]:
        existing: Dict[str, Dict[str, Any]] = {}
        for ot in self.repo.list():
            existing[ot.op_type_id] = {"工种ID": ot.op_type_id, "工种名称": ot.name, "归属": ot.category}
        return existing

    def ensure_replace_allowed(self) -> None:
        """
        REPLACE（清空后导入）保护：
        若已被设备/供应商/工艺模板/批次工序引用，则禁止清空。
        """
        for table, col, code, msg in [
            ("Machines", "op_type_id", ErrorCode.PERMISSION_DENIED, "已有设备引用了工种，不能执行“替换（清空后导入）”。"),
            ("Suppliers", "op_type_id", ErrorCode.PERMISSION_DENIED, "已有供应商绑定了工种，不能执行“替换（清空后导入）”。"),
            ("PartOperations", "op_type_id", ErrorCode.PERMISSION_DENIED, "已有零件工序模板引用了工种，不能执行“替换（清空后导入）”。"),
            ("BatchOperations", "op_type_id", ErrorCode.PERMISSION_DENIED, "已有批次工序引用了工种，不能执行“替换（清空后导入）”。"),
        ]:
            row = self.conn.execute(
                f"SELECT 1 FROM {table} WHERE {col} IS NOT NULL AND TRIM({col}) <> '' LIMIT 1"
            ).fetchone()
            if row is not None:
                raise BusinessError(code, f"{msg}请先解除引用或改用“覆盖/追加”。")

