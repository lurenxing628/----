from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import Operator
from core.models.enums import OperatorStatus
from data.repositories import OperatorRepository


class OperatorService:
    """人员服务（Operators）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self.repo = OperatorRepository(conn, logger=logger)

    # -------------------------
    # 校验与工具方法
    # -------------------------
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            v = value.strip()
            return v if v != "" else None
        v = str(value).strip()
        return v if v != "" else None

    def _validate_operator_fields(
        self,
        operator_id: Any,
        name: Any,
        status: Any,
        allow_partial: bool = False,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        op_id = self._normalize_text(operator_id)
        op_name = self._normalize_text(name)
        op_status = self._normalize_text(status)

        if not allow_partial:
            if not op_id:
                raise ValidationError("“工号”不能为空", field="工号")
            if not op_name:
                raise ValidationError("“姓名”不能为空", field="姓名")
            if not op_status:
                raise ValidationError("“状态”不能为空（允许：active / inactive）", field="状态")

        if op_status is not None and op_status not in (OperatorStatus.ACTIVE.value, OperatorStatus.INACTIVE.value):
            raise ValidationError("“状态”不合法（允许：active / inactive）", field="状态")

        return op_id, op_name, op_status

    def _get_or_raise(self, operator_id: str) -> Operator:
        op = self.repo.get(operator_id)
        if not op:
            raise BusinessError(ErrorCode.OPERATOR_NOT_FOUND, f"人员“{operator_id}”不存在")
        return op

    # -------------------------
    # CRUD
    # -------------------------
    def list(self, status: Optional[str] = None) -> List[Operator]:
        if status:
            # 校验一下 status（避免页面/接口传错）
            self._validate_operator_fields(operator_id="DUMMY", name="DUMMY", status=status, allow_partial=True)
        return self.repo.list(status=status)

    def get(self, operator_id: str) -> Operator:
        op_id, _, _ = self._validate_operator_fields(operator_id=operator_id, name=None, status=None, allow_partial=True)
        if not op_id:
            raise ValidationError("“工号”不能为空", field="工号")
        return self._get_or_raise(op_id)

    def create(self, operator_id: Any, name: Any, status: Any = "active", remark: Any = None) -> Operator:
        op_id, op_name, op_status = self._validate_operator_fields(operator_id=operator_id, name=name, status=status)
        op_remark = self._normalize_text(remark)

        if self.repo.exists(op_id):
            raise BusinessError(ErrorCode.OPERATOR_ALREADY_EXISTS, f"工号“{op_id}”已存在，不能重复添加。")

        with self.tx_manager.transaction():
            self.repo.create(
                {
                    "operator_id": op_id,
                    "name": op_name,
                    "status": op_status or OperatorStatus.ACTIVE.value,
                    "remark": op_remark,
                }
            )
        return self._get_or_raise(op_id)

    def update(
        self,
        operator_id: Any,
        name: Any = None,
        status: Any = None,
        remark: Any = None,
    ) -> Operator:
        op_id, op_name, op_status = self._validate_operator_fields(
            operator_id=operator_id, name=name, status=status, allow_partial=True
        )
        if not op_id:
            raise ValidationError("“工号”不能为空", field="工号")
        self._get_or_raise(op_id)

        updates: Dict[str, Any] = {}
        if op_name is not None:
            updates["name"] = op_name
        if op_status is not None:
            updates["status"] = op_status
        if remark is not None:
            updates["remark"] = self._normalize_text(remark)

        with self.tx_manager.transaction():
            self.repo.update(op_id, updates)
        return self._get_or_raise(op_id)

    def set_status(self, operator_id: Any, status: Any) -> Operator:
        return self.update(operator_id=operator_id, status=status)

    def delete(self, operator_id: Any) -> None:
        """
        删除人员（物理删除）。

        保护策略：
        - 若人员已被 BatchOperations 或 Schedule 引用，则禁止删除（避免排产数据断链/外键失败）
        - 建议改用“停用（inactive）”
        """
        op_id, _, _ = self._validate_operator_fields(operator_id=operator_id, name=None, status=None, allow_partial=True)
        if not op_id:
            raise ValidationError("“工号”不能为空", field="工号")
        self._get_or_raise(op_id)

        # 若被批次工序引用，则禁止删除
        row = self.conn.execute(
            "SELECT 1 FROM BatchOperations WHERE operator_id = ? LIMIT 1",
            (op_id,),
        ).fetchone()
        if row is not None:
            raise BusinessError(
                ErrorCode.OPERATOR_IN_USE,
                "该人员已被批次工序引用，不能删除。请先解除引用或改为“停用”。",
            )

        # 若被排程引用，则禁止删除（否则会触发 Schedule.operator_id 外键错误）
        row2 = self.conn.execute(
            "SELECT 1 FROM Schedule WHERE operator_id = ? LIMIT 1",
            (op_id,),
        ).fetchone()
        if row2 is not None:
            raise BusinessError(
                ErrorCode.OPERATOR_IN_USE,
                "该人员已被排程结果引用，不能删除。请改为“停用”。",
            )

        with self.tx_manager.transaction():
            self.repo.delete(op_id)

    # -------------------------
    # Excel 相关辅助（按中文列名）
    # -------------------------
    def build_existing_for_excel(self) -> Dict[str, Dict[str, Any]]:
        """
        构建给 ExcelService.preview_import 使用的 existing_data：
        - key: 工号
        - value: 以 Excel 列名（中文）表示的 dict
        """
        existing: Dict[str, Dict[str, Any]] = {}
        for op in self.repo.list():
            existing[op.operator_id] = {
                "工号": op.operator_id,
                "姓名": op.name,
                "状态": op.status,
                "备注": op.remark,
            }
        return existing

    def ensure_replace_allowed(self) -> None:
        """
        REPLACE（清空后导入）保护：
        如果人员已被批次工序引用（BatchOperations.operator_id），则禁止清空。
        """
        row = self.conn.execute(
            "SELECT 1 FROM BatchOperations WHERE operator_id IS NOT NULL AND TRIM(operator_id) <> '' LIMIT 1"
        ).fetchone()
        if row is not None:
            raise BusinessError(
                ErrorCode.OPERATOR_IN_USE,
                "已有批次工序引用了人员，不能执行“替换（清空后导入）”。请先解除引用或改用“覆盖/追加”。",
            )

