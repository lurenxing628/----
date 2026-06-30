"""把标准 FJSP 实例(Brandimarte 等)结构降维映射进我们 APS 模型,
供 due_budget_experiment 复用其毛/净开关与逾期/拖期测量。

降维声明(如实):
- 我们模型一道工序只有单一 unit_hours,"选哪台机器"不改加工时长。
  FJSP 原始每台可选机器加工时间不同 -> 这里取该 op 在可选机器集合上的
  **代表加工时间**(默认 min,可切 mean),作为 unit_hours。这是已知的降维损失:
  丢掉了"机器选择影响工时"这一柔性维度,只保留"机器选择(占用争用)"维度。
- job -> 批次(quantity=1);op -> 工序(seq=10,20,...给前后置链);source=internal;setup_hours=0。
- 每个 op 的可选机器集合 -> 一个合成 op_type_id 的 machines_by_op_type;每台机器配 1 个操作员。
- 同一 (机器集合) 复用同一 op_type_id,使资源池规模可控且语义稳定。

时间单位:FJSP 加工时间是无量纲整数,这里直接当"小时"用(配 8h/天班次日历)。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

# 8h/天工作窗(与 due_budget_experiment 的 _EightHourCalendar 对齐)
_HOURS_PER_DAY = 8.0
_START = datetime(2026, 1, 1, 8, 0, 0)


def load_fjsp_json(path: str) -> Tuple[int, List[List[List[Tuple[int, float]]]]]:
    """读 SchedulingLab/fjsp-instances 的 json 格式。

    返回 (machine_count, jobs),其中 jobs[j][o] = [(machine_id, proc_time), ...]。
    """
    d = json.load(open(path))
    machines = int(d["machines"])
    jobs: List[List[List[Tuple[int, float]]]] = []
    for job in d["jobs"]:
        ops: List[List[Tuple[int, float]]] = []
        for op in job:
            alts = [(int(a["machine"]), float(a["processing"])) for a in op]
            ops.append(alts)
        jobs.append(ops)
    return machines, jobs


def build_fjsp_scenario(
    path: str,
    *,
    instance_name: str,
    proc_repr: str = "min",
    tightness: float = 1.0,
    block_fraction: float = 0.45,
    seed_fraction: float = 0.12,
    differential: bool = True,
) -> Dict[str, Any]:
    """把一个 FJSP 实例构造成 due_budget_experiment 期望的 scenario dict。

    争用注入:
    - 合成交期:每批 due = ceil(关键路径估计 * tightness) 个工作日后;tightness 越小越紧。
    - downtime:对每台机器,在其"被该实例用得最多的时间段"按 block_fraction 比例铺设停机,
      differential=True 时把停机集中压在"日历后段"(松交期批次会落到的区域),制造毛/净秩翻转;
      differential=False 时均匀铺开(对照)。
    - seed:在若干瓶颈机器上放已冻结片段(占交期窗口内),进一步压低净残余。

    返回 dict: operations / batches / downtime_map / seed_results / resource_pool / context / auto_assign
    """
    machines, jobs = load_fjsp_json(path)
    machine_ids = [f"M{m:02d}" for m in range(machines)]
    operator_ids = [f"OP-{m:02d}" for m in range(machines)]

    # 1) 工序 + 批次 + 前后置链 + op_type 合成(按机器集合去重)
    ops: List[Any] = []
    batches: Dict[str, Any] = {}
    pred: Dict[int, set] = {}
    succ: Dict[int, set] = {}
    op_type_by_machineset: Dict[Tuple[int, ...], str] = {}
    machines_by_op_type: Dict[str, List[str]] = {}

    op_id = 0
    cp_hours_by_batch: Dict[str, float] = {}  # 关键路径(=该 job 各 op 代表工时之和,串行链)
    for j, job in enumerate(jobs):
        bid = f"J{j:02d}"
        chain_ids: List[int] = []
        cp = 0.0
        for o, alts in enumerate(job):
            op_id += 1
            machineset = tuple(sorted({m for m, _t in alts}))
            if machineset not in op_type_by_machineset:
                otid = f"OT-{len(op_type_by_machineset):03d}"
                op_type_by_machineset[machineset] = otid
                machines_by_op_type[otid] = [machine_ids[m] for m in machineset]
            otid = op_type_by_machineset[machineset]
            # 代表加工时间
            times = [t for _m, t in alts]
            unit = min(times) if proc_repr == "min" else (sum(times) / len(times))
            unit = float(max(unit, 0.1))  # 防 0 工时
            cp += unit
            ops.append(
                SimpleNamespace(
                    id=int(op_id),
                    op_code=f"{bid}-{o}",
                    batch_id=bid,
                    seq=int((o + 1) * 10),
                    source="internal",
                    machine_id=None,        # 柔性:自动派工从 op_type 机器集合里选
                    operator_id=None,
                    setup_hours=0.0,
                    unit_hours=unit,
                    op_type_id=otid,
                    op_type_name=otid,
                )
            )
            chain_ids.append(op_id)
        # 前后置:链式 seq
        for k, oid in enumerate(chain_ids):
            pred[oid] = {chain_ids[k - 1]} if k > 0 else set()
            succ[oid] = {chain_ids[k + 1]} if k + 1 < len(chain_ids) else set()
        cp_hours_by_batch[bid] = cp

    # 2) 合成交期:关键路径工时换算成工作日 * tightness
    #    多档松紧:把批次按 index 轮流分配 tightness ∈ {tightness-0.2, tightness, tightness+0.2}
    import math
    tight_levels = [max(0.5, tightness - 0.2), tightness, tightness + 0.2]
    for idx, bid in enumerate(sorted(cp_hours_by_batch)):
        cp = cp_hours_by_batch[bid]
        tl = tight_levels[idx % len(tight_levels)]
        work_days = max(1, math.ceil((cp / _HOURS_PER_DAY) * tl))
        due_dt = _START + timedelta(days=work_days)
        due_date = due_dt.date().isoformat()
        prio = "high" if (idx % 5 == 0) else "normal"
        batches[bid] = SimpleNamespace(
            batch_id=bid,
            priority=prio,
            due_date=due_date,
            ready_status="yes",
            ready_date=None,
            quantity=1,
        )

    # 3) 估计排程跨度(用于铺 downtime 的时间范围):粗略 = 总工时 / 机器数 换算成天 + 余量
    total_hours = sum(cp_hours_by_batch.values())
    span_days = max(6, int(math.ceil((total_hours / max(1, machines)) / _HOURS_PER_DAY)) + 4)

    # 4) downtime:每台机器铺停机片段
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]] = {}
    for m, mid in enumerate(machine_ids):
        segments: List[Tuple[datetime, datetime]] = []
        if differential:
            # 集中在后段(松交期批次落点):后 60% 的天里,每天占 block_fraction*8h
            start_day = int(span_days * 0.4)
            day_range = range(start_day, span_days)
        else:
            day_range = range(0, span_days)
        # 机器间错相位,避免完全相同
        for d in day_range:
            if (d + m) % 2 == 0:  # 半数天停机,制造不均
                day0 = _START + timedelta(days=d)
                block_h = _HOURS_PER_DAY * block_fraction
                seg_start = datetime(day0.year, day0.month, day0.day, 8, 0)
                seg_end = seg_start + timedelta(hours=block_h)
                segments.append((seg_start, seg_end))
        if segments:
            downtime_map[mid] = segments

    # 5) seed:在前 1/3 机器上放已冻结片段,落在交期窗口内、净进一步坍缩
    seed_results: List[Any] = []
    sid = 900
    n_seed_machines = max(1, machines // 3)
    for m in range(n_seed_machines):
        mid = machine_ids[m]
        # 放在前段某天(贴近紧交期),占一段
        day0 = _START + timedelta(days=1 + m)
        s = datetime(day0.year, day0.month, day0.day, 8, 0)
        e = s + timedelta(hours=_HOURS_PER_DAY * seed_fraction * 8)  # 占 ~seed_fraction*8 比例的窗
        e = min(e, datetime(day0.year, day0.month, day0.day, 16, 0))
        if e <= s:
            e = s + timedelta(hours=1)
        sid += 1
        seed_results.append(
            SimpleNamespace(
                op_id=int(sid), op_code=f"SEED{sid}", batch_id="B_SEED", seq=10,
                machine_id=mid, operator_id=operator_ids[m], source="internal",
                start_time=s, end_time=e, op_type_name="OT-SEED",
            )
        )

    resource_pool = {
        "machines_by_op_type": machines_by_op_type,
        "operators_by_machine": {mid: [operator_ids[m]] for m, mid in enumerate(machine_ids)},
        "machines_by_operator": {operator_ids[m]: [mid] for m, mid in enumerate(machine_ids)},
    }

    context = _build_fjsp_context(ops, seed_results=seed_results, pred=pred, succ=succ)
    return {
        "name": instance_name,
        "operations": ops,
        "batches": batches,
        "downtime_map": downtime_map,
        "seed_results": seed_results,
        "resource_pool": resource_pool,
        "context": context,
        "auto_assign": True,
        "_meta": {
            "machines": machines,
            "n_batches": len(batches),
            "n_ops": len(ops),
            "n_op_types": len(machines_by_op_type),
            "span_days": span_days,
            "proc_repr": proc_repr,
            "tightness": tightness,
            "differential": differential,
        },
    }


def _build_fjsp_context(ops, *, seed_results, pred, succ) -> Dict[str, Any]:
    op_ids = [int(o.id) for o in ops]
    seed_ids = sorted({int(s.op_id) for s in list(seed_results or [])})
    pred = {int(k): set(int(x) for x in v) for k, v in (pred or {}).items()}
    succ = {int(k): set(int(x) for x in v) for k, v in (succ or {}).items()}
    metrics = {}
    for oid in sorted(op_ids):
        metrics[oid] = {
            "is_on_critical_path": False,
            "critical_path_rank": None,
            "impact_count": len(succ.get(oid, set())),
            "generation_index": 0,
            "downstream_critical_minutes": 0,
            "bottleneck_machine_score": 1.0,
        }
    return {
        "enabled": True,
        "schedulable_op_ids": set(op_ids),
        "fixed_op_ids": set(seed_ids),
        "fixed_op_sources_by_op_id": {oid: "seed" for oid in seed_ids},
        "predecessor_op_ids_by_op_id": {oid: set(pred.get(oid, set())) for oid in op_ids},
        "successor_op_ids_by_op_id": {oid: set(succ.get(oid, set())) for oid in op_ids},
        "sort_key_by_op_id": {oid: (0, i, oid) for i, oid in enumerate(sorted(op_ids), start=1)},
        "graph_priority_key_by_op_id": {oid: (0.0,) for oid in op_ids},
        "node_metrics_by_op_id": metrics,
    }
