from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import Operator
from core.models.enums import OPERATOR_STATUS_VALUES, OperatorStatus
from core.services.common.normalize import normalize_text
from data.repositories import OperatorRepository, ResourceTeamRepository


class OperatorService:
    """人员服务（Operators）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self.repo = OperatorRepository(conn, logger=logger)
        self.team_repo = ResourceTeamRepository(conn, logger=logger)

    # -------------------------
    # 校验与工具方法
    # -------------------------
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    def _validate_operator_fields(
        self,
        operator_id: Any,
        name: Any,
        status: Any,
        team_id: Any = None,
        allow_partial: bool = False,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        op_id = self._normalize_text(operator_id)
        op_name = self._normalize_text(name)
        op_status = self._normalize_text(status)
        op_team_id = self._normalize_text(team_id)
        if op_status is not None:
            op_status = op_status.lower()

        if not allow_partial:
            if not op_id:
                raise ValidationError("工号不能为空", field="工号")
            if not op_name:
                raise ValidationError("姓名不能为空", field="姓名")
            if not op_status:
                raise ValidationError("状态不能为空，请选择：在岗 或 停用/休假。", field="状态")

        if op_status is not None and op_status not in OPERATOR_STATUS_VALUES:
            raise ValidationError("状态不正确，请选择：在岗 / 停用或休假。", field="状态")
        if op_team_id and not self.team_repo.get(op_team_id):
            raise BusinessError(ErrorCode.TEAM_NOT_FOUND, f"班组{op_team_id}不存在，请先维护班组。")

        return op_id, op_name, op_status, op_team_id

    def _get_or_raise(self, operator_id: str) -> Operator:
        op = self.repo.get(operator_id)
        if not op:
            raise BusinessError(ErrorCode.OPERATOR_NOT_FOUND, f"人员{operator_id}不存在")
        return op

    # -------------------------
    # CRUD
    # -------------------------
    def list(self, status: Optional[str] = None, team_id: Optional[str] = None) -> List[Operator]:
        filter_status = None
        filter_team_id = None
        if status or team_id is not None:
            _, _, filter_status, filter_team_id = self._validate_operator_fields(
                operator_id=None,
                name=None,
                status=status,
                team_id=team_id,
                allow_partial=True,
            )
            if status and filter_status is None:
                raise ValidationError("缺少状态参数", field="状态")
        return self.repo.list(status=filter_status, team_id=filter_team_id)

    def list_page(
        self,
        status: Optional[str] = None,
        team_id: Optional[str] = None,
        page: int = 1,
        per_page: int = 100,
    ) -> Tuple[List[Operator], int]:
        filter_status = None
        filter_team_id = None
        if status or team_id is not None:
            _, _, filter_status, filter_team_id = self._validate_operator_fields(
                operator_id=None,
                name=None,
                status=status,
                team_id=team_id,
                allow_partial=True,
            )
            if status and filter_status is None:
                raise ValidationError("缺少状态参数", field="状态")
        per_page_int = max(1, int(per_page or 100))
        total = self.repo.count(status=filter_status, team_id=filter_team_id)
        total_pages = max(1, (int(total) + per_page_int - 1) // per_page_int)
        page_int = min(max(1, int(page or 1)), total_pages)
        offset = (page_int - 1) * per_page_int
        rows = self.repo.list(status=filter_status, team_id=filter_team_id, limit=per_page_int, offset=offset)
        return rows, int(total)

    def get(self, operator_id: str) -> Operator:
        op_id, _, _, _ = self._validate_operator_fields(
            operator_id=operator_id,
            name=None,
            status=None,
            allow_partial=True,
        )
        if not op_id:
            raise ValidationError("工号不能为空", field="工号")
        return self._get_or_raise(op_id)

    def get_optional(self, operator_id: Any) -> Optional[Operator]:
        """
        宽松查询：找不到返回 None（用于页面回显已删除/已停用资源）。
        """
        op_id, _, _, _ = self._validate_operator_fields(
            operator_id=operator_id,
            name=None,
            status=None,
            allow_partial=True,
        )
        if not op_id:
            return None
        return self.repo.get(op_id)

    def create(
        self,
        operator_id: Any,
        name: Any,
        status: Any = OperatorStatus.ACTIVE.value,
        remark: Any = None,
        team_id: Any = None,
    ) -> Operator:
        op_id, op_name, op_status, op_team_id = self._validate_operator_fields(
            operator_id=operator_id,
            name=name,
            status=status,
            team_id=team_id,
        )
        if op_id is None:
            raise ValidationError("工号不能为空", field="工号")
        if op_name is None:
            raise ValidationError("姓名不能为空", field="姓名")
        op_remark = self._normalize_text(remark)

        if self.repo.exists(op_id):
            raise BusinessError(ErrorCode.OPERATOR_ALREADY_EXISTS, f"工号“{op_id}”已存在，这次没有保存。请改用别的工号，或去修改已有的那个人员。")

        with self.tx_manager.transaction():
            self.repo.create(
                {
                    "operator_id": op_id,
                    "name": op_name,
                    "status": op_status or OperatorStatus.ACTIVE.value,
                    "remark": op_remark,
                    "team_id": op_team_id,
                }
            )
        return self._get_or_raise(op_id)

    def update(
        self,
        operator_id: Any,
        name: Any = None,
        status: Any = None,
        remark: Any = None,
        team_id: Any = None,
    ) -> Operator:
        op_id, op_name, op_status, op_team_id = self._validate_operator_fields(
            operator_id=operator_id,
            name=name,
            status=status,
            team_id=team_id,
            allow_partial=True,
        )
        if not op_id:
            raise ValidationError("工号不能为空", field="工号")
        self._get_or_raise(op_id)

        updates: Dict[str, Any] = {}
        if op_name is not None:
            updates["name"] = op_name
        if op_status is not None:
            updates["status"] = op_status
        if remark is not None:
            updates["remark"] = self._normalize_text(remark)
        if team_id is not None:
            updates["team_id"] = op_team_id

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
        - 建议改用停用（inactive）
        """
        op_id, _, _, _ = self._validate_operator_fields(
            operator_id=operator_id,
            name=None,
            status=None,
            allow_partial=True,
        )
        if not op_id:
            raise ValidationError("工号不能为空", field="工号")
        self._get_or_raise(op_id)

        # 若被批次工序引用，则禁止删除
        if self.repo.is_referenced_by_batch_operations(op_id):
            raise BusinessError(
                ErrorCode.OPERATOR_IN_USE,
                "还有批次工序在用这个人员，没有删除。请先把这些批次工序改成别的人员，或把这个人员改成“停用”。",
            )

        # 若被排程引用，则禁止删除（否则会触发 Schedule.operator_id 外键错误）
        if self.repo.is_referenced_by_schedule(op_id):
            raise BusinessError(
                ErrorCode.OPERATOR_IN_USE,
                "排产结果里还在用这个人员，没有删除。请把这个人员改成“停用”。",
            )

        with self.tx_manager.transaction():
            self.repo.delete(op_id)

    # -------------------------
    # Excel 相关辅助（按中文列名）
    # -------------------------

    def ensure_replace_allowed(self) -> None:
        """
        REPLACE（清空后导入）保护：
        如果人员已被批次工序或排程结果引用，则禁止清空。
        """
        if self.repo.has_any_batch_operations_operator_reference():
            raise BusinessError(
                ErrorCode.OPERATOR_IN_USE,
                "还有批次工序在用人员，不能先清除全部人员再重导，这次没有导入。请先解除这些关联，或改用“已有的就更新，没有的就新增”。",
            )
        if self.repo.has_any_schedule_operator_reference():
            raise BusinessError(
                ErrorCode.OPERATOR_IN_USE,
                "排产结果里还在用人员，不能先清除全部人员再重导，这次没有导入。请先解除这些关联，或改用“已有的就更新，没有的就新增”。",
            )
