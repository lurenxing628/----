from __future__ import annotations

"""
可选 OR-Tools “高质量起点”：

思路（务实的混合策略）：
- 不做全量 APS（MIP/CP 全建模在几千工序规模下容易爆炸）
- 只对“瓶颈工种(op_type_id)”做一个单机序列子问题的 CP-SAT 近似求解，得到 batch 顺序
- 然后把该 batch_order 作为启发式排产（Greedy/SGS）的一个 multi-start 起点

该模块是“可选依赖”：
- 若环境未安装 `ortools`，会直接返回 None，不影响主流程
"""

import math
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.priority_constants import priority_weight_scaled
from core.algorithms.value_domains import INTERNAL


def _parse_due_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value or "").strip().replace("/", "-")
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _due_exclusive(d: Optional[date]) -> datetime:
    if not d:
        return datetime.max
    return datetime(d.year, d.month, d.day) + timedelta(days=1)


def try_solve_bottleneck_batch_order(
    *,
    operations: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    time_limit_seconds: int = 5,
    max_jobs: int = 200,
    logger=None,
) -> Optional[List[str]]:
    """
    返回一个 batch_id 列表（优先顺序），可直接作为 `batch_order_override` 传入启发式排产。

    注意：
    - 这是“单机序列”近似：把同一批次在瓶颈工种上的加工总量聚合成一个 job
    - 目标：最小化“加权拖期”（priority 权重）作为启发式起点
    """
    try:
        from ortools.sat.python import cp_model  # type: ignore
    except Exception:
        return None

    # warm-start 必须“失败即降级”：任何异常都不应影响主流程
    try:
        # 1) 找瓶颈工种（按 internal 工序工时总和）
        load_by_type: Dict[str, float] = {}
        per_batch_type_load: Dict[Tuple[str, str], float] = {}

        for op in operations:
            if (getattr(op, "source", INTERNAL) or INTERNAL).strip().lower() != INTERNAL:
                continue
            bid = str(getattr(op, "batch_id", "") or "").strip()
            if not bid or bid not in batches:
                continue
            ot = str(getattr(op, "op_type_id", "") or "").strip()
            if not ot:
                continue
            b = batches.get(bid)
            qty = getattr(b, "quantity", 0) or 0
            setup_hours = getattr(op, "setup_hours", 0) or 0
            unit_hours = getattr(op, "unit_hours", 0) or 0
            try:
                h = float(setup_hours) + float(unit_hours) * float(qty)
            except Exception:
                h = 0.0
            # 防御：NaN/Inf 不应进入瓶颈识别（否则可能污染 max() 或导致 ceil 崩溃）
            if (not math.isfinite(float(h))) or h <= 0:
                continue
            load_by_type[ot] = load_by_type.get(ot, 0.0) + float(h)
            per_batch_type_load[(bid, ot)] = per_batch_type_load.get((bid, ot), 0.0) + float(h)

        if not load_by_type:
            return None

        bottleneck_ot = max(load_by_type.items(), key=lambda x: float(x[1] or 0.0))[0]

        # 2) 聚合成 job（按 batch）
        jobs: List[Tuple[str, int, int]] = []  # (batch_id, dur_min, weight)
        due_min_by_batch: Dict[str, int] = {}

        for bid, b in batches.items():
            h = float(per_batch_type_load.get((bid, bottleneck_ot), 0.0) or 0.0)
            if (not math.isfinite(float(h))) or h <= 0:
                continue
            dur_min = max(1, int(math.ceil(h * 60.0)))
            w = priority_weight_scaled(getattr(b, "priority", None))
            jobs.append((bid, dur_min, int(w)))

            due_d = _parse_due_date(getattr(b, "due_date", None))
            if due_d:
                due_exclusive = _due_exclusive(due_d)
                due_min = int((due_exclusive - start_dt).total_seconds() / 60.0)
                # 允许 due_min 为负：用于保留“已逾期批次”的相对紧迫度（排序/截断窗口）
                due_min_by_batch[bid] = int(due_min)
            else:
                due_min_by_batch[bid] = 10**9  # 无交期：放到最后

        if len(jobs) < 2:
            return None

        # 若规模过大：只对“更紧急”的一部分求解（滚动窗口/瓶颈子问题）
        if len(jobs) > int(max_jobs):
            jobs.sort(key=lambda x: (due_min_by_batch.get(x[0], 10**9), -x[2], x[0]))
            keep = jobs[: int(max_jobs)]
            keep_ids = {bid for bid, _, _ in keep}
            jobs = keep
        else:
            keep_ids = {bid for bid, _, _ in jobs}

        # 3) CP-SAT 单机序列：NoOverlap + 最小化加权拖期
        horizon = int(sum(d for _, d, _ in jobs) + 1)
        # due_min 允许为负时：tardy 可能大于 horizon*10，需要放大上界避免模型 infeasible
        tardy_ub = int(horizon * 10)
        try:
            min_due_min = min(int(due_min_by_batch.get(bid, 10**9)) for bid, _, _ in jobs)
        except Exception:
            min_due_min = 0
        if min_due_min < 0:
            try:
                tardy_ub = max(tardy_ub, int(horizon - min_due_min + 1))
            except Exception:
                tardy_ub = int(horizon * 10)

        model = cp_model.CpModel()
        starts: Dict[str, Any] = {}
        ends: Dict[str, Any] = {}
        intervals = []
        tardies = []
        weights = []

        for idx, (bid, dur, w) in enumerate(jobs):
            s = model.NewIntVar(0, horizon, f"s_{idx}")
            e = model.NewIntVar(0, horizon, f"e_{idx}")
            itv = model.NewIntervalVar(s, int(dur), e, f"itv_{idx}")
            starts[bid] = s
            ends[bid] = e
            intervals.append(itv)

            due_min = int(due_min_by_batch.get(bid, 10**9))
            # tardy >= end - due ; tardy >= 0
            t = model.NewIntVar(0, int(tardy_ub), f"tardy_{idx}")
            model.Add(t >= e - int(due_min))
            model.Add(t >= 0)
            tardies.append(t)
            weights.append(int(w))

        model.AddNoOverlap(intervals)
        model.Minimize(sum(tardies[i] * int(weights[i]) for i in range(len(tardies))))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(max(1, int(time_limit_seconds)))
        try:
            # 允许并行（若环境支持）
            solver.parameters.num_search_workers = 8
        except Exception:
            pass

        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None

        # 4) 读取顺序：按 start 升序
        ordered = sorted(list(starts.keys()), key=lambda bid: int(solver.Value(starts[bid])))

        # 将未参与求解的批次追加在后（保持稳定）
        rest = [bid for bid in batches.keys() if bid not in keep_ids]
        if rest:
            # 交期早/高优先级的优先（简单排序）
            rest.sort(
                key=lambda bid: (
                    due_min_by_batch.get(bid, 10**9),
                    -priority_weight_scaled(getattr(batches.get(bid), "priority", None)),
                    bid,
                )
            )

        if logger:
            try:
                logger.info(
                    f"OR-Tools bottleneck warm-start: op_type_id={bottleneck_ot} jobs={len(jobs)} total_batches={len(batches)} time_limit={time_limit_seconds}s"
                )
            except Exception:
                pass

        return list(ordered) + rest
    except Exception as e:
        if logger:
            try:
                logger.warning(f"OR-Tools bottleneck warm-start 异常（已降级为 None）：{e}")
            except Exception:
                pass
        return None

