from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import Batch, BatchOperation, ExternalGroup, PartOperation
from core.models.enums import BatchOperationStatus, BatchStatus, ReadyStatus, SourceType, YesNo
from core.services.common.build_outcome import BuildOutcome
from core.services.common.normalize import normalize_text
from data.repositories import (
    BatchOperationRepository,
    BatchRepository,
    ExternalGroupRepository,
    MachineRepository,
    OperatorMachineRepository,
    OperatorRepository,
    PartOperationRepository,
    ScheduleHistoryRepository,
    ScheduleRepository,
    SupplierRepository,
)

from . import operation_edit_service as op_edit
from .freeze_window import build_freeze_window_seed
from .number_utils import parse_finite_float, to_yes_no
from .resource_pool_builder import build_resource_pool, extend_downtime_map_for_resource_pool, load_machine_downtimes
from .schedule_input_builder import build_algo_operations
from .schedule_optimizer import optimize_schedule
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


def _get_snapshot_with_optional_strict_mode(cfg_svc: Any, *, strict_mode: bool) -> Any:
    try:
        return cfg_svc.get_snapshot(strict_mode=bool(strict_mode))
    except TypeError as exc:
        message = str(exc)
        if (
            "strict_mode" in message
            and ("unexpected keyword argument" in message or "got an unexpected keyword argument" in message)
        ):
            return cfg_svc.get_snapshot()
        raise


def _build_algo_operations_with_optional_outcome(svc, operations: List[Any], *, strict_mode: bool) -> BuildOutcome[List[Any]]:
    try:
        outcome = build_algo_operations(
            svc,
            operations,
            strict_mode=bool(strict_mode),
            return_outcome=True,
        )
    except TypeError as exc:
        message = str(exc)
        if (
            ("strict_mode" in message or "return_outcome" in message)
            and ("unexpected keyword argument" in message or "got an unexpected keyword argument" in message)
        ):
            outcome = build_algo_operations(svc, operations)
        else:
            raise
    if isinstance(outcome, BuildOutcome):
        return outcome
    return BuildOutcome(value=list(outcome or []))


