from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.algorithms import BatchForSort, GreedyScheduler, ScheduleResult, SortStrategy, StrategyFactory
from core.algorithms.evaluation import compute_metrics, objective_score
from core.models import Batch, BatchOperation, ExternalGroup, PartOperation
from core.models.enums import BatchStatus, MergeMode, OperatorStatus, SourceType
from data.repositories import (
    BatchOperationRepository,
    BatchRepository,
    ExternalGroupRepository,
    MachineRepository,
    MachineDowntimeRepository,
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
        s = s.replace("/", "-").replace("T", " ").replace("：", ":")
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
        op_type_id: Optional[str]
        op_type_name: Optional[str]
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
        end_date: Any = None,
        created_by: Optional[str] = None,
        simulate: bool = False,
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
        start_dt_norm = self._normalize_datetime(start_dt)
        if start_dt_norm is None:
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
            if op and op.id and (op.source or "").strip() == SourceType.INTERNAL.value and ((op.machine_id or "").strip() == "" or (op.operator_id or "").strip() == "")
        }

        # 仅允许排产“齐套=yes”的批次（其余直接提示，不参与排产）
        not_ready = [bid for bid, b in batches.items() if (self._normalize_text(getattr(b, "ready_status", None)) or "") != "yes"]
        if not_ready:
            sample = "，".join(not_ready[:20])
            raise ValidationError(f"以下批次未齐套（ready_status!=yes），禁止排产：{sample}", field="齐套")

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
                    op_type_id=getattr(op, "op_type_id", None),
                    op_type_name=getattr(op, "op_type_name", None),
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
        prev_version = int(latest or 0)
        version = prev_version + 1

        # -------------------------
        # 可选优化项：冻结窗口（硬约束，默认关闭）
        # - 复用上一版本在“窗口内”的排程结果，不再重排
        # - 为保证批次前后约束：按批次 seq 前缀冻结（冻结到窗口内出现的最大 seq）
        # -------------------------
        frozen_op_ids: set = set()
        seed_results: List[Any] = []
        algo_warnings: List[str] = []
        if (
            getattr(cfg, "freeze_window_enabled", "no") == "yes"
            and int(getattr(cfg, "freeze_window_days", 0) or 0) > 0
            and prev_version > 0
        ):
            freeze_days = int(getattr(cfg, "freeze_window_days", 0) or 0)
            freeze_end = start_dt_norm + timedelta(days=freeze_days)
            freeze_end_str = self._format_dt(freeze_end)
            start_str = self._format_dt(start_dt_norm)

            op_by_id: Dict[int, BatchOperation] = {int(op.id): op for op in operations if op and op.id}
            op_ids_all = sorted(list(op_by_id.keys()))

            # 查询上一版本在窗口内的排程（仅查本次选中批次的工序）
            schedule_map: Dict[int, Dict[str, Any]] = {}
            try:
                chunk_size = 900  # sqlite 默认变量上限 999，留余量
                for i in range(0, len(op_ids_all), chunk_size):
                    chunk = op_ids_all[i : i + chunk_size]
                    placeholders = ",".join(["?"] * len(chunk))
                    rows = self.conn.execute(
                        f"""
                        SELECT op_id, machine_id, operator_id, start_time, end_time
                        FROM Schedule
                        WHERE version = ?
                          AND op_id IN ({placeholders})
                          AND start_time >= ?
                          AND start_time < ?
                        """,
                        tuple([int(prev_version)] + [int(x) for x in chunk] + [start_str, freeze_end_str]),
                    ).fetchall()
                    for r in rows:
                        try:
                            schedule_map[int(r["op_id"])] = dict(r)
                        except Exception:
                            continue
            except Exception as e:
                schedule_map = {}
                algo_warnings.append(f"冻结窗口启用但读取上一版本排程失败：{e}")

            # 冻结到窗口内出现的最大 seq（按批次前缀冻结）
            if schedule_map:
                max_seq_by_batch: Dict[str, int] = {}
                seed_tmp: Dict[int, Dict[str, Any]] = {}
                for oid in schedule_map.keys():
                    op0 = op_by_id.get(int(oid))
                    if not op0:
                        continue
                    bid = str(op0.batch_id or "")
                    seq0 = int(op0.seq or 0)
                    if seq0 <= 0:
                        continue
                    max_seq_by_batch[bid] = max(max_seq_by_batch.get(bid, 0), seq0)

                for bid, max_seq in max_seq_by_batch.items():
                    if max_seq <= 0:
                        continue
                    prefix = [int(op.id) for op in operations if op and op.id and op.batch_id == bid and int(op.seq or 0) <= max_seq]
                    missing = [oid for oid in prefix if oid not in schedule_map]
                    if missing:
                        sample = ", ".join([str(x) for x in missing[:5]])
                        algo_warnings.append(f"冻结窗口跳过批次 {bid}：上一版本缺少前缀工序排程（示例 op_id={sample}）")
                        continue
                    # 校验时间有效（否则不冻结该批次，避免“冻结但无有效区间”导致工序丢失）
                    invalid_oid = None
                    for oid in prefix:
                        row = schedule_map.get(int(oid)) or {}
                        st = self._normalize_datetime(row.get("start_time"))
                        et = self._normalize_datetime(row.get("end_time"))
                        if not st or not et or et <= st:
                            invalid_oid = int(oid)
                            break
                        seed_tmp[int(oid)] = {"row": row, "start_time": st, "end_time": et}
                    if invalid_oid is not None:
                        algo_warnings.append(f"冻结窗口跳过批次 {bid}：上一版本工序时间无效（op_id={invalid_oid}）")
                        # 清理该批次临时缓存
                        for oid in prefix:
                            seed_tmp.pop(int(oid), None)
                        continue
                    for oid in prefix:
                        frozen_op_ids.add(int(oid))

                # 生成 seed_results（用于算法占用资源 + 新版本回写）
                for oid in sorted(frozen_op_ids):
                    op0 = op_by_id.get(oid)
                    seed = seed_tmp.get(oid)
                    if not op0 or not seed:
                        continue
                    row = seed.get("row")
                    st = seed.get("start_time")
                    et = seed.get("end_time")
                    if not row or not st or not et:
                        continue
                    seed_results.append(
                        {
                            "op_id": oid,
                            "op_code": op0.op_code,
                            "batch_id": op0.batch_id,
                            "seq": int(op0.seq or 0),
                            "machine_id": row.get("machine_id"),
                            "operator_id": row.get("operator_id"),
                            "start_time": st,
                            "end_time": et,
                            "source": (op0.source or "internal").strip(),
                            "op_type_name": getattr(op0, "op_type_name", None),
                        }
                    )

                # 排序（便于人类阅读/留痕）
                seed_results.sort(key=lambda x: (x.get("start_time") or datetime.min, x.get("op_id") or 0))

        # 执行算法（支持 improve：多起点 + 目标函数 + 时间预算）
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
            }

        # 预加载停机区间（按设备维度展开后的记录），用于算法避让
        downtime_map: Dict[str, List[Tuple[datetime, datetime]]] = {}
        try:
            dt_repo = MachineDowntimeRepository(self.conn, logger=self.logger)
            start_str = self._format_dt(start_dt_norm)
            machine_ids = sorted(
                {
                    (op.machine_id or "").strip()
                    for op in algo_ops
                    if (op.source or "").strip() == SourceType.INTERNAL.value and (op.machine_id or "").strip()
                }
            )
            for mid in machine_ids:
                rows = dt_repo.list_active_after(mid, start_str)
                intervals: List[Tuple[datetime, datetime]] = []
                for d in rows:
                    st = self._normalize_datetime(d.start_time)
                    et = self._normalize_datetime(d.end_time)
                    if st and et and et > st:
                        intervals.append((st, et))
                if intervals:
                    intervals.sort(key=lambda x: x[0])
                    downtime_map[mid] = intervals
        except Exception:
            downtime_map = {}

        # 自动分配资源（可选）：预加载“可用资源池”（避免算法层重复查库）
        resource_pool: Optional[Dict[str, Any]] = None
        auto_assign_enabled = getattr(cfg, "auto_assign_enabled", "no") == "yes"
        if auto_assign_enabled:
            try:
                # 仅考虑 active 资源
                machines = self.machine_repo.list(status="active")
                active_machines = {str(m.machine_id or "").strip() for m in machines if m and str(m.machine_id or "").strip()}

                # 仅对本次排产涉及的 op_type_id 构建映射（缺省/为空则退化为全量）
                op_type_ids = {
                    str(getattr(o, "op_type_id", "") or "").strip()
                    for o in algo_ops
                    if (getattr(o, "source", "") or "").strip() == SourceType.INTERNAL.value and str(getattr(o, "op_type_id", "") or "").strip()
                }
                machines_by_op_type: Dict[str, List[str]] = {}
                for m in machines:
                    mid = str(m.machine_id or "").strip()
                    ot = str(m.op_type_id or "").strip()
                    if not mid or mid not in active_machines:
                        continue
                    if op_type_ids and ot and ot not in op_type_ids:
                        continue
                    machines_by_op_type.setdefault(ot, []).append(mid)

                active_ops = {str(o.operator_id or "").strip() for o in self.operator_repo.list(status="active") if o and str(o.operator_id or "").strip()}

                # OperatorMachine：一次性取出，按设备聚合（并按“主操/技能”做轻量排序）
                rows = self.conn.execute(
                    "SELECT operator_id, machine_id, skill_level, is_primary FROM OperatorMachine"
                ).fetchall()
                operators_by_machine: Dict[str, List[Tuple[int, str]]] = {}  # machine_id -> [(rank, operator_id)]
                machines_by_operator: Dict[str, List[str]] = {}
                pair_rank: Dict[Tuple[str, str], int] = {}

                def _skill_rank(v: Any) -> int:
                    """
                    技能等级排序（数值越小越优）。

                    兼容：
                    - 新口径：beginner/normal/expert（见 OperatorMachineService）
                    - 旧口径：low/normal/high（历史数据/脚本）
                    - 常见中文：初级/普通/熟练（以及 高级/专家/一般/中级/新手）
                    """
                    s0 = str(v or "").strip()
                    if s0 == "":
                        return 9
                    low = s0.lower()
                    if low in ("expert", "high", "skilled"):
                        return 0
                    if low in ("normal",):
                        return 1
                    if low in ("beginner", "low"):
                        return 2
                    if s0 in ("熟练", "高级", "专家"):
                        return 0
                    if s0 in ("普通", "一般", "中级"):
                        return 1
                    if s0 in ("初级", "新手"):
                        return 2
                    return 9

                for r in rows:
                    oid = str(r["operator_id"] or "").strip()
                    mid = str(r["machine_id"] or "").strip()
                    if not oid or not mid:
                        continue
                    if mid not in active_machines:
                        continue
                    if oid not in active_ops:
                        continue
                    is_primary = str(r["is_primary"] or "").strip().lower()
                    sr = _skill_rank(r["skill_level"])
                    rank = (0 if is_primary in ("yes", "y", "true", "1", "on") else 1) * 10 + sr
                    operators_by_machine.setdefault(mid, []).append((int(rank), oid))
                    machines_by_operator.setdefault(oid, []).append(mid)
                    pair_rank[(oid, mid)] = int(rank)

                # 排序：rank 越小越优（主操优先，其次高技能）
                operators_by_machine_sorted: Dict[str, List[str]] = {}
                for mid, items in operators_by_machine.items():
                    items.sort(key=lambda x: (x[0], x[1]))
                    operators_by_machine_sorted[mid] = [oid for _, oid in items]

                resource_pool = {
                    "machines_by_op_type": machines_by_op_type,
                    "operators_by_machine": operators_by_machine_sorted,
                    "machines_by_operator": machines_by_operator,
                    "pair_rank": pair_rank,
                }
            except Exception as e:
                resource_pool = None
                # 不阻断排产：自动分配降级为关闭，但要让用户/日志可观测
                try:
                    algo_warnings.append("自动分配资源池构建失败，已降级为不自动分配（请查看日志）。")
                except Exception:
                    pass
                if self.logger:
                    try:
                        self.logger.warning(f"自动分配资源池构建失败，已降级为不自动分配：{e}")
                    except Exception:
                        pass

        # auto-assign 启用时：停机区间需要覆盖“候选设备”，否则算法可能误排到停机段内
        if auto_assign_enabled and resource_pool and isinstance(resource_pool.get("operators_by_machine"), dict):
            try:
                dt_repo = MachineDowntimeRepository(self.conn, logger=self.logger)
                start_str = self._format_dt(start_dt_norm)
                extra_mids = sorted(
                    {
                        str(mid).strip()
                        for mid in (resource_pool.get("operators_by_machine") or {}).keys()
                        if str(mid).strip() and str(mid).strip() not in downtime_map
                    }
                )
                for mid in extra_mids:
                    rows = dt_repo.list_active_after(mid, start_str)
                    intervals: List[Tuple[datetime, datetime]] = []
                    for d in rows:
                        st = self._normalize_datetime(d.start_time)
                        et = self._normalize_datetime(d.end_time)
                        if st and et and et > st:
                            intervals.append((st, et))
                    if intervals:
                        intervals.sort(key=lambda x: x[0])
                        downtime_map[mid] = intervals
            except Exception:
                pass

        # 过滤掉冻结工序（由 seed_results 复用）
        algo_ops_to_schedule = [x for x in algo_ops if int(getattr(x, "id", 0) or 0) not in frozen_op_ids]

        algo_mode = (getattr(cfg, "algo_mode", "greedy") or "greedy").strip()
        objective_name = (getattr(cfg, "objective", "min_overdue") or "min_overdue").strip()
        time_budget_seconds = int(getattr(cfg, "time_budget_seconds", 20) or 20)
        time_budget_seconds = max(1, int(time_budget_seconds))

        # 统一构造排序输入（用于 multi-start / 扰动）
        def _parse_date(value: Any) -> Optional[Any]:
            if value is None:
                return None
            if hasattr(value, "date"):
                try:
                    return value.date()
                except Exception:
                    pass
            s = str(value).strip().replace("/", "-")
            if not s:
                return None
            try:
                return datetime.strptime(s, "%Y-%m-%d").date()
            except Exception:
                return None

        batch_for_sort: List[BatchForSort] = []
        for b in batches.values():
            batch_for_sort.append(
                BatchForSort(
                    batch_id=str(getattr(b, "batch_id", "") or ""),
                    priority=str(getattr(b, "priority", "") or "normal"),
                    due_date=_parse_date(getattr(b, "due_date", None)),
                    ready_status=str(getattr(b, "ready_status", "") or "yes"),
                    ready_date=_parse_date(getattr(b, "ready_date", None)),
                    created_at=self._normalize_datetime(getattr(b, "created_at", None)),
                )
            )

        def _build_order(strategy_enum: SortStrategy, params: Dict[str, Any]) -> List[str]:
            sorter0 = StrategyFactory.create(strategy_enum, **(params or {}))
            return [x.batch_id for x in sorter0.sort(batch_for_sort)]

        # multi-start：策略集（先用当前策略，再补全其它策略）
        if algo_mode == "improve":
            keys = [cfg.sort_strategy] + [k for k in cfg_svc.VALID_STRATEGIES if k != cfg.sort_strategy]  # type: ignore[attr-defined]
        else:
            keys = [cfg.sort_strategy]

        best = None
        attempts: List[Dict[str, Any]] = []
        improvement_trace: List[Dict[str, Any]] = []

        t_begin = time.time()
        deadline = t_begin + (time_budget_seconds if algo_mode == "improve" else 10_000_000)

        # GreedyScheduler 需要 seed_results 为 ScheduleResult：这里转换一次
        seed_sr_list: List[ScheduleResult] = []
        if seed_results:
            for x in seed_results:
                try:
                    seed_sr_list.append(
                        ScheduleResult(
                            op_id=int(x.get("op_id") or 0),
                            op_code=str(x.get("op_code") or ""),
                            batch_id=str(x.get("batch_id") or ""),
                            seq=int(x.get("seq") or 0),
                            machine_id=(str(x.get("machine_id") or "") or None),
                            operator_id=(str(x.get("operator_id") or "") or None),
                            start_time=x.get("start_time"),
                            end_time=x.get("end_time"),
                            source=str(x.get("source") or "internal"),
                            op_type_name=(str(x.get("op_type_name") or "") or None),
                        )
                    )
                except Exception:
                    continue

        # improve：规则随机化（派工规则）+ 多起点
        dispatch_mode_cfg = (getattr(cfg, "dispatch_mode", None) or "batch_order").strip() or "batch_order"
        dispatch_rule_cfg = (getattr(cfg, "dispatch_rule", None) or "slack").strip() or "slack"
        if algo_mode == "improve" and dispatch_mode_cfg == "sgs":
            dispatch_rules = [dispatch_rule_cfg] + [x for x in cfg_svc.VALID_DISPATCH_RULES if x != dispatch_rule_cfg]  # type: ignore[attr-defined]
        else:
            dispatch_rules = [dispatch_rule_cfg]

        # 可选：OR-Tools 高质量起点（瓶颈子问题）
        if algo_mode == "improve" and getattr(cfg, "ortools_enabled", "no") == "yes":
            try:
                from core.algorithms.ortools_bottleneck import try_solve_bottleneck_batch_order

                remaining = float(deadline - time.time())
                tl_cfg = int(getattr(cfg, "ortools_time_limit_seconds", 5) or 5)
                tl = max(1, min(int(tl_cfg), int(remaining)))
                ort_order = try_solve_bottleneck_batch_order(
                    operations=algo_ops_to_schedule,
                    batches=batches,
                    start_dt=start_dt_norm,
                    time_limit_seconds=tl,
                    logger=self.logger,
                )
                if ort_order and time.time() <= deadline:
                    # 用当前策略（仅用于“补齐 order 未覆盖的批次”）
                    try:
                        ort_strat = SortStrategy(cfg.sort_strategy)
                    except Exception:
                        ort_strat = SortStrategy.PRIORITY_FIRST
                    ort_params: Dict[str, Any] = {}
                    if ort_strat == SortStrategy.WEIGHTED:
                        ort_params = {
                            "priority_weight": float(cfg.priority_weight),
                            "due_weight": float(cfg.due_weight),
                        }
                    res, summ, used_strat, used_params = scheduler.schedule(
                        operations=algo_ops_to_schedule,
                        batches=batches,
                        strategy=ort_strat,
                        strategy_params=ort_params,
                        start_dt=start_dt_norm,
                        end_date=end_date_norm,
                        machine_downtimes=downtime_map,
                        batch_order_override=list(ort_order),
                        seed_results=seed_sr_list,
                        dispatch_mode=dispatch_mode_cfg,
                        dispatch_rule=dispatch_rule_cfg,
                        resource_pool=resource_pool,
                    )
                    metrics = compute_metrics(res, batches)
                    score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)
                    attempts.append(
                        {
                            "tag": f"ortools:bottleneck|{dispatch_mode_cfg}:{dispatch_rule_cfg}",
                            "strategy": used_strat.value,
                            "dispatch_mode": dispatch_mode_cfg,
                            "dispatch_rule": dispatch_rule_cfg,
                            "score": list(score),
                            "failed_ops": int(summ.failed_ops),
                            "metrics": metrics.to_dict(),
                        }
                    )
                    cand = {
                        "results": res,
                        "summary": summ,
                        "strategy": used_strat,
                        "params": used_params,
                        "dispatch_mode": dispatch_mode_cfg,
                        "dispatch_rule": dispatch_rule_cfg,
                        "order": list(ort_order),
                        "metrics": metrics,
                        "score": score,
                    }
                    if best is None or score < best["score"]:
                        best = cand
                        if len(improvement_trace) < 200:
                            improvement_trace.append(
                                {
                                    "elapsed_ms": int((time.time() - t_begin) * 1000),
                                    "tag": f"ortools:bottleneck|{dispatch_mode_cfg}:{dispatch_rule_cfg}",
                                    "strategy": used_strat.value,
                                    "dispatch_mode": dispatch_mode_cfg,
                                    "dispatch_rule": dispatch_rule_cfg,
                                    "score": list(score),
                                    "metrics": metrics.to_dict(),
                                }
                            )
            except Exception as e:
                # 可选项失败不阻断主流程
                if self.logger:
                    try:
                        self.logger.warning(f"OR-Tools 高质量起点失败（已忽略）：{e}")
                    except Exception:
                        pass

        # 执行策略轮询（multi-start）
        for k in keys:
            if time.time() > deadline:
                break
            try:
                strat = SortStrategy(k)
            except Exception:
                continue
            params0: Dict[str, Any] = {}
            if strat == SortStrategy.WEIGHTED:
                params0 = {
                    "priority_weight": float(cfg.priority_weight),
                    "due_weight": float(cfg.due_weight),
                }

            for dr in dispatch_rules:
                if time.time() > deadline:
                    break
                order = _build_order(strat, params0)
                res, summ, used_strat, used_params = scheduler.schedule(
                    operations=algo_ops_to_schedule,
                    batches=batches,
                    strategy=strat,
                    strategy_params=params0,
                    start_dt=start_dt_norm,
                    end_date=end_date_norm,
                    machine_downtimes=downtime_map,
                    batch_order_override=order,
                    seed_results=seed_sr_list,
                    dispatch_mode=dispatch_mode_cfg,
                    dispatch_rule=dr,
                    resource_pool=resource_pool,
                )
                metrics = compute_metrics(res, batches)
                score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)
                attempts.append(
                    {
                        "tag": f"start:{k}|{dispatch_mode_cfg}:{dr}",
                        "strategy": used_strat.value,
                        "dispatch_mode": dispatch_mode_cfg,
                        "dispatch_rule": dr,
                        "score": list(score),
                        "failed_ops": int(summ.failed_ops),
                        "metrics": metrics.to_dict(),
                    }
                )
                cand = {
                    "results": res,
                    "summary": summ,
                    "strategy": used_strat,
                    "params": used_params,
                    "dispatch_mode": dispatch_mode_cfg,
                    "dispatch_rule": dr,
                    "order": order,
                    "metrics": metrics,
                    "score": score,
                }
                if best is None or score < best["score"]:
                    best = cand
                    if len(improvement_trace) < 200:
                        improvement_trace.append(
                            {
                                "elapsed_ms": int((time.time() - t_begin) * 1000),
                                "tag": f"start:{k}|{dispatch_mode_cfg}:{dr}",
                                "strategy": used_strat.value,
                                "dispatch_mode": dispatch_mode_cfg,
                                "dispatch_rule": dr,
                                "score": list(score),
                                "metrics": metrics.to_dict(),
                            }
                        )

        # 局部搜索（可选）：在 best batch_order 上做随机 swap/insert
        if algo_mode == "improve" and best is not None and len(best.get("order") or []) >= 2:
            rnd = random.Random(int(version))
            cur_order = list(best["order"])
            cur_strat = best["strategy"]
            cur_params = dict(best["params"] or {})
            cur_dispatch_mode = str(best.get("dispatch_mode") or dispatch_mode_cfg)
            cur_dispatch_rule = str(best.get("dispatch_rule") or dispatch_rule_cfg)
            it = 0
            it_limit = max(200, min(5000, int(time_budget_seconds) * 20))
            no_improve = 0
            restart_after = max(50, min(800, int(it_limit / 8) if it_limit > 0 else 200))
            while time.time() <= deadline and it < it_limit:
                it += 1
                cand_order = list(cur_order)
                n = len(cand_order)
                r0 = rnd.random()
                if r0 < 0.55:
                    move = "swap"
                elif r0 < 0.85:
                    move = "insert"
                else:
                    move = "block"
                if move == "swap":
                    i, j = rnd.sample(range(n), 2)
                    cand_order[i], cand_order[j] = cand_order[j], cand_order[i]
                elif move == "insert":
                    i = rnd.randrange(n)
                    j = rnd.randrange(n)
                    x = cand_order.pop(i)
                    cand_order.insert(j, x)
                else:
                    # block move：抽取一段连续区间移动到另一位置
                    if n >= 4:
                        i = rnd.randrange(n - 1)
                        max_len = min(6, n - i)
                        ln = rnd.randrange(2, max_len + 1)
                        block = cand_order[i : i + ln]
                        del cand_order[i : i + ln]
                        j = rnd.randrange(len(cand_order) + 1)
                        for t in reversed(block):
                            cand_order.insert(j, t)
                    else:
                        # n<4 时 block move 会退化为空操作；改用 swap，避免浪费一次迭代
                        i, j = rnd.sample(range(n), 2)
                        cand_order[i], cand_order[j] = cand_order[j], cand_order[i]
                        move = "swap_fallback"

                # 兜底：避免空迭代（例如 insert 选到 i==j，或 block 回插原位）
                if cand_order == cur_order and n >= 2:
                    i, j = rnd.sample(range(n), 2)
                    cand_order[i], cand_order[j] = cand_order[j], cand_order[i]
                    move = "swap_fallback"

                res, summ, used_strat, used_params = scheduler.schedule(
                    operations=algo_ops_to_schedule,
                    batches=batches,
                    strategy=cur_strat,
                    strategy_params=cur_params,
                    start_dt=start_dt_norm,
                    end_date=end_date_norm,
                    machine_downtimes=downtime_map,
                    batch_order_override=cand_order,
                    seed_results=seed_sr_list,
                    dispatch_mode=cur_dispatch_mode,
                    dispatch_rule=cur_dispatch_rule,
                    resource_pool=resource_pool,
                )
                metrics = compute_metrics(res, batches)
                score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)
                if score < best["score"]:
                    best = {
                        "results": res,
                        "summary": summ,
                        "strategy": used_strat,
                        "params": used_params,
                        "dispatch_mode": cur_dispatch_mode,
                        "dispatch_rule": cur_dispatch_rule,
                        "order": cand_order,
                        "metrics": metrics,
                        "score": score,
                    }
                    cur_order = list(cand_order)
                    no_improve = 0
                    if len(improvement_trace) < 200:
                        improvement_trace.append(
                            {
                                "elapsed_ms": int((time.time() - t_begin) * 1000),
                                "tag": f"local:{move}",
                                "strategy": used_strat.value,
                                "dispatch_mode": cur_dispatch_mode,
                                "dispatch_rule": cur_dispatch_rule,
                                "score": list(score),
                                "metrics": metrics.to_dict(),
                            }
                        )
                    # 记录少量轨迹，避免 result_summary 过大
                    if len(attempts) < 12:
                        attempts.append(
                            {
                                "tag": f"local:{move}",
                                "strategy": used_strat.value,
                                "dispatch_mode": cur_dispatch_mode,
                                "dispatch_rule": cur_dispatch_rule,
                                "score": list(score),
                                "failed_ops": int(summ.failed_ops),
                                "metrics": metrics.to_dict(),
                            }
                        )
                else:
                    no_improve += 1

                # 多次重启（轻量 ILS）：长时间无改进则从 best 出发做随机 shake
                if no_improve >= restart_after and best is not None:
                    no_improve = 0
                    cur_order = list(best.get("order") or cur_order)
                    # small shake：有限次 swap/insert
                    shake = rnd.randint(3, 8)
                    for _ in range(shake):
                        if len(cur_order) < 2:
                            break
                        if rnd.random() < 0.6:
                            i, j = rnd.sample(range(len(cur_order)), 2)
                            cur_order[i], cur_order[j] = cur_order[j], cur_order[i]
                        else:
                            i = rnd.randrange(len(cur_order))
                            j = rnd.randrange(len(cur_order))
                            x = cur_order.pop(i)
                            cur_order.insert(j, x)

        if best is None:
            # 理论上不会发生；兜底为原始单次
            results, summary, used_strategy, used_params = scheduler.schedule(
                operations=algo_ops_to_schedule,
                batches=batches,
                strategy=strategy_enum,
                strategy_params=strategy_params,
                start_dt=start_dt_norm,
                end_date=end_date_norm,
                machine_downtimes=downtime_map,
                seed_results=seed_sr_list,
                resource_pool=resource_pool,
            )
            best_metrics = compute_metrics(results, batches)
            best_score = (float(summary.failed_ops),) + objective_score(objective_name, best_metrics)
            best_order = _build_order(strategy_enum or SortStrategy.PRIORITY_FIRST, used_params or {})
        else:
            results = best["results"]
            summary = best["summary"]
            used_strategy = best["strategy"]
            used_params = best["params"]
            best_metrics = best["metrics"]
            best_score = best["score"]
            best_order = best["order"]

        # 把“冻结窗口相关 warning”合并到算法 warning 中
        if algo_warnings:
            try:
                summary.warnings.extend(algo_warnings)  # type: ignore[attr-defined]
            except Exception:
                pass

        # 超期预警：批次预计完工时间 vs due_date
        overdue_items: List[Dict[str, Any]] = []
        finish_by_batch: Dict[str, datetime] = {}
        for r in results:
            if not r.end_time:
                continue
            cur = finish_by_batch.get(r.batch_id)
            if (cur is None) or (r.end_time > cur):
                finish_by_batch[r.batch_id] = r.end_time

        invalid_due_count = 0
        invalid_due_ids_sample: List[str] = []
        invalid_due_raw_sample: List[str] = []
        for bid, b in batches.items():
            due = self._normalize_text(b.due_date)
            if not due:
                continue
            try:
                due_date = datetime.strptime(due.replace("/", "-"), "%Y-%m-%d").date()
            except Exception:
                invalid_due_count += 1
                if len(invalid_due_ids_sample) < 10:
                    invalid_due_ids_sample.append(str(bid))
                if len(invalid_due_raw_sample) < 5:
                    invalid_due_raw_sample.append(f"{bid}={due!r}")
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

        if invalid_due_count > 0:
            sample_ids = "，".join(invalid_due_ids_sample[:10])
            msg = f"存在 {invalid_due_count} 个批次 due_date 格式不合法，已忽略超期判断（示例批次：{sample_ids}）"
            try:
                summary.warnings.append(msg)
            except Exception:
                pass
            if self.logger:
                try:
                    raw_sample = "；".join(invalid_due_raw_sample[:5])
                    self.logger.warning(f"{msg}；示例原始 due_date：{raw_sample}")
                except Exception:
                    pass

        # result_status：success/partial/failed
        if summary.success:
            result_status = "success"
        elif summary.scheduled_ops > 0:
            result_status = "partial"
        else:
            result_status = "failed"
        if simulate:
            result_status = "simulated"

        # result_summary（JSON）：按文档固定键名（至少包含 strategy_params / overdue_batches）
        time_cost_ms = int((time.time() - t0) * 1000)
        frozen_batch_ids = sorted(
            {
                str(op.batch_id or "")
                for op in operations
                if op and op.id and int(op.id) in frozen_op_ids and str(op.batch_id or "").strip()
            }
        )
        result_summary_obj: Dict[str, Any] = {
            "is_simulation": bool(simulate),
            "version": version,
            "strategy": used_strategy.value,
            "strategy_params": used_params or {},
            "algo": {
                "mode": algo_mode,
                "objective": objective_name,
                "time_budget_seconds": int(time_budget_seconds),
                "hard_constraints": [
                    "precedence",
                    "calendar",
                    "resource_machine_operator",
                    "downtime_avoid",
                ]
                + (["freeze_window"] if getattr(cfg, "freeze_window_enabled", "no") == "yes" else []),
                "soft_objectives": [objective_name],
                "best_score": list(best_score) if best_score is not None else None,
                "metrics": best_metrics.to_dict() if best_metrics is not None else None,
                "best_batch_order": list(best_order or []),
                "attempts": (attempts or [])[:12],
                "improvement_trace": (improvement_trace or [])[:200],
                "freeze_window": {
                    "enabled": getattr(cfg, "freeze_window_enabled", "no"),
                    "days": int(getattr(cfg, "freeze_window_days", 0) or 0),
                    "frozen_op_count": int(len(frozen_op_ids)),
                    "frozen_batch_count": int(len(frozen_batch_ids)),
                    "frozen_batch_ids_sample": frozen_batch_ids[:20],
                },
            },
            "selected_batch_ids": list(normalized),
            "start_time": self._format_dt(start_dt_norm),
            "end_date": end_date_norm.isoformat() if end_date_norm else None,
            "counts": {
                "batch_count": len(batches),
                # 与调度器 summary 同口径（包含 seed_results；并考虑 seed 与 operations 去重过滤）
                "op_count": int(summary.total_ops),
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
                    "lock_status": "locked" if int(r.op_id) in frozen_op_ids else "unlocked",
                    "version": int(version),
                }
            )

        # 原子落库：Schedule + 状态更新 + ScheduleHistory
        with self.tx_manager.transaction():
            if schedule_rows:
                self.schedule_repo.bulk_create(schedule_rows)

            if not simulate:
                # 批次工序：成功排到的置 scheduled；失败的保持原状态（便于继续补全）
                scheduled_op_ids = {int(r.op_id) for r in results if r and r.op_id}
                assigned_by_op_id: Dict[int, Dict[str, Any]] = {
                    int(r.op_id): {"machine_id": r.machine_id, "operator_id": r.operator_id}
                    for r in results
                    if r and int(getattr(r, "op_id", 0) or 0) > 0 and (r.source or "").strip() == SourceType.INTERNAL.value
                }
                for op in operations:
                    if not op.id:
                        continue
                    if int(op.id) in scheduled_op_ids:
                        self.op_repo.update(int(op.id), {"status": "scheduled"})
                        # 自动分配补全：仅在原本缺省资源时回写 machine/operator（避免覆盖人工已选）
                        if int(op.id) in missing_internal_resource_op_ids:
                            assign = assigned_by_op_id.get(int(op.id)) or {}
                            mc = (assign.get("machine_id") or "").strip()
                            oid = (assign.get("operator_id") or "").strip()
                            if mc and oid:
                                self.op_repo.update(int(op.id), {"machine_id": mc, "operator_id": oid})

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
                    "op_count": int(summary.total_ops),
                    "result_status": result_status,
                    "result_summary": result_summary_json,
                    "created_by": created_by_text,
                }
            )

        # 操作日志留痕（OperationLogs）：放到事务后（避免内部 commit 干扰原子性）
        if self.op_logger is not None:
            detail = {
                "is_simulation": bool(simulate),
                "version": int(version),
                "strategy": used_strategy.value,
                "strategy_params": used_params or {},
                "algo": result_summary_obj.get("algo"),
                "batch_ids": list(normalized),
                "batch_count": len(batches),
                "op_count": int(summary.total_ops),
                "scheduled_ops": summary.scheduled_ops,
                "failed_ops": summary.failed_ops,
                "result_status": result_status,
                "overdue_count": len(overdue_items),
                "overdue_batches_sample": overdue_items[:10],
                "time_cost_ms": time_cost_ms,
            }
            self.op_logger.info(
                module="scheduler",
                action="simulate" if simulate else "schedule",
                target_type="schedule",
                target_id=str(version),
                detail=detail,
            )

        return {
            "is_simulation": bool(simulate),
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

