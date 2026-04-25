from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import OpType
from core.models.enums import SOURCE_TYPE_VALUES, SourceType
from core.services.common.enum_normalizers import source_type_label
from core.services.common.normalize import normalize_text
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
        return normalize_text(value)

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
        if ot_category is not None:
            ot_category = ot_category.lower()

        if not allow_partial:
            if not ot_id:
                raise ValidationError("“工种ID”不能为空", field="工种ID")
            if not ot_name:
                raise ValidationError("“工种名称”不能为空", field="工种名称")
            if not ot_category:
                ot_category = SourceType.INTERNAL.value

        if ot_category is not None and ot_category not in SOURCE_TYPE_VALUES:
            raise ValidationError("“归属”不正确，请选择：内部 / 外部。", field="归属")

        return ot_id, ot_name, ot_category

    def _get_or_raise(self, op_type_id: str) -> OpType:
        ot = self.repo.get(op_type_id)
        if not ot:
            raise BusinessError(ErrorCode.NOT_FOUND, f"工种“{op_type_id}”不存在")
        return ot

    def list(self, category: Optional[str] = None) -> List[OpType]:
        filter_cat = None
        if category:
            _id, _name, filter_cat = self._validate_fields(None, None, category, allow_partial=True)
            if filter_cat is None:
                raise ValidationError("缺少归属参数", field="归属")
        return self.repo.list(category=filter_cat)

    def get(self, op_type_id: str) -> OpType:
        ot_id, _, _ = self._validate_fields(op_type_id, None, None, allow_partial=True)
        if not ot_id:
            raise ValidationError("“工种ID”不能为空", field="工种ID")
        return self._get_or_raise(ot_id)

    def get_optional(self, op_type_id: Any) -> Optional[OpType]:
        ot_id, _, _ = self._validate_fields(op_type_id, None, None, allow_partial=True)
        if not ot_id:
            return None
        return self.repo.get(ot_id)

    def get_by_name_optional(self, name: Any) -> Optional[OpType]:
        n = self._normalize_text(name)
        if not n:
            return None
        return self.repo.get_by_name(n)

    def resolve_op_type_id_optional(self, value: Any) -> Optional[str]:
        """
        Excel/表单兼容：允许用工种ID或工种名称定位工种，返回 op_type_id（找不到则 None）。
        """
        v = self._normalize_text(value)
        if not v:
            return None
        ot = self.get_optional(v)
        if not ot:
            ot = self.get_by_name_optional(v)
        return ot.op_type_id if ot else None

    def create(self, op_type_id: Any, name: Any, category: Any = SourceType.INTERNAL.value, remark: Any = None) -> OpType:
        ot_id, ot_name, ot_category = self._validate_fields(op_type_id, name, category)
        if ot_id is None:
            raise ValidationError("“工种ID”不能为空", field="工种ID")
        if ot_name is None:
            raise ValidationError("“工种名称”不能为空", field="工种名称")
        ot_remark = self._normalize_text(remark)

        if self.repo.get(ot_id):
            raise BusinessError(ErrorCode.DUPLICATE_ENTRY, f"工种ID“{ot_id}”已存在，不能重复添加。")
        if self.repo.get_by_name(ot_name):
            raise BusinessError(ErrorCode.DUPLICATE_ENTRY, f"工种名称“{ot_name}”已存在，不能重复添加。")

        with self.tx_manager.transaction():
            self.repo.create({"op_type_id": ot_id, "name": ot_name, "category": ot_category or SourceType.INTERNAL.value, "remark": ot_remark})
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
        if self.repo.has_machine_reference(ot_id):
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "该工种已被设备引用，不能删除。建议改为外部/内部归属或调整引用后再试。")
        if self.repo.has_supplier_reference(ot_id):
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "该工种已被供应商引用，不能删除。建议改为外部/内部归属或调整引用后再试。")
        if self.repo.has_part_operation_reference(ot_id):
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "该工种已被零件工序模板引用，不能删除。建议改为外部/内部归属或调整引用后再试。")
        if self.repo.has_batch_operation_reference(ot_id):
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "该工种已被批次工序引用，不能删除。建议改为外部/内部归属或调整引用后再试。")

        with self.tx_manager.transaction():
            self.repo.delete(ot_id)

    # -------------------------
    # Excel 辅助
    # -------------------------
    def build_existing_for_excel(self) -> Dict[str, Dict[str, Any]]:
        existing: Dict[str, Dict[str, Any]] = {}
        for ot in self.repo.list():
            existing[ot.op_type_id] = {
                "工种ID": ot.op_type_id,
                "工种名称": ot.name,
                "归属": ot.category,
                "归属显示": source_type_label(ot.category),
            }
        return existing

    def ensure_replace_allowed(self) -> None:
        """
        REPLACE（清空后导入）保护：
        若已被设备/供应商/工艺模板/批次工序引用，则禁止清空。
        """
        if self.repo.has_any_machine_reference():
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "已有设备引用了工种，不能执行“替换（清空后导入）”。请先解除引用或改用“覆盖/追加”。")
        if self.repo.has_any_supplier_reference():
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "已有供应商绑定了工种，不能执行“替换（清空后导入）”。请先解除引用或改用“覆盖/追加”。")
        if self.repo.has_any_part_operation_reference():
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "已有零件工序模板引用了工种，不能执行“替换（清空后导入）”。请先解除引用或改用“覆盖/追加”。")
        if self.repo.has_any_batch_operation_reference():
            raise BusinessError(ErrorCode.PERMISSION_DENIED, "已有批次工序引用了工种，不能执行“替换（清空后导入）”。请先解除引用或改用“覆盖/追加”。")
