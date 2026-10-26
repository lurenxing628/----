from __future__ import annotations

"""
可选 OR-Tools “高质量起点”：

思路（务实的混合策略）：
- 不做全量 APS（MIP/CP 全建模在几千工序规模下容易爆炸）
- 只对“瓶颈工种(op_type_id)”做一个单机序列子问题的 CP-SAT 近似求解，得到 batch 顺序
- 然后把该 batch_order 作为启发式排产（Greedy/SGS）的一个 multi-start 起点

该模块是“可选依赖”：
- 若环境未安装 `ortools`，会抛出 `OrtoolsWarmstartError`，由上层记录为可见降级后继续主流程
"""

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast

from core.algorithm_contracts.date_parsers import due_exclusive, parse_date
from core.algorithm_contracts.priority_constants import priority_weight_scaled
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.algorithm_contracts.value_domains import INTERNAL
from core.algorithm_runtime.operation_effort import internal_operation_effort
from core.errors import ValidationError
from core.models.batch import Batch

_LOGGER = logging.getLogger(__name__)
# 规模过大时只对更紧急的这么多个批次求解瓶颈子问题。
_MAX_BOTTLENECK_JOBS = 200


class OrtoolsWarmstartError(RuntimeError):
    """OR-Tools warm-start 真失败：交给上层现有降级链路展示。"""