def _build_freeze_window_seed_with_optional_meta(
    svc,
    *,
    cfg: Any,
    prev_version: int,
    start_dt: datetime,
    operations: List[Any],
    reschedulable_operations: Optional[List[Any]],
    strict_mode: bool,
) -> Tuple[set, List[Dict[str, Any]], List[str], Dict[str, Any]]:
    freeze_meta: Dict[str, Any] = {}
    try:
        result = build_freeze_window_seed(
            svc,
            cfg=cfg,
            prev_version=prev_version,
            start_dt=start_dt,
            operations=operations,
            reschedulable_operations=reschedulable_operations,
            strict_mode=bool(strict_mode),
            meta=freeze_meta,
        )
    except TypeError as exc:
        message = str(exc)
        if ("strict_mode" in message or "meta" in message) and (
            "unexpected keyword argument" in message or "got an unexpected keyword argument" in message
        ):
            result = build_freeze_window_seed(
                svc,
                cfg=cfg,
                prev_version=prev_version,
                start_dt=start_dt,
                operations=operations,
                reschedulable_operations=reschedulable_operations,
            )
        else:
            raise
    return result[0], result[1], result[2], freeze_meta


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

        self.batch_repo = BatchRepository(conn, logger=logger)
        self.op_repo = BatchOperationRepository(conn, logger=logger)

        self.part_op_repo = PartOperationRepository(conn, logger=logger)
        self.group_repo = ExternalGroupRepository(conn, logger=logger)

        self.machine_repo = MachineRepository(conn, logger=logger)
        self.operator_repo = OperatorRepository(conn, logger=logger)
        self.operator_machine_repo = OperatorMachineRepository(conn, logger=logger)
        self.supplier_repo = SupplierRepository(conn, logger=logger)

        self.schedule_repo = ScheduleRepository(conn, logger=logger)
        self.history_repo = ScheduleHistoryRepository(conn, logger=logger)

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
        if not batch_ids:
            raise ValidationError("请至少选择 1 个批次执行排产。", field="batch_ids")

        # 去重 + 保序
        normalized: List[str] = []
        seen = set()
        for x in batch_ids:
            bid = self._normalize_text(x)
            if not bid:
                continue
            if bid in seen:
                continue
            seen.add(bid)
            normalized.append(bid)
        if not normalized:
            raise ValidationError("请至少选择 1 个批次执行排产。", field="batch_ids")

        t0 = time.time()
        start_dt_norm: Optional[datetime] = None
        start_dt_provided = start_dt is not None and str(start_dt).strip() != ""
        if start_dt_provided:
            start_dt_norm = self._normalize_datetime(start_dt)
            if start_dt_norm is None:
                raise ValidationError(
                    "start_dt 格式不合法（允许：YYYY-MM-DD / YYYY-MM-DD HH:MM(:SS)）",
                    field="start_dt",
                )
        else:
            tomorrow = (datetime.now() + timedelta(days=1)).date()
            start_dt_norm = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 8, 0, 0)
        created_by_text = self._normalize_text(created_by) or "system"
        run_label = "模拟排产" if simulate else "排产"

        end_date_norm = None
        if end_date is not None and str(end_date).strip() != "":
            dt = self._normalize_datetime(end_date)
            if not dt:
                raise ValidationError("end_date 格式不合法（期望：YYYY-MM-DD）", field="end_date")
            end_date_norm = dt.date()
            if end_date_norm < start_dt_norm.date():
                raise ValidationError("end_date 不能早于 start_dt 所在日期", field="end_date")

        # 读取配置与日历服务（避免从包 __init__ 导入导致循环）
        from .calendar_service import CalendarService
        from .config_service import ConfigService

        cal_svc = CalendarService(self.conn, logger=self.logger, op_logger=self.op_logger)
        cfg_svc = ConfigService(self.conn, logger=self.logger, op_logger=self.op_logger)
        cfg = _get_snapshot_with_optional_strict_mode(cfg_svc, strict_mode=bool(strict_mode))
        if enforce_ready is None:
            enforce_ready_effective = (
                to_yes_no(getattr(cfg, "enforce_ready_default", YesNo.NO.value), default=YesNo.NO.value) == YesNo.YES.value
            )
        elif isinstance(enforce_ready, str):
            enforce_ready_effective = to_yes_no(enforce_ready, default=YesNo.NO.value) == YesNo.YES.value
        else:
            enforce_ready_effective = bool(enforce_ready)

        # 读取批次与工序
        batches: Dict[str, Batch] = {}
        operations: List[BatchOperation] = []
        blocked_batch_ids: List[str] = []
        for bid in normalized:
            b = self._get_batch_or_raise(bid)
            batches[bid] = b
            if _normalized_status_text(getattr(b, "status", None)) in _FAIL_FAST_BATCH_STATUSES:
                blocked_batch_ids.append(bid)
                continue
            operations.extend(self.op_repo.list_by_batch(bid))
        if blocked_batch_ids:
            sample = "，".join(blocked_batch_ids[:20])
            raise ValidationError(f"以下批次状态不允许排产（completed/cancelled）：{sample}", field="批次")

        reschedulable_operations = [op for op in operations if self._is_reschedulable_operation(op)]
        reschedulable_op_ids = {
            int(getattr(op, "id", 0) or 0)
            for op in reschedulable_operations
            if op and getattr(op, "id", None) and int(getattr(op, "id", 0) or 0) > 0
        }
        if not reschedulable_operations:
            _raise_schedule_empty_result(
                f"所选批次没有可重排工序，本次未执行{run_label}。",
                reason="no_reschedulable_operations",
            )

        # 自动分配资源：记录哪些内部工序原本缺省 machine/operator（便于在“非模拟”时回写补全）
        missing_internal_resource_op_ids = {
            int(op.id)
            for op in reschedulable_operations
            if op
            and op.id
            and (op.source or "").strip().lower() == SourceType.INTERNAL.value
            and (((op.machine_id or "").strip() == "") or ((op.operator_id or "").strip() == ""))
        }

        # 齐套约束（可选）：仅允许排产“齐套=yes”的批次
        if enforce_ready_effective:
            not_ready = [
                bid
                for bid, b in batches.items()
                if (self._normalize_text(getattr(b, "ready_status", None)) or "").strip().lower() != ReadyStatus.YES.value
            ]
            if not_ready:
                sample = "，".join(not_ready[:20])
                raise ValidationError(f"以下批次未齐套（ready_status!=yes），禁止排产：{sample}", field="齐套")

        # 算法输入（补充 merged 外部组信息）
        algo_input_outcome = _build_algo_operations_with_optional_outcome(
            self, reschedulable_operations, strict_mode=bool(strict_mode)
        )
        algo_ops = list(algo_input_outcome.value or [])

        # 上一版本号（供冻结窗口复用使用）
        latest = self.history_repo.get_latest_version()
        prev_version = int(latest or 0)

        # 冻结窗口（可选）
        frozen_op_ids, seed_results, algo_warnings, freeze_meta = _build_freeze_window_seed_with_optional_meta(
            self,
            cfg=cfg,
            prev_version=prev_version,
            start_dt=start_dt_norm,
            operations=operations,
            reschedulable_operations=reschedulable_operations,
            strict_mode=bool(strict_mode),
        )

        # 防御：warnings 预期为 list，但外部 stub/历史调用可能返回 None
        if algo_warnings is None:
            algo_warnings = []

        algo_ops_to_schedule = [x for x in algo_ops if int(getattr(x, "id", 0) or 0) not in frozen_op_ids]
        if not algo_ops_to_schedule:
            _raise_schedule_empty_result(
                f"冻结窗口内无可调整工序，本次未执行{run_label}。",
                reason="all_operations_frozen",
            )

        # 停机区间（用于算法避让）
        downtime_meta: Dict[str, Any] = {}
        resource_pool_meta: Dict[str, Any] = {}
        downtime_map = load_machine_downtimes(
            self,
            algo_ops=algo_ops,
            start_dt=start_dt_norm,
            warnings=algo_warnings,
            meta=downtime_meta,
        )

        # 自动分配资源池（可选）
        resource_pool, pool_warnings = build_resource_pool(self, cfg=cfg, algo_ops=algo_ops, meta=resource_pool_meta)
        pool_warnings = list(pool_warnings or [])
        if pool_warnings:
            algo_warnings.extend(pool_warnings)

        # auto-assign 启用时：停机区间覆盖候选设备
        downtime_map = extend_downtime_map_for_resource_pool(
            self,
            cfg=cfg,
            resource_pool=resource_pool,
            downtime_map=downtime_map,
            start_dt=start_dt_norm,
            warnings=algo_warnings,
            meta=downtime_meta,
        )

        # 算法阶段仅使用一个稳定种子版本，真正版本号延后到确认可落库后再原子分配，
        # 避免“无有效排程行”这类失败路径占用版本号序列。
        optimizer_seed_version = max(int(prev_version) + 1, 1)

        outcome = optimize_schedule(
            calendar_service=cal_svc,
            cfg_svc=cfg_svc,
            cfg=cfg,
            algo_ops_to_schedule=algo_ops_to_schedule,
            batches=batches,
            start_dt=start_dt_norm,
            end_date=end_date_norm,
            downtime_map=downtime_map,
            seed_results=seed_results,
            resource_pool=resource_pool,
            version=optimizer_seed_version,
            logger=self.logger,
            strict_mode=bool(strict_mode),
        )

        results = outcome.results
        summary = outcome.summary
        used_strategy = outcome.used_strategy
        used_params = outcome.used_params
        best_metrics = outcome.metrics
        best_score = outcome.best_score
        best_order = outcome.best_order
        attempts = outcome.attempts
        improvement_trace = outcome.improvement_trace
        algo_mode = outcome.algo_mode
        objective_name = outcome.objective_name
        algo_stats = getattr(outcome, "algo_stats", {}) or {}
        time_budget_seconds = outcome.time_budget_seconds

        has_actionable_schedule = has_actionable_schedule_rows(results, allowed_op_ids=set(reschedulable_op_ids))
        if not has_actionable_schedule:
            _raise_schedule_empty_result(
                f"优化结果未生成有效可落库排程行，本次未执行{run_label}。",
                reason="no_actionable_schedule_rows",
            )

        warning_merge_status: Dict[str, Any] = {
            "summary_merge_attempted": bool(algo_warnings),
            "summary_merge_failed": False,
            "summary_merge_error": None,
        }
        # 把“冻结窗口/资源池”等 warning 合并到算法 warning 中
        if algo_warnings:
            summary.warnings.extend(algo_warnings)

        # 仅在确认存在可落库结果后再占用正式版本号，避免空结果推进序列。
        # 这里仍使用数据库原子分配，保持跨进程唯一递增语义。
        with self.tx_manager.transaction():
            version = int(self.history_repo.allocate_next_version())

        overdue_items, result_status, result_summary_obj, result_summary_json, time_cost_ms = build_result_summary(
            self,
            cfg=cfg,
            version=version,
            normalized_batch_ids=normalized,
            start_dt=start_dt_norm,
            end_date=end_date_norm,
            batches=batches,
            operations=operations,
            results=results,
            summary=summary,
            used_strategy=used_strategy,
            used_params=used_params,
            algo_mode=algo_mode,
            objective_name=objective_name,
            time_budget_seconds=int(time_budget_seconds),
            best_score=best_score,
            best_metrics=best_metrics,
            best_order=best_order,
            attempts=attempts,
            improvement_trace=improvement_trace,
            frozen_op_ids=set(frozen_op_ids),
            freeze_meta=freeze_meta,
            input_build_outcome=algo_input_outcome,
            downtime_meta=downtime_meta,
            resource_pool_meta=resource_pool_meta,
            algo_stats=algo_stats,
            algo_warnings=list(algo_warnings or []),
            warning_merge_status=warning_merge_status,
            simulate=simulate,
            t0=t0,
        )

        persist_schedule(
            self,
            cfg=cfg,
            version=version,
            results=results,
            summary=summary,
            used_strategy=used_strategy,
            used_params=used_params,
            batches=batches,
            operations=operations,
            reschedulable_operations=reschedulable_operations,
            reschedulable_op_ids=set(reschedulable_op_ids),
            normalized_batch_ids=normalized,
            created_by=created_by_text,
            has_actionable_schedule=has_actionable_schedule,
            simulate=simulate,
            frozen_op_ids=set(frozen_op_ids),
            result_status=result_status,
            result_summary_json=result_summary_json,
            result_summary_obj=result_summary_obj,
            missing_internal_resource_op_ids=missing_internal_resource_op_ids,
            overdue_items=overdue_items,
            time_cost_ms=time_cost_ms,
        )

        return {
            "is_simulation": bool(simulate),
            "version": int(version),
            "strategy": used_strategy.value,
            "strategy_params": used_params or {},
            "result_status": result_status,
            "summary": {
                "success": getattr(summary, "success", False),
                "total_ops": int(getattr(summary, "total_ops", 0)),
                "scheduled_ops": int(getattr(summary, "scheduled_ops", 0)),
                "failed_ops": int(getattr(summary, "failed_ops", 0)),
                "warnings": getattr(summary, "warnings", None),
                "errors": getattr(summary, "errors", None),
                "duration_seconds": getattr(summary, "duration_seconds", 0.0),
            },
            "overdue_batches": overdue_items,
            "time_cost_ms": int(time_cost_ms),
        }

