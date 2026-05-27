from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import Batch, BatchOperation, ExternalGroup, PartOperation
from core.models.enums import BatchOperationStatus, BatchStatus
from core.services.common.normalize import normalize_text

from . import operation_edit_service as op_edit
from .number_utils import parse_finite_float
from .repository_bundle import build_schedule_repository_bundle
from .resource_pool_builder import build_resource_pool, extend_downtime_map_for_resource_pool, load_machine_downtimes
from .run.freeze_window import build_freeze_window_seed
from .run.schedule_input_builder import build_algo_operations
from .run.schedule_input_collector import collect_schedule_run_input
from .run.schedule_optimizer import optimize_schedule
from .run.schedule_orchestrator import orchestrate_schedule_run
from .run.schedule_persistence import (
    persist_schedule_run_with_candidates as persist_schedule,
)
from .run.schedule_persistence import (
    validate_execution_guard_before_persist,
)
from .run.schedule_template_lookup import get_template_and_group_for_op
from .summary.schedule_summary import build_result_summary

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
        self.candidate_repo = self._repos.candidate_repo

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
        run_time_budget_seconds: Any = None,
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
                run_time_budget_seconds=run_time_budget_seconds,
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
        run_time_budget_seconds: Any = None,
    ) -> Dict[str, Any]:
        """
        执行排产并落库（Schedule）+ 留痕（ScheduleHistory + OperationLogs）。

        说明：
        - 版本号：从 ScheduleHistory.max(version)+1 递增
        - Schedule 写入、状态更新、ScheduleHistory 写入：**单事务原子**
        - OperationLogs：由于 OperationLogger 内部会 commit()，因此放到事务提交后写入，避免破坏原子性
        - simulate=True 时：用于“插单模拟/模拟排产”
          - 只做安全校验和试算返回，不写 Schedule、ScheduleHistory 或正式状态
        - enforce_ready 取值规则：
          - 显式传入 True/False：按传入值执行
          - 传入 None：回退读取配置 `enforce_ready_default`
        """
        from .calendar_service import CalendarService
        from .config.config_service import ConfigService

        schedule_input = collect_schedule_run_input(
            self,
            batch_ids=batch_ids,
            start_dt=start_dt,
            end_date=end_date,
            created_by=created_by,
            simulate=simulate,
            enforce_ready=enforce_ready,
            strict_mode=bool(strict_mode),
            run_time_budget_seconds=run_time_budget_seconds,
            calendar_service_cls=CalendarService,
            config_service_cls=ConfigService,
            get_snapshot_with_strict_mode=_get_snapshot_with_strict_mode,
            build_algo_operations_fn=build_algo_operations,
            build_freeze_window_seed_fn=build_freeze_window_seed,
            load_machine_downtimes_fn=load_machine_downtimes,
            build_resource_pool_fn=build_resource_pool,
            extend_downtime_map_for_resource_pool_fn=extend_downtime_map_for_resource_pool,
        )

        simulation_validated_only = bool(simulate)

        def _validate_execution_guard_before_version(validated_schedule_payload):
            validate_execution_guard_before_persist(
                self,
                validated_schedule_payload=validated_schedule_payload,
                execution_guard_state_revisions=dict(schedule_input.execution_guard_state_revisions or {}),
                execution_facts=dict(schedule_input.execution_facts or {}),
                execution_fixed_op_ids=set(schedule_input.execution_fixed_op_ids or set()),
                execution_completed_op_ids=set(schedule_input.execution_completed_op_ids or set()),
                execution_snapshot_revision=schedule_input.execution_snapshot_revision,
                execution_snapshot_op_ids=list(schedule_input.execution_snapshot_op_ids),
                payload_validation_operations=list(schedule_input.payload_validation_operations or []),
            )

        def _persist_orchestration(orchestration):
            persist_schedule(
                self,
                cfg=schedule_input.cfg,
                version=orchestration.version,
                validated_schedule_payload=orchestration.validated_schedule_payload,
                summary=orchestration.summary,
                used_strategy=orchestration.used_strategy,
                used_params=orchestration.used_params,
                batches=schedule_input.batches,
                reschedulable_operations=schedule_input.reschedulable_operations,
                normalized_batch_ids=schedule_input.normalized_batch_ids,
                created_by=schedule_input.created_by_text,
                simulate=simulate,
                frozen_op_ids=set(schedule_input.frozen_op_ids),
                execution_fixed_op_ids=set(schedule_input.execution_fixed_op_ids),
                execution_completed_op_ids=set(schedule_input.execution_completed_op_ids),
                execution_guard_state_revisions=dict(schedule_input.execution_guard_state_revisions),
                execution_snapshot_revision=schedule_input.execution_snapshot_revision,
                execution_snapshot_op_ids=list(schedule_input.execution_snapshot_op_ids),
                execution_facts=dict(schedule_input.execution_facts),
                payload_validation_operations=list(schedule_input.payload_validation_operations),
                result_status=orchestration.result_status,
                result_summary_json=orchestration.result_summary_json,
                result_summary_obj=orchestration.result_summary_obj,
                missing_internal_resource_op_ids=schedule_input.missing_internal_resource_op_ids,
                overdue_items=orchestration.overdue_items,
                time_cost_ms=orchestration.time_cost_ms,
                candidate_comparison=orchestration.candidate_comparison,
            )

        orchestration = orchestrate_schedule_run(
            self,
            schedule_input=schedule_input,
            simulate=simulate,
            strict_mode=bool(strict_mode),
            optimize_schedule_fn=optimize_schedule,
            build_result_summary_fn=build_result_summary,
            before_version_allocate_fn=_validate_execution_guard_before_version,
            allocate_version=not simulation_validated_only,
            version_override=schedule_input.prev_version,
            persist_schedule_fn=None if simulation_validated_only else _persist_orchestration,
        )

        if simulation_validated_only:
            validate_execution_guard_before_persist(
                self,
                validated_schedule_payload=orchestration.validated_schedule_payload,
                execution_guard_state_revisions=dict(schedule_input.execution_guard_state_revisions or {}),
                execution_facts=dict(schedule_input.execution_facts or {}),
                execution_fixed_op_ids=set(schedule_input.execution_fixed_op_ids or set()),
                execution_completed_op_ids=set(schedule_input.execution_completed_op_ids or set()),
                execution_snapshot_revision=schedule_input.execution_snapshot_revision,
                execution_snapshot_op_ids=list(schedule_input.execution_snapshot_op_ids),
                payload_validation_operations=list(schedule_input.payload_validation_operations or []),
            )

        result: Dict[str, Any] = {
            "is_simulation": bool(simulate),
            "version": None if simulation_validated_only else int(orchestration.version),
            "result_persisted": not simulation_validated_only,
            "can_open_result_version": not simulation_validated_only,
            "strategy": orchestration.used_strategy.value,
            "strategy_params": orchestration.used_params or {},
            "result_status": orchestration.result_status,
            "summary": orchestration.summary_contract.to_dict(),
            "overdue_batches": orchestration.overdue_items,
            "time_cost_ms": int(orchestration.time_cost_ms),
        }
        if simulation_validated_only:
            result["user_message"] = "这次模拟只做安全检查，没有生成新的排程版本，也没有改动正式排程。"
        return result