def _status_value(cp_model: Any, name: str) -> Optional[int]:
    value = getattr(cp_model, name, None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise OrtoolsWarmstartError(f"OR-Tools 状态码不可读取：{name}") from exc


def _status_name(cp_model: Any, status: int) -> str:
    for name in ("OPTIMAL", "FEASIBLE", "INFEASIBLE", "MODEL_INVALID", "UNKNOWN"):
        if _status_value(cp_model, name) == int(status):
            return name
    return str(status)


def try_solve_bottleneck_batch_order(
    *,
    operations: List[OpForScheduleAlgo],
    batches: Dict[str, Batch],
    start_dt: datetime,
    time_limit_seconds: int = 5,
) -> Optional[List[str]]:
    """
    返回一个 batch_id 列表（优先顺序），可直接作为 `batch_order_override` 传入启发式排产。

    注意：
    - 这是“单机序列”近似：把同一批次在瓶颈工种上的加工总量聚合成一个 job
    - 目标：最小化“加权拖期”（priority 权重）作为启发式起点
    """
    try:
        from ortools.sat.python import cp_model  # type: ignore
    except Exception as exc:
        raise OrtoolsWarmstartError("OR-Tools 预热依赖加载失败") from exc

    # warm-start 必须“失败即降级”：真失败抛给上层现有降级链路，只有无候选/超时无解返回 None。
    # 1) 找瓶颈工种（按 internal 工序工时总和）
    load_by_type: Dict[str, float] = {}
    per_batch_type_load: Dict[Tuple[str, str], float] = {}

    for op in operations:
        if op.source != INTERNAL:
            continue
        bid, ot = op.batch_id, op.op_type_id
        if bid not in batches:
            continue
        try:
            effort = internal_operation_effort(op, batches[bid])
        except (ValueError, ValidationError) as exc:
            raise OrtoolsWarmstartError(f"OR-Tools 预热无法读取工序工时：{exc}") from exc
        h = cast(float, effort.required_standard_hours)
        if h <= 0:
            continue
        load_by_type[ot] = load_by_type.get(ot, 0.0) + float(h)
        per_batch_type_load[(bid, ot)] = per_batch_type_load.get((bid, ot), 0.0) + float(h)

    if not load_by_type:
        return None

    bottleneck_ot = max(load_by_type.items(), key=lambda x: x[1])[0]

    # 2) 聚合成 job（按 batch）
    jobs: List[Tuple[str, int, int]] = []  # (batch_id, dur_min, weight)
    due_min_by_batch: Dict[str, int] = {}

    for bid, b in batches.items():
        due_d = parse_date(b.due_date)
        if due_d:
            due_dt_exclusive = due_exclusive(due_d)
            due_min = int((due_dt_exclusive - start_dt).total_seconds() / 60.0)
            # 允许 due_min 为负：用于保留“已逾期批次”的相对紧迫度（排序/截断窗口）
            due_min_by_batch[bid] = int(due_min)
        else:
            due_min_by_batch[bid] = 10**9  # 无交期：放到最后

        h = per_batch_type_load.get((bid, bottleneck_ot), 0.0)
        if (not math.isfinite(float(h))) or h <= 0:
            continue
        dur_min = max(1, int(math.ceil(h * 60.0)))
        w = priority_weight_scaled(b.priority)
        jobs.append((bid, dur_min, int(w)))

    if len(jobs) < 2:
        return None

    # 若规模过大：只对“更紧急”的一部分求解（滚动窗口/瓶颈子问题）
    if len(jobs) > _MAX_BOTTLENECK_JOBS:
        jobs.sort(key=lambda x: (due_min_by_batch.get(x[0], 10**9), -x[2], x[0]))
        keep = jobs[:_MAX_BOTTLENECK_JOBS]
        keep_ids = {bid for bid, _, _ in keep}
        jobs = keep
    else:
        keep_ids = {bid for bid, _, _ in jobs}

    # 3) CP-SAT 单机序列：NoOverlap + 最小化加权拖期
    horizon = int(sum(d for _, d, _ in jobs) + 1)
    # due_min 允许为负时：tardy 可能大于 horizon*10，需要放大上界避免模型 infeasible
    tardy_ub = int(horizon * 10)
    min_due_min = min(int(due_min_by_batch.get(bid, 10**9)) for bid, _, _ in jobs)
    if min_due_min < 0:
        tardy_ub = max(tardy_ub, int(horizon - min_due_min + 1))

    model = cp_model.CpModel()
    starts: Dict[str, Any] = {}
    intervals = []
    tardies = []
    weights = []

    for idx, (bid, dur, w) in enumerate(jobs):
        s = model.NewIntVar(0, horizon, f"s_{idx}")
        e = model.NewIntVar(0, horizon, f"e_{idx}")
        itv = model.NewIntervalVar(s, int(dur), e, f"itv_{idx}")
        starts[bid] = s
        intervals.append(itv)

        due_min = int(due_min_by_batch.get(bid, 10**9))
        # tardy >= end - due ; tardy >= 0
        t = model.NewIntVar(0, int(tardy_ub), f"tardy_{idx}")
        model.Add(t >= e - int(due_min))
        tardies.append(t)
        weights.append(int(w))

    model.AddNoOverlap(intervals)
    model.Minimize(sum(tardies[i] * int(weights[i]) for i in range(len(tardies))))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(max(1, int(time_limit_seconds)))
    try:
        # 允许并行（若环境支持）
        solver.parameters.num_search_workers = 8
    except Exception as exc:
        _LOGGER.warning(f"OR-Tools 预热并行参数设置失败，继续单线程求解：{exc}")

    status = solver.Solve(model)
    success_statuses = {_status_value(cp_model, "OPTIMAL"), _status_value(cp_model, "FEASIBLE")}
    invalid_statuses = {_status_value(cp_model, "MODEL_INVALID"), _status_value(cp_model, "INFEASIBLE")}
    if int(status) not in {int(item) for item in success_statuses if item is not None}:
        if int(status) in {int(item) for item in invalid_statuses if item is not None}:
            status_name = _status_name(cp_model, int(status))
            raise OrtoolsWarmstartError(f"OR-Tools 预热模型不可用：status={status_name}")
        return None

    # 4) 读取顺序：按 start 升序
    ordered = sorted(starts, key=lambda bid: int(solver.Value(starts[bid])))

    # 将未参与求解的批次追加在后（保持稳定）
    rest = [bid for bid in batches.keys() if bid not in keep_ids]
    if rest:
        # 交期早/高优先级的优先（简单排序）
        rest.sort(
            key=lambda bid: (
                due_min_by_batch.get(bid, 10**9),
                -priority_weight_scaled(batches[bid].priority),
                bid,
            )
        )

    _LOGGER.info(
        f"OR-Tools bottleneck warm-start: op_type_id={bottleneck_ot} jobs={len(jobs)} total_batches={len(batches)} time_limit={time_limit_seconds}s",
    )

    return ordered + rest
