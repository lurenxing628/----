from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.algorithms import GreedyScheduler, SortStrategy
from core.models import Batch, BatchOperation, ExternalGroup, PartOperation
from core.models.enums import BatchStatus, MergeMode, OperatorStatus, SourceType
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
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None if allow_none else 0.0
        try:
            return float(value)
        except Exception:
            raise ValidationError(f"“{field}”必须是数字", field=field)

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
        s = s.replace("/", "-")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        return None

    @dataclass
    class _OpForScheduleAlgo:
        """算法输入工序（补充 merged 外部组信息）。"""

        id: int
        op_code: str
        batch_id: str
        seq: int
        source: str
        machine_id: Optional[str]
        operator_id: Optional[str]
        supplier_id: Optional[str]
        setup_hours: float
        unit_hours: float
        ext_days: Optional[float]
        # 外部组信息（来自 PartOperations + ExternalGroups）
        ext_group_id: Optional[str]
        ext_merge_mode: Optional[str]
        ext_group_total_days: Optional[float]

    # -------------------------
    # 查询
    # -------------------------
    def list_batch_operations(self, batch_id: Any) -> List[BatchOperation]:
        bid = self._normalize_text(batch_id)
        if not bid:
            raise ValidationError("“批次号”不能为空", field="批次号")
        self._get_batch_or_raise(bid)
        return self.op_repo.list_by_batch(bid)

    def get_operation(self, op_id: Any) -> BatchOperation:
        try:
            oid = int(op_id)
        except Exception:
            raise ValidationError("工序ID 不合法", field="op_id")
        return self._get_op_or_raise(oid)

    def get_external_merge_hint(self, op_id: Any) -> Dict[str, Any]:
        """
        返回外部工序“合并周期”提示信息（供页面展示）。
        """
        op = self.get_operation(op_id)
        if op.source != SourceType.EXTERNAL.value:
            return {"is_external": False}

        tmpl, grp = self._get_template_and_group_for_op(op)
        if not tmpl or not grp:
            return {"is_external": True, "merge_mode": None}
        return {
            "is_external": True,
            "template_ext_group_id": tmpl.ext_group_id,
            "merge_mode": grp.merge_mode,
            "group_total_days": grp.total_days,
        }

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
        """
        内部工序补充信息：
        - machine_id/operator_id 可选（允许清空）
        - setup_hours/unit_hours 非负（允许为空，空视为 0）
        """
        op = self.get_operation(op_id)
        if op.id is None:
            raise BusinessError(ErrorCode.NOT_FOUND, f"批次工序（ID={op_id}）不存在")
        if op.source != SourceType.INTERNAL.value:
            raise ValidationError("只能编辑内部工序的设备/人员/工时信息", field="source")

        mc_id = self._normalize_text(machine_id)
        op_id_text = self._normalize_text(operator_id)

        # 设备存在性 + 可用性（维护/停用时禁止分配）
        if mc_id:
            m = self.machine_repo.get(mc_id)
            if not m:
                raise BusinessError(ErrorCode.MACHINE_NOT_FOUND, f"设备“{mc_id}”不存在")
            if (m.status or "").strip() != "active":
                raise BusinessError(ErrorCode.MACHINE_NOT_AVAILABLE, f"设备“{mc_id}”当前状态为“{m.status}”，不可用于排产。")

        # 人员存在性 + 在岗性
        if op_id_text:
            person = self.operator_repo.get(op_id_text)
            if not person:
                raise BusinessError(ErrorCode.OPERATOR_NOT_FOUND, f"人员“{op_id_text}”不存在")
            if (person.status or "").strip() != OperatorStatus.ACTIVE.value:
                raise BusinessError(ErrorCode.RESOURCE_NOT_AVAILABLE, f"人员“{op_id_text}”当前状态为“{person.status}”，不可用于排产。")

        # 人员-设备匹配性（双向约束）：两者都选择时必须已维护可操作关联
        if mc_id and op_id_text:
            if not self.operator_machine_repo.exists(op_id_text, mc_id):
                op_code = op.op_code or "-"
                raise ValidationError(
                    f"人员“{op_id_text}”未被配置为可操作设备“{mc_id}”（工序 {op_code} / ID={op.id}）。"
                    f"请先在【人员管理】或【设备管理】中维护人机关联（OperatorMachine）后再排产。",
                    field="设备/人员",
                )

        sh = self._normalize_float(setup_hours, field="换型时间(小时)", allow_none=True)
        uh = self._normalize_float(unit_hours, field="单件工时(小时)", allow_none=True)
        sh = 0.0 if sh is None else float(sh)
        uh = 0.0 if uh is None else float(uh)
        if sh < 0 or uh < 0:
            raise ValidationError("工时不能为负数", field="工时")

        updates: Dict[str, Any] = {
            "machine_id": mc_id,
            "operator_id": op_id_text,
            "setup_hours": float(sh),
            "unit_hours": float(uh),
        }
        if status is not None:
            updates["status"] = self._normalize_text(status)

        with self.tx_manager.transaction():
            self.op_repo.update(int(op.id), updates)

        return self._get_op_or_raise(int(op.id))

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
        """
        外部工序补充信息：
        - supplier_id 可选（允许清空）
        - ext_days 必须 >0（merged 外部组时禁止逐道设置）
        """
        op = self.get_operation(op_id)
        if op.id is None:
            raise BusinessError(ErrorCode.NOT_FOUND, f"批次工序（ID={op_id}）不存在")
        if op.source != SourceType.EXTERNAL.value:
            raise ValidationError("只能编辑外部工序的供应商/周期信息", field="source")

        sup_id = self._normalize_text(supplier_id)
        if sup_id:
            s = self.supplier_repo.get(sup_id)
            if not s:
                raise BusinessError(ErrorCode.NOT_FOUND, f"供应商“{sup_id}”不存在")
            if (s.status or "").strip() != "active":
                raise BusinessError(ErrorCode.RESOURCE_NOT_AVAILABLE, f"供应商“{sup_id}”已停用，不可用于排产。")

        # 合并周期（merged）时：周期不在 BatchOperations.ext_days 上维护
        tmpl, grp = self._get_template_and_group_for_op(op)
        if grp and grp.merge_mode == MergeMode.MERGED.value:
            if ext_days is not None and self._normalize_text(ext_days) is not None:
                td = grp.total_days
                td_text = f"{td} 天" if td is not None else "（未设置）"
                raise ValidationError(
                    f"该外部工序属于“合并周期”外部组，不能逐道设置周期。请在工艺管理中设置该组的合并周期（当前：{td_text}）。",
                    field="周期",
                )
            # merged：保持 ext_days 为 NULL，避免误导
            ext_days_value = None
        else:
            dv = self._normalize_float(ext_days, field="外协周期(天)", allow_none=True)
            if dv is None:
                # 用户没填：兜底 1 天（避免后续排产无法计算）
                dv = 1.0
            if dv <= 0:
                raise ValidationError("“外协周期(天)”必须大于 0", field="外协周期(天)")
            ext_days_value = float(dv)

        updates: Dict[str, Any] = {"supplier_id": sup_id, "ext_days": ext_days_value}
        if status is not None:
            updates["status"] = self._normalize_text(status)

        with self.tx_manager.transaction():
            self.op_repo.update(int(op.id), updates)

        return self._get_op_or_raise(int(op.id))

    # -------------------------
    # Phase 7：执行排产（算法 + 落库 + 留痕）
    # -------------------------
    def run_schedule(
        self,
        batch_ids: List[str],
        start_dt: Any = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行排产并落库（Schedule）+ 留痕（ScheduleHistory + OperationLogs）。

        说明：
        - 版本号：从 ScheduleHistory.max(version)+1 递增
        - Schedule 写入、状态更新、ScheduleHistory 写入：**单事务原子**
        - OperationLogs：由于 OperationLogger 内部会 commit()，因此放到事务提交后写入，避免破坏原子性
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
        start_dt_norm = self._normalize_datetime(start_dt) or datetime.now()
        created_by_text = self._normalize_text(created_by) or "system"

        # 读取配置与日历服务（避免从包 __init__ 导入导致循环）
        from .calendar_service import CalendarService
        from .config_service import ConfigService

        cal_svc = CalendarService(self.conn, logger=self.logger, op_logger=self.op_logger)
        cfg_svc = ConfigService(self.conn, logger=self.logger, op_logger=self.op_logger)
        cfg = cfg_svc.get_snapshot()

        # 读取批次与工序
        batches: Dict[str, Batch] = {}
        operations: List[BatchOperation] = []
        for bid in normalized:
            b = self._get_batch_or_raise(bid)
            batches[bid] = b
            operations.extend(self.op_repo.list_by_batch(bid))

        # 构建算法输入（补充 merged 外部组信息）
        algo_ops: List[ScheduleService._OpForScheduleAlgo] = []
        for op in operations:
            ext_group_id = None
            merge_mode = None
            total_days = None
            if (op.source or "").strip() == SourceType.EXTERNAL.value:
                tmpl, grp = self._get_template_and_group_for_op(op)
                ext_group_id = (tmpl.ext_group_id if tmpl else None) if tmpl else None
                merge_mode = grp.merge_mode if grp else None
                total_days = grp.total_days if grp else None

            algo_ops.append(
                self._OpForScheduleAlgo(
                    id=int(op.id or 0),
                    op_code=op.op_code,
                    batch_id=op.batch_id,
                    seq=int(op.seq or 0),
                    source=op.source,
                    machine_id=op.machine_id,
                    operator_id=op.operator_id,
                    supplier_id=op.supplier_id,
                    setup_hours=float(op.setup_hours or 0.0),
                    unit_hours=float(op.unit_hours or 0.0),
                    ext_days=float(op.ext_days) if op.ext_days is not None and op.ext_days != "" else None,
                    ext_group_id=ext_group_id,
                    ext_merge_mode=merge_mode,
                    ext_group_total_days=float(total_days) if total_days is not None and total_days != "" else None,
                )
            )

        # 生成版本号（递增）
        latest = self.history_repo.get_latest_version()
        version = int(latest) + 1

        # 执行算法
        scheduler = GreedyScheduler(calendar_service=cal_svc, config_service=cfg_svc, logger=self.logger)
        strategy_enum: Optional[SortStrategy] = None
        try:
            strategy_enum = SortStrategy(cfg.sort_strategy)
        except Exception:
            strategy_enum = None

        strategy_params: Optional[Dict[str, Any]] = None
        if (cfg.sort_strategy or "").strip() == SortStrategy.WEIGHTED.value:
            strategy_params = {
                "priority_weight": float(cfg.priority_weight),
                "due_weight": float(cfg.due_weight),
                "ready_weight": float(cfg.ready_weight),
            }

        results, summary, used_strategy, used_params = scheduler.schedule(
            operations=algo_ops,
            batches=batches,
            strategy=strategy_enum,
            strategy_params=strategy_params,
            start_dt=start_dt_norm,
        )

        # 超期预警：批次预计完工时间 vs due_date
        overdue_items: List[Dict[str, Any]] = []
        finish_by_batch: Dict[str, datetime] = {}
        for r in results:
            if not r.end_time:
                continue
            cur = finish_by_batch.get(r.batch_id)
            if (cur is None) or (r.end_time > cur):
                finish_by_batch[r.batch_id] = r.end_time

        for bid, b in batches.items():
            due = self._normalize_text(b.due_date)
            if not due:
                continue
            try:
                due_date = datetime.strptime(due.replace("/", "-"), "%Y-%m-%d").date()
            except Exception:
                continue
            finish = finish_by_batch.get(bid)
            if not finish:
                continue
            if finish.date() > due_date:
                overdue_items.append(
                    {
                        "batch_id": bid,
                        "due_date": due,
                        "finish_time": self._format_dt(finish),
                    }
                )

        # result_status：success/partial/failed
        if summary.success:
            result_status = "success"
        elif summary.scheduled_ops > 0:
            result_status = "partial"
        else:
            result_status = "failed"

        # result_summary（JSON）：按文档固定键名（至少包含 strategy_params / overdue_batches）
        time_cost_ms = int((time.time() - t0) * 1000)
        result_summary_obj: Dict[str, Any] = {
            "version": version,
            "strategy": used_strategy.value,
            "strategy_params": used_params or {},
            "selected_batch_ids": list(normalized),
            "start_time": self._format_dt(start_dt_norm),
            "counts": {
                "batch_count": len(batches),
                "op_count": len(algo_ops),
                "scheduled_ops": summary.scheduled_ops,
                "failed_ops": summary.failed_ops,
            },
            "overdue_batches": {"count": len(overdue_items), "items": overdue_items},
            "errors_sample": (summary.errors or [])[:10],
            "warnings": summary.warnings or [],
            "time_cost_ms": time_cost_ms,
        }
        result_summary_json = json.dumps(result_summary_obj, ensure_ascii=False)

        # 组装 Schedule 落库行
        schedule_rows: List[Dict[str, Any]] = []
        for r in results:
            if not r.start_time or not r.end_time:
                continue
            schedule_rows.append(
                {
                    "op_id": int(r.op_id),
                    "machine_id": r.machine_id,
                    "operator_id": r.operator_id,
                    "start_time": self._format_dt(r.start_time),
                    "end_time": self._format_dt(r.end_time),
                    "lock_status": "unlocked",
                    "version": int(version),
                }
            )

        # 原子落库：Schedule + 状态更新 + ScheduleHistory
        with self.tx_manager.transaction():
            if schedule_rows:
                self.schedule_repo.bulk_create(schedule_rows)

            # 批次工序：成功排到的置 scheduled；失败的保持原状态（便于继续补全）
            scheduled_op_ids = {int(r.op_id) for r in results if r and r.op_id}
            for op in operations:
                if not op.id:
                    continue
                if int(op.id) in scheduled_op_ids:
                    self.op_repo.update(int(op.id), {"status": "scheduled"})

            # 批次：若本批次所有工序都排到 -> scheduled，否则保持 pending
            by_batch_total: Dict[str, int] = {}
            by_batch_scheduled: Dict[str, int] = {}
            for op in operations:
                by_batch_total[op.batch_id] = by_batch_total.get(op.batch_id, 0) + 1
                if op.id and int(op.id) in scheduled_op_ids:
                    by_batch_scheduled[op.batch_id] = by_batch_scheduled.get(op.batch_id, 0) + 1

            for bid, b in batches.items():
                total = by_batch_total.get(bid, 0)
                ok = by_batch_scheduled.get(bid, 0)
                new_status = BatchStatus.SCHEDULED.value if total > 0 and ok == total else BatchStatus.PENDING.value
                self.batch_repo.update(bid, {"status": new_status})

            # 排产历史留痕（DB）
            self.history_repo.create(
                {
                    "version": int(version),
                    "strategy": used_strategy.value,
                    "batch_count": len(batches),
                    "op_count": len(algo_ops),
                    "result_status": result_status,
                    "result_summary": result_summary_json,
                    "created_by": created_by_text,
                }
            )

        # 操作日志留痕（OperationLogs）：放到事务后（避免内部 commit 干扰原子性）
        if self.op_logger is not None:
            detail = {
                "version": int(version),
                "strategy": used_strategy.value,
                "strategy_params": used_params or {},
                "batch_ids": list(normalized),
                "batch_count": len(batches),
                "op_count": len(algo_ops),
                "scheduled_ops": summary.scheduled_ops,
                "failed_ops": summary.failed_ops,
                "result_status": result_status,
                "overdue_count": len(overdue_items),
                "overdue_batches_sample": overdue_items[:10],
                "time_cost_ms": time_cost_ms,
            }
            self.op_logger.info(
                module="scheduler",
                action="schedule",
                target_type="schedule",
                target_id=str(version),
                detail=detail,
            )

        return {
            "version": int(version),
            "strategy": used_strategy.value,
            "strategy_params": used_params or {},
            "result_status": result_status,
            "summary": {
                "success": summary.success,
                "total_ops": summary.total_ops,
                "scheduled_ops": summary.scheduled_ops,
                "failed_ops": summary.failed_ops,
                "warnings": summary.warnings,
                "errors": summary.errors,
                "duration_seconds": summary.duration_seconds,
            },
            "overdue_batches": overdue_items,
            "time_cost_ms": time_cost_ms,
        }

