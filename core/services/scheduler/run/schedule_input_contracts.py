from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from core.algorithm_contracts.operation_effort import OperationEffort
from core.models import Batch, BatchOperation
from core.services.common.build_outcome import BuildOutcome
from core.services.scheduler.execution.execution_fact_provider import ExecutionFact


@dataclass
class ScheduleRunInput:
    normalized_batch_ids: List[str]
    start_dt_norm: datetime
    end_date_norm: Optional[date]
    created_by_text: str
    run_label: str
    t0: float
    cal_svc: Any
    cfg_svc: Any
    cfg: Any
    readiness_gate_enabled: bool
    batches: Dict[str, Batch]
    operations: List[BatchOperation]
    reschedulable_operations: List[BatchOperation]
    reschedulable_op_ids: Set[int]
    missing_internal_resource_op_ids: Set[int]
    algo_input_outcome: BuildOutcome[List[Any]]
    algo_ops: List[Any]
    prev_version: int
    frozen_op_ids: Set[int]
    seed_results: List[Dict[str, Any]]
    execution_facts: Dict[int, ExecutionFact]
    execution_fixed_op_ids: Set[int]
    execution_completed_op_ids: Set[int]
    execution_seed_results: List[Dict[str, Any]]
    execution_guard_state_revisions: Dict[int, str]
    execution_snapshot_revision: str
    execution_snapshot_op_ids: List[int]
    execution_snapshot_op_count: int
    execution_has_guarded_facts: bool
    schedule_output_allowed_op_ids: Set[int]
    payload_validation_operations: List[BatchOperation]
    algo_warnings: List[str]
    freeze_meta: Dict[str, Any]
    algo_ops_to_schedule: List[Any]
    downtime_meta: Dict[str, Any]
    resource_pool_meta: Dict[str, Any]
    downtime_map: Dict[str, Any]
    resource_pool: Any
    optimizer_seed_version: int
    run_time_budget_seconds: Optional[float] = None
    operation_efforts: List[OperationEffort] = field(default_factory=list)


def _op_seq(op: Any) -> int:
    # R69/O24 收口：persistence_guard 与 runtime_support 两份逐字节相同的副本合一到本契约文件。
    # `or 0` 兜的是 None/0/空串等「无 seq」合法形态（下游靠 completed_seq<=0 短路过滤），绝不卷入报错；
    # 只有坏类型（如 seq="abc"）才 loud raise——护栏链路里坏 seq 必须暴露，禁改回 except 静默归 0
    # （静默归 0 会让 completed_seq<=0 短路放空过滤、漏判后继工序需重算，算法侧静默漏排）。
    try:
        return int(getattr(op, "seq", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"工序 seq 值无效（无法转为整数）：{getattr(op, 'seq', None)!r}") from exc


def _build_freeze_window_seed_with_meta(
    build_freeze_window_seed_fn: Any,
    svc: Any,
    *,
    cfg: Any,
    prev_version: int,
    start_dt: datetime,
    operations: List[Any],
    reschedulable_operations: Optional[List[Any]],
    strict_mode: bool,
) -> Tuple[Set[int], List[Dict[str, Any]], List[str], Dict[str, Any]]:
    freeze_meta: Dict[str, Any] = {}
    result = build_freeze_window_seed_fn(
        svc,
        cfg=cfg,
        prev_version=prev_version,
        start_dt=start_dt,
        operations=operations,
        reschedulable_operations=reschedulable_operations,
        strict_mode=bool(strict_mode),
        meta=freeze_meta,
    )
    frozen_op_ids, seed_results, algo_warnings = result
    return set(frozen_op_ids or set()), list(seed_results or []), list(algo_warnings or []), freeze_meta
