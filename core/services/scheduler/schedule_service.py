from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import Batch, BatchOperation, ExternalGroup, PartOperation
from core.models.enums import SourceType
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
from .schedule_persistence import persist_schedule
from .schedule_summary import build_result_summary


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
        if value is None:
            return None
        if isinstance(value, str):
            v = value.strip()
            return v if v != "" else None
        v = str(value).strip()
        return v if v != "" else None

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
        """
        通过 Batch.part_no + op.seq 回查“零件模板工序”与“外部组”信息。

        说明：BatchOperations 表不存 ext_group_id，因此这里以模板为事实来源。
        """
        batch = self._get_batch_or_raise(op.batch_id)
        tmpl = self.part_op_repo.get(batch.part_no, int(op.seq))
        if not tmpl:
            return None, None
        if not tmpl.ext_group_id:
            return tmpl, None
        grp = self.group_repo.get(tmpl.ext_group_id)
        return tmpl, grp

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
        cfg = cfg_svc.get_snapshot()
        if enforce_ready is None:
            enforce_ready_effective = to_yes_no(getattr(cfg, "enforce_ready_default", "no"), default="no") == "yes"
        elif isinstance(enforce_ready, str):
            enforce_ready_effective = to_yes_no(enforce_ready, default="no") == "yes"
        else:
            enforce_ready_effective = bool(enforce_ready)

        # 读取批次与工序
        batches: Dict[str, Batch] = {}
        operations: List[BatchOperation] = []
        for bid in normalized:
            b = self._get_batch_or_raise(bid)
            batches[bid] = b
            operations.extend(self.op_repo.list_by_batch(bid))

        # 自动分配资源：记录哪些内部工序原本缺省 machine/operator（便于在“非模拟”时回写补全）
        missing_internal_resource_op_ids = {
            int(op.id)
            for op in operations
            if op
            and op.id
            and (op.source or "").strip().lower() == SourceType.INTERNAL.value
            and (((op.machine_id or "").strip() == "") or ((op.operator_id or "").strip() == ""))
        }

        # 齐套约束（可选）：仅允许排产“齐套=yes”的批次
        if enforce_ready_effective:
            not_ready = [
                bid for bid, b in batches.items() if (self._normalize_text(getattr(b, "ready_status", None)) or "") != "yes"
            ]
            if not_ready:
                sample = "，".join(not_ready[:20])
                raise ValidationError(f"以下批次未齐套（ready_status!=yes），禁止排产：{sample}", field="齐套")

        # 算法输入（补充 merged 外部组信息）
        algo_ops = build_algo_operations(self, operations)

        # 上一版本号（供冻结窗口复用使用）
        latest = self.history_repo.get_latest_version()
        prev_version = int(latest or 0)

        # 分配新版本号（数据库原子分配；避免并发下 MAX(version)+1 复用）
        # 注意：只占用极短写事务，避免长时间锁库影响算法执行。
        with self.tx_manager.transaction():
            version = int(self.history_repo.allocate_next_version())

        # 冻结窗口（可选）
        frozen_op_ids, seed_results, algo_warnings = build_freeze_window_seed(
            self, cfg=cfg, prev_version=prev_version, start_dt=start_dt_norm, operations=operations
        )

        # 防御：warnings 预期为 list，但外部 stub/历史调用可能返回 None
        if algo_warnings is None:
            algo_warnings = []

        # 停机区间（用于算法避让）
        downtime_meta: Dict[str, Any] = {}
        downtime_map = load_machine_downtimes(
            self,
            algo_ops=algo_ops,
            start_dt=start_dt_norm,
            warnings=algo_warnings,
            meta=downtime_meta,
        )

        # 自动分配资源池（可选）
        resource_pool, pool_warnings = build_resource_pool(self, cfg=cfg, algo_ops=algo_ops)
        if pool_warnings:
            try:
                if algo_warnings is None:
                    algo_warnings = []
                algo_warnings.extend(list(pool_warnings))
            except Exception:
                try:
                    algo_warnings = list(algo_warnings or []) + list(pool_warnings or [])
                except Exception:
                    algo_warnings = list(pool_warnings or [])

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

        # 过滤掉冻结工序（由 seed_results 复用）
        algo_ops_to_schedule = [x for x in algo_ops if int(getattr(x, "id", 0) or 0) not in frozen_op_ids]

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
            version=version,
            logger=self.logger,
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
        time_budget_seconds = outcome.time_budget_seconds

        # 把“冻结窗口/资源池”等 warning 合并到算法 warning 中
        if algo_warnings:
            try:
                summary.warnings.extend(list(algo_warnings))  # type: ignore[attr-defined]
            except Exception:
                try:
                    existing = getattr(summary, "warnings", None)
                    if isinstance(existing, list):
                        merged = list(existing) + list(algo_warnings)
                    elif isinstance(existing, tuple):
                        merged = list(existing) + list(algo_warnings)
                    elif existing is None:
                        merged = list(algo_warnings)
                    else:
                        merged = list(algo_warnings)
                    setattr(summary, "warnings", merged)
                except Exception:
                    pass

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
            downtime_meta=downtime_meta,
            simulate=simulate,
            t0=t0,
        )

        persist_schedule(
            self,
            version=version,
            results=results,
            summary=summary,
            used_strategy=used_strategy,
            used_params=used_params,
            batches=batches,
            operations=operations,
            normalized_batch_ids=normalized,
            created_by=created_by_text,
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

