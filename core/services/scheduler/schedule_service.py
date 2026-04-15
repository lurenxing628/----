from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import Batch, BatchOperation, ExternalGroup, PartOperation
from core.models.enums import BatchOperationStatus, BatchStatus, ReadyStatus, SourceType, YesNo
from core.services.common.normalize import normalize_text

from . import operation_edit_service as op_edit
from .freeze_window import build_freeze_window_seed
from .number_utils import parse_finite_float, to_yes_no
from .repository_bundle import build_schedule_repository_bundle
from .resource_pool_builder import build_resource_pool, extend_downtime_map_for_resource_pool, load_machine_downtimes
from .schedule_input_builder import build_algo_operations
from .schedule_input_collector import collect_schedule_run_input
from .schedule_optimizer import optimize_schedule
from .schedule_orchestrator import orchestrate_schedule_run
from .schedule_persistence import has_actionable_schedule_rows, persist_schedule
from .schedule_summary import build_result_summary
from .schedule_template_lookup import get_template_and_group_for_op

_RUN_SCHEDULE_LOCK = threading.Lock()
_TERMINAL_OPERATION_STATUSES = frozenset(
    (BatchOperationStatus.COMPLETED.value, BatchOperationStatus.SKIPPED.value)
)
_FAIL_FAST_BATCH_STATUSES = frozenset((BatchStatus.COMPLETED.value, BatchStatus.CANCELLED.value))


def _normalized_status_text(value: Any) -> str:
    return (normalize_text(value) or "").strip().lower()


def _get_snapshot_with_strict_mode(cfg_svc: Any, *, strict_mode: bool) -> Any:
    return cfg_svc.get_snapshot(strict_mode=bool(strict_mode))


def _raise_schedule_empty_result(message: str, *, reason: str) -> None:
    exc = ValidationError(message, field="排产")
    exc.details = dict(exc.details or {})
    exc.details["reason"] = reason
    raise exc


