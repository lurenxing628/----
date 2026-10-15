from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import Batch, BatchOperation, ExternalGroup, PartOperation
from core.services.common.normalize import normalize_text
from core.shared.number_utils import parse_finite_float
from data.repositories import (
    BatchOperationRepository,
    BatchRepository,
    ExternalGroupRepository,
    MachineRepository,
    OperatorMachineRepository,
    OperatorRepository,
    PartOperationRepository,
    SupplierRepository,
)

from . import operation_edit_service as op_edit
from .run.schedule_template_lookup import get_template_and_group_for_op


class ScheduleService:
    """
    批次工序编辑服务。

    本类主要负责：
    - 批次工序补充/编辑：内部工序（设备/人员/工时），外部工序（供应商/周期）
    - 对“合并周期（merged）外部组”给出明确提示与限制（避免用户误以为可逐道工序设置周期）
    """

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)

        self.batch_repo = BatchRepository(conn, logger=logger)
        self.op_repo = BatchOperationRepository(conn, logger=logger)
        self.part_op_repo = PartOperationRepository(conn, logger=logger)
        self.group_repo = ExternalGroupRepository(conn, logger=logger)
        self.machine_repo = MachineRepository(conn, logger=logger)
        self.operator_repo = OperatorRepository(conn, logger=logger)
        self.operator_machine_repo = OperatorMachineRepository(conn, logger=logger)
        self.supplier_repo = SupplierRepository(conn, logger=logger)

    # -------------------------
    # 工具方法
    # -------------------------
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    @staticmethod
    def _normalize_float(value: Any, field: str, allow_none: bool = True) -> Optional[float]:
        return parse_finite_float(value, field=field, allow_none=allow_none)

    def _get_batch_or_raise(self, batch_id: str) -> Batch:
        b = self.batch_repo.get(batch_id)
        if not b:
            raise BusinessError(ErrorCode.BATCH_NOT_FOUND, f"批次“{batch_id}”不存在")
        return b

    def _get_op_or_raise(self, op_id: int) -> BatchOperation:
        normalized_op_id = int(op_id)
        op = self.op_repo.get(normalized_op_id)
        if not op:
            if self.logger is not None:
                self.logger.warning("排产工序不存在：op_id=%s", normalized_op_id)
            raise BusinessError(
                ErrorCode.NOT_FOUND,
                "这道工序不存在或已被删除，请刷新批次详情后重试。",
                details={"field": "op_id"},
                internal_details={"reason": "missing_batch_operation", "op_id": normalized_op_id},
            )
        return op

    def _get_template_and_group_for_op(self, op: BatchOperation) -> Tuple[Optional[PartOperation], Optional[ExternalGroup]]:
        return get_template_and_group_for_op(self, op)

    # -------------------------
    # 查询
    # -------------------------
    def list_batch_operations(self, batch_id: Any) -> List[BatchOperation]:
        return op_edit.list_batch_operations(self, batch_id)

    def get_operation(self, op_id: Any) -> BatchOperation:
        return op_edit.get_operation(self, op_id)

    def get_external_merge_hint_for_op(self, op: BatchOperation) -> Dict[str, Any]:
        """
        基于已加载工序对象返回外部工序“合并周期”提示信息，避免列表页逐行重复回库读取同一工序。
        """
        return op_edit.get_external_merge_hint_for_op(self, op)

    def get_external_merge_hint(self, op_id: Any) -> Dict[str, Any]:
        """
        返回外部工序“合并周期”提示信息（供页面展示）。
        """
        return op_edit.get_external_merge_hint(self, op_id)

    # -------------------------
    # 更新：内部工序
    # -------------------------
    def update_internal_operation(
        self,
        op_id: Any,
        machine_id: Any = None,
        operator_id: Any = None,
        setup_hours: Any = None,
        unit_hours: Any = None,
        status: Any = None,
    ) -> BatchOperation:
        return op_edit.update_internal_operation(
            self,
            op_id=op_id,
            machine_id=machine_id,
            operator_id=operator_id,
            setup_hours=setup_hours,
            unit_hours=unit_hours,
            status=status,
        )

    # -------------------------
    # 更新：外部工序
    # -------------------------
    def update_external_operation(
        self,
        op_id: Any,
        supplier_id: Any = None,
        ext_days: Any = None,
        status: Any = None,
    ) -> BatchOperation:
        return op_edit.update_external_operation(
            self,
            op_id=op_id,
            supplier_id=supplier_id,
            ext_days=ext_days,
            status=status,
        )