class ScheduleService:
    """
    排产服务（Phase 6：先做“非算法部分”）。

    本类主要负责：
    - 批次工序补充/编辑：内部工序（设备/人员/工时），外部工序（供应商/周期）
    - 对“合并周期（merged）外部组”给出明确提示与限制（避免用户误以为可逐道工序设置周期）
    """

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)

        self._repos = build_schedule_repository_bundle(conn, logger=logger)
        self.batch_repo = self._repos.batch_repo
        self.op_repo = self._repos.op_repo
        self.part_op_repo = self._repos.part_op_repo
        self.group_repo = self._repos.group_repo
        self.machine_repo = self._repos.machine_repo
        self.operator_repo = self._repos.operator_repo
        self.operator_machine_repo = self._repos.operator_machine_repo
        self.supplier_repo = self._repos.supplier_repo
        self.schedule_repo = self._repos.schedule_repo
        self.history_repo = self._repos.history_repo

    # -------------------------
    # 工具方法
    # -------------------------
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    @staticmethod
    def _is_reschedulable_operation(op: Any) -> bool:
        status = _normalized_status_text(getattr(op, "status", None)) or BatchOperationStatus.PENDING.value
        return status not in _TERMINAL_OPERATION_STATUSES

    @staticmethod
    def _normalize_float(value: Any, field: str, allow_none: bool = True) -> Optional[float]:
        return parse_finite_float(value, field=field, allow_none=allow_none)

    def _get_batch_or_raise(self, batch_id: str) -> Batch:
        b = self.batch_repo.get(batch_id)
        if not b:
            raise BusinessError(ErrorCode.BATCH_NOT_FOUND, f"批次“{batch_id}”不存在")
        return b

    def _get_op_or_raise(self, op_id: int) -> BatchOperation:
        op = self.op_repo.get(int(op_id))
        if not op:
            raise BusinessError(ErrorCode.NOT_FOUND, f"批次工序（ID={op_id}）不存在")
        return op

    def _get_template_and_group_for_op(self, op: BatchOperation) -> Tuple[Optional[PartOperation], Optional[ExternalGroup]]:
        return get_template_and_group_for_op(self, op)

    @staticmethod
    def _format_dt(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _normalize_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        s = str(value).strip()
        if not s:
            return None
        s = s.replace("/", "-").replace("T", " ").replace("：", ":")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        return None

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

    # -------------------------
    # Phase 7：执行排产（算法 + 落库 + 留痕）
    # -------------------------
    def run_schedule(
        self,
        batch_ids: List[str],
        start_dt: Any = None,
        end_date: Any = None,
        created_by: Optional[str] = None,
        simulate: bool = False,
        enforce_ready: Optional[bool] = None,
        strict_mode: bool = False,
    ) -> Dict[str, Any]:
        if not _RUN_SCHEDULE_LOCK.acquire(blocking=False):
            raise ValidationError("系统正在执行排产，请稍后重试。", field="排产")
        try:
            self._aps_schedule_input_cache = {"batch": {}, "tmpl": {}, "grp": {}}
            return self._run_schedule_impl(
                batch_ids=batch_ids,
                start_dt=start_dt,
                end_date=end_date,
                created_by=created_by,
                simulate=simulate,
                enforce_ready=enforce_ready,
                strict_mode=strict_mode,
            )
        finally:
            self._aps_schedule_input_cache = None
            _RUN_SCHEDULE_LOCK.release()

    def _run_schedule_impl(
        self,
        batch_ids: List[str],
        start_dt: Any = None,
        end_date: Any = None,
        created_by: Optional[str] = None,
        simulate: bool = False,
        enforce_ready: Optional[bool] = None,
        strict_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        执行排产并落库（Schedule）+ 留痕（ScheduleHistory + OperationLogs）。

        说明：
        - 版本号：从 ScheduleHistory.max(version)+1 递增
        - Schedule 写入、状态更新、ScheduleHistory 写入：**单事务原子**
        - OperationLogs：由于 OperationLogger 内部会 commit()，因此放到事务提交后写入，避免破坏原子性
        - simulate=True 时：用于“插单模拟/模拟排产”
          - 仍会落库到新版本（Schedule + ScheduleHistory），确保可追溯
          - 但不会更新 Batches/BatchOperations 的状态（避免污染正式状态）
        - enforce_ready 取值规则：
          - 显式传入 True/False：按传入值执行
          - 传入 None：回退读取配置 `enforce_ready_default`
        """
        from .calendar_service import CalendarService
        from .config_service import ConfigService

        schedule_input = collect_schedule_run_input(
            self,
            batch_ids=batch_ids,
            start_dt=start_dt,
            end_date=end_date,
            created_by=created_by,
            simulate=simulate,
            enforce_ready=enforce_ready,
            strict_mode=bool(strict_mode),
            calendar_service_cls=CalendarService,
            config_service_cls=ConfigService,
            get_snapshot_with_strict_mode=_get_snapshot_with_strict_mode,
            build_algo_operations_fn=build_algo_operations,
            build_freeze_window_seed_fn=build_freeze_window_seed,
            load_machine_downtimes_fn=load_machine_downtimes,
            build_resource_pool_fn=build_resource_pool,
            extend_downtime_map_for_resource_pool_fn=extend_downtime_map_for_resource_pool,
        )

        orchestration = orchestrate_schedule_run(
            self,
            schedule_input=schedule_input,
            simulate=simulate,
            strict_mode=bool(strict_mode),
            optimize_schedule_fn=optimize_schedule,
            has_actionable_schedule_rows_fn=has_actionable_schedule_rows,
            build_result_summary_fn=build_result_summary,
        )

        persist_schedule(
            self,
            cfg=schedule_input.cfg,
            version=orchestration.version,
            results=orchestration.results,
            summary=orchestration.summary,
            used_strategy=orchestration.used_strategy,
            used_params=orchestration.used_params,
            batches=schedule_input.batches,
            operations=schedule_input.operations,
            reschedulable_operations=schedule_input.reschedulable_operations,
            reschedulable_op_ids=set(schedule_input.reschedulable_op_ids),
            normalized_batch_ids=schedule_input.normalized_batch_ids,
            created_by=schedule_input.created_by_text,
            has_actionable_schedule=orchestration.has_actionable_schedule,
            simulate=simulate,
            frozen_op_ids=set(schedule_input.frozen_op_ids),
            result_status=orchestration.result_status,
            result_summary_json=orchestration.result_summary_json,
            result_summary_obj=orchestration.result_summary_obj,
            missing_internal_resource_op_ids=schedule_input.missing_internal_resource_op_ids,
            overdue_items=orchestration.overdue_items,
            time_cost_ms=orchestration.time_cost_ms,
        )

        return {
            "is_simulation": bool(simulate),
            "version": int(orchestration.version),
            "strategy": orchestration.used_strategy.value,
            "strategy_params": orchestration.used_params or {},
            "result_status": orchestration.result_status,
            "summary": {
                "success": getattr(orchestration.summary, "success", False),
                "total_ops": int(getattr(orchestration.summary, "total_ops", 0)),
                "scheduled_ops": int(getattr(orchestration.summary, "scheduled_ops", 0)),
                "failed_ops": int(getattr(orchestration.summary, "failed_ops", 0)),
                "warnings": getattr(orchestration.summary, "warnings", None),
                "errors": getattr(orchestration.summary, "errors", None),
                "duration_seconds": getattr(orchestration.summary, "duration_seconds", 0.0),
            },
            "overdue_batches": orchestration.overdue_items,
            "time_cost_ms": int(orchestration.time_cost_ms),
        }

