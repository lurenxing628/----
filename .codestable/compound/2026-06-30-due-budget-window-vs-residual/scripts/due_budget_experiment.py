"""方向性对比实验:GraphReady v2「追交预算」毛窗口产能 vs 净残余产能。

只在真实排产代码路径上跑(run_graph_ready_candidates + 真实 GreedyScheduler SGS),
用 monkeypatch 切换 _deadline_budget_hours 的口径,跑完务必还原。

口径:
  毛(现状) = capacity["residual_capacity_window_hours"]  (窗口总工时,未扣占用)
  净        = capacity["residual_capacity_hours"]         (= 窗口 - downtime/seed 占用)

不写 core。脚本独立运行。
"""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
ARTIFACT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SCRIPT_DIR.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.algorithms import GreedyScheduler, SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.algo_stats import snapshot_algo_stats
from core.models.schedule_config_runtime import default_snapshot_values
from core.services.scheduler.run import optimizer_graph_ready_v2_features as v2feat
from core.services.scheduler.run.optimizer_candidate_profile import build_candidate_profile
from core.services.scheduler.run.optimizer_graph_ready import run_graph_ready_candidates
from core.services.scheduler.run.optimizer_graph_ready_v2_features import enrich_graph_ready_v2_metrics
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState

_START = datetime(2026, 1, 1, 8, 0, 0)
_OBJECTIVE = "min_overdue"  # 由 --objective 覆盖


# ---------------------------------------------------------------------------
# 有班次的日历(8h/天,08:00-16:00),抄自合同测试 _EightHourCalendar / _EightHourPolicy
# ---------------------------------------------------------------------------
class _ContinuousCalendar:
    """SGS 真实排产需要的日历接口最小实现(连续推进版,policy 单独覆盖)。"""

    def adjust_to_working_time(self, dt, priority=None, machine_id=None, operator_id=None):
        # 推到下一个 08:00-16:00 窗口内
        cur = dt
        for _ in range(400):
            day_start = datetime.combine(cur.date(), time(8, 0, 0))
            day_end = datetime.combine(cur.date(), time(16, 0, 0))
            if cur < day_start:
                return day_start
            if cur < day_end:
                return cur
            cur = datetime.combine(cur.date() + timedelta(days=1), time(8, 0, 0))
        return cur

    def add_working_hours(self, dt, hours, priority=None, machine_id=None, operator_id=None):
        remaining = float(hours or 0.0)
        cur = self.adjust_to_working_time(dt)
        for _ in range(2000):
            if remaining <= 1e-9:
                return cur
            day_end = datetime.combine(cur.date(), time(16, 0, 0))
            avail = (day_end - cur).total_seconds() / 3600.0
            if avail <= 0:
                cur = self.adjust_to_working_time(datetime.combine(cur.date() + timedelta(days=1), time(8, 0, 0)))
                continue
            if remaining <= avail:
                return cur + timedelta(hours=remaining)
            remaining -= avail
            cur = self.adjust_to_working_time(datetime.combine(cur.date() + timedelta(days=1), time(8, 0, 0)))
        return cur

    def get_efficiency(self, dt, machine_id=None, operator_id=None):
        return 1.0

    def add_calendar_days(self, dt, days, machine_id=None, operator_id=None):
        return dt + timedelta(days=float(days or 0.0))


class _EightHourPolicy:
    efficiency = 1.0

    def __init__(self, dt: datetime) -> None:
        self._dt = dt

    def is_priority_allowed(self, _priority: Any) -> bool:
        return True

    def work_window(self):
        start = datetime.combine(self._dt.date(), time(8, 0, 0))
        return start, start + timedelta(hours=8)


class _EightHourCalendar(_ContinuousCalendar):
    def policy_for_datetime(self, dt: datetime, operator_id: Any = None):
        return _EightHourPolicy(dt)


# ---------------------------------------------------------------------------
# 毛/净 口径切换(monkeypatch _deadline_budget_hours),finally 还原
# ---------------------------------------------------------------------------
_ORIG_DEADLINE_BUDGET = v2feat._deadline_budget_hours
_EXTERNAL = None  # 懒加载


def _gross_budget(op, *, calendar_service, due_wall_hours, capacity):
    """毛口径 = 现状实现(window_hours)。直接复用原函数。"""
    return _ORIG_DEADLINE_BUDGET(op, calendar_service=calendar_service, due_wall_hours=due_wall_hours, capacity=capacity)


def _net_budget(op, *, calendar_service, due_wall_hours, capacity):
    """净口径 = 同样的分支判定,但内制+有日历时返回 residual_capacity_hours(扣占用)。"""
    from core.algorithms.value_domains import EXTERNAL

    if due_wall_hours <= 0.0:
        return float(due_wall_hours)
    if str(getattr(op, "source", "internal") or "internal").strip().lower() == EXTERNAL:
        return float(due_wall_hours)
    policy_for_datetime = getattr(calendar_service, "policy_for_datetime", None)
    uses_cal = callable(policy_for_datetime) and int(capacity.get("candidate_machine_count") or 0) > 0
    if uses_cal:
        return float(capacity["residual_capacity_hours"])  # 净:扣掉 downtime/seed 占用
    return float(due_wall_hours)


@contextmanager
def budget_basis(basis: str):
    """basis in {'gross','net'}。退出时还原全局模块属性,避免污染。"""
    assert basis in ("gross", "net")
    saved = v2feat._deadline_budget_hours
    try:
        v2feat._deadline_budget_hours = _gross_budget if basis == "gross" else _net_budget
        yield
    finally:
        v2feat._deadline_budget_hours = saved


# ---------------------------------------------------------------------------
# 争用场景构造
# ---------------------------------------------------------------------------
def _op(op_id, batch_id, *, seq, machine_id, op_type_id, setup_hours, operator_id="OP-1"):
    return SimpleNamespace(
        id=int(op_id),
        op_code=f"OP-{op_id}",
        batch_id=str(batch_id),
        seq=int(seq),
        source="internal",
        machine_id=machine_id,
        operator_id=operator_id,
        setup_hours=float(setup_hours),
        unit_hours=0.0,
        op_type_id=op_type_id,
        op_type_name=op_type_id,
    )


def _batch(batch_id, *, due_date, priority="normal", quantity=1):
    return SimpleNamespace(
        batch_id=str(batch_id),
        priority=priority,
        due_date=due_date,
        ready_status="yes",
        ready_date=None,
        quantity=int(quantity),
    )


_FJSP_DIR = ARTIFACT_ROOT / "baselines" / "fjsp"
# 真实 FJSP 实例(Brandimarte)+ 各档松紧。名字形如 fjsp:mk06:t1.0
_FJSP_SPECS = {
    "mk01": {"path": str(_FJSP_DIR / "mk01.json")},
    "mk06": {"path": str(_FJSP_DIR / "mk06.json")},
    "mk10": {"path": str(_FJSP_DIR / "mk10.json")},
}


def _build_fjsp_named(name: str) -> Dict[str, Any]:
    """name 形如 'fjsp:mk06' 或 'fjsp:mk06:t0.8' 或 'fjsp:mk06:t1.0:uniform'。"""
    from fjsp_loader import build_fjsp_scenario

    parts = name.split(":")
    inst = parts[1]
    if inst not in _FJSP_SPECS:
        raise ValueError(f"unknown fjsp instance {inst}")
    tightness = 1.0
    differential = True
    for tok in parts[2:]:
        if tok.startswith("t"):
            tightness = float(tok[1:])
        elif tok == "uniform":
            differential = False
        elif tok == "diff":
            differential = True
    return build_fjsp_scenario(
        _FJSP_SPECS[inst]["path"],
        instance_name=name,
        tightness=tightness,
        differential=differential,
    )


def build_scenario(name: str) -> Dict[str, Any]:
    if name.startswith("fjsp:"):
        return _build_fjsp_named(name)
    """造多个内制批次,工序落在同一组瓶颈机器上抢资源,交期松紧不一;
    瓶颈机器注入 downtime + seed,落在交期窗口内 -> 净 < 毛。

    返回 dict: operations / batches / downtime_map / seed_results / resource_pool / context
    """
    if name == "tight_bottleneck":
        # 单瓶颈机器 MC-BN,4 个内制批次都排它;交期紧
        machine = "MC-BN"
        ops = [
            _op(1, "B_HOT", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=6.0),    # 紧
            _op(2, "B_WARM", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=5.0),   # 中
            _op(3, "B_COOL", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=4.0),   # 宽
            _op(4, "B_COLD", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=3.0),   # 很宽
        ]
        batches = {
            "B_HOT": _batch("B_HOT", due_date="2026-01-02"),    # 窗口很短(~2 工作日内)
            "B_WARM": _batch("B_WARM", due_date="2026-01-03"),
            "B_COOL": _batch("B_COOL", due_date="2026-01-06"),
            "B_COLD": _batch("B_COLD", due_date="2026-01-08"),
        }
        # downtime 落在前几天瓶颈机器窗口内
        downtime_map = {
            machine: [
                (datetime(2026, 1, 1, 8, 0), datetime(2026, 1, 1, 12, 0)),   # 第1天上午占4h
                (datetime(2026, 1, 2, 8, 0), datetime(2026, 1, 2, 11, 0)),   # 第2天上午占3h
            ]
        }
        # seed:已冻结片段,落在瓶颈机器交期窗口内
        seed_results = [
            SimpleNamespace(
                op_id=99, op_code="SEED1", batch_id="B_SEED", seq=10,
                machine_id=machine, operator_id="OP-1", source="internal",
                start_time=datetime(2026, 1, 1, 13, 0), end_time=datetime(2026, 1, 1, 16, 0),  # 第1天下午占3h
                op_type_name="OT-BN",
            ),
            SimpleNamespace(
                op_id=98, op_code="SEED2", batch_id="B_SEED", seq=10,
                machine_id=machine, operator_id="OP-1", source="internal",
                start_time=datetime(2026, 1, 3, 8, 0), end_time=datetime(2026, 1, 3, 12, 0),    # 第3天上午占4h
                op_type_name="OT-BN",
            ),
        ]
        resource_pool = None
    elif name == "two_machine_pool":
        # 两台同型号瓶颈机器(自动派工),其中一台被占满,逼净显著下降
        ops = [
            _op(1, "B_HOT", seq=10, machine_id=None, operator_id=None, op_type_id="OT-BN", setup_hours=7.0),
            _op(2, "B_WARM", seq=10, machine_id=None, operator_id=None, op_type_id="OT-BN", setup_hours=6.0),
            _op(3, "B_COOL", seq=10, machine_id=None, operator_id=None, op_type_id="OT-BN", setup_hours=4.0),
            _op(4, "B_COLD", seq=10, machine_id=None, operator_id=None, op_type_id="OT-BN", setup_hours=3.0),
            _op(5, "B_MILD", seq=10, machine_id=None, operator_id=None, op_type_id="OT-BN", setup_hours=5.0),
        ]
        batches = {
            "B_HOT": _batch("B_HOT", due_date="2026-01-02", priority="high"),
            "B_WARM": _batch("B_WARM", due_date="2026-01-03"),
            "B_COOL": _batch("B_COOL", due_date="2026-01-05"),
            "B_COLD": _batch("B_COLD", due_date="2026-01-09"),
            "B_MILD": _batch("B_MILD", due_date="2026-01-04"),
        }
        machines = ["MC-BN-1", "MC-BN-2"]
        # 两台都注 downtime(强度不同),seed 压在 MC-BN-1
        downtime_map = {
            "MC-BN-1": [
                (datetime(2026, 1, 1, 8, 0), datetime(2026, 1, 1, 14, 0)),   # 占6h
                (datetime(2026, 1, 2, 8, 0), datetime(2026, 1, 2, 13, 0)),   # 占5h
            ],
            "MC-BN-2": [
                (datetime(2026, 1, 1, 8, 0), datetime(2026, 1, 1, 11, 0)),   # 占3h
            ],
        }
        seed_results = [
            SimpleNamespace(
                op_id=99, op_code="SEED1", batch_id="B_SEED", seq=10,
                machine_id="MC-BN-1", operator_id="OP-A", source="internal",
                start_time=datetime(2026, 1, 2, 13, 0), end_time=datetime(2026, 1, 2, 16, 0),
                op_type_name="OT-BN",
            ),
            SimpleNamespace(
                op_id=98, op_code="SEED2", batch_id="B_SEED", seq=10,
                machine_id="MC-BN-2", operator_id="OP-B", source="internal",
                start_time=datetime(2026, 1, 1, 13, 0), end_time=datetime(2026, 1, 1, 16, 0),
                op_type_name="OT-BN",
            ),
        ]
        resource_pool = {
            "machines_by_op_type": {"OT-BN": machines},
            "operators_by_machine": {"MC-BN-1": ["OP-A"], "MC-BN-2": ["OP-B"]},
            "machines_by_operator": {"OP-A": ["MC-BN-1"], "OP-B": ["MC-BN-2"]},
        }
    elif name == "heavy_seed_choke":
        # 单瓶颈,seed/downtime 极重,几乎吃光交期窗口 -> 净远小于毛,且制造逾期
        machine = "MC-BN"
        ops = [
            _op(1, "B_HOT", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=6.0),
            _op(2, "B_WARM", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=6.0),
            _op(3, "B_COOL", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=5.0),
            _op(4, "B_COLD", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=4.0),
        ]
        batches = {
            "B_HOT": _batch("B_HOT", due_date="2026-01-02"),
            "B_WARM": _batch("B_WARM", due_date="2026-01-03"),
            "B_COOL": _batch("B_COOL", due_date="2026-01-04"),
            "B_COLD": _batch("B_COLD", due_date="2026-01-07"),
        }
        downtime_map = {
            machine: [
                (datetime(2026, 1, 1, 10, 0), datetime(2026, 1, 1, 16, 0)),   # 第1天占6h
                (datetime(2026, 1, 2, 8, 0), datetime(2026, 1, 2, 14, 0)),    # 第2天占6h
                (datetime(2026, 1, 3, 8, 0), datetime(2026, 1, 3, 13, 0)),    # 第3天占5h
            ]
        }
        seed_results = [
            SimpleNamespace(
                op_id=99, op_code="SEED1", batch_id="B_SEED", seq=10,
                machine_id=machine, operator_id="OP-1", source="internal",
                start_time=datetime(2026, 1, 1, 8, 0), end_time=datetime(2026, 1, 1, 10, 0),
                op_type_name="OT-BN",
            ),
        ]
        resource_pool = None
    elif name == "rank_flip":
        # 关键场景:让 net 相对 gross 翻转批次的 due_budget 排名。
        # 思路:交期窗口大的松批次被重度占用,交期窗口小的紧批次几乎不被占用,
        # 于是按"毛窗口"看松批次预算充裕,但按"净残余"看松批次反而比紧批次更挤。
        # 这样毛/净给出不同的工序优先级,排出不同方案,信号才会显现。
        machine = "MC-BN"
        ops = [
            # 紧批次:窗口小,但几乎不占用
            _op(1, "B_TIGHT", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=5.0),
            # 松批次:窗口大,但被重度占用(downtime+seed 落在它窗口靠后段)
            _op(2, "B_LOOSE", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=10.0),
            # 中批次:做参照
            _op(3, "B_MID", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=6.0),
        ]
        batches = {
            "B_TIGHT": _batch("B_TIGHT", due_date="2026-01-02"),   # 窗口~16h(2工作日)
            "B_LOOSE": _batch("B_LOOSE", due_date="2026-01-09"),   # 窗口~64h(8工作日)
            "B_MID": _batch("B_MID", due_date="2026-01-05"),       # 窗口~40h
        }
        # downtime 全压在 LOOSE 的远端窗口(1/5-1/8),不碰 TIGHT 的近端窗口
        downtime_map = {
            machine: [
                (datetime(2026, 1, 5, 8, 0), datetime(2026, 1, 5, 16, 0)),   # 占8h
                (datetime(2026, 1, 6, 8, 0), datetime(2026, 1, 6, 16, 0)),   # 占8h
                (datetime(2026, 1, 7, 8, 0), datetime(2026, 1, 7, 16, 0)),   # 占8h
                (datetime(2026, 1, 8, 8, 0), datetime(2026, 1, 8, 16, 0)),   # 占8h
            ]
        }
        # seed 也压在 LOOSE 远端
        seed_results = [
            SimpleNamespace(
                op_id=99, op_code="SEED1", batch_id="B_SEED", seq=10,
                machine_id=machine, operator_id="OP-1", source="internal",
                start_time=datetime(2026, 1, 9, 8, 0), end_time=datetime(2026, 1, 9, 16, 0),
                op_type_name="OT-BN",
            ),
        ]
        resource_pool = None
    elif name == "rank_flip_choke":
        # rank_flip 的加压版:松批次被占到净预算 < 紧批次,且整体产能不足以救所有批次,
        # 让毛/净的不同优先级真的转化成不同的逾期/拖期。
        machine = "MC-BN"
        ops = [
            _op(1, "B_TIGHT", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=7.0),
            _op(2, "B_LOOSE", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=12.0),
            _op(3, "B_MID", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=8.0),
            _op(4, "B_MID2", seq=10, machine_id=machine, op_type_id="OT-BN", setup_hours=6.0),
        ]
        batches = {
            "B_TIGHT": _batch("B_TIGHT", due_date="2026-01-03"),
            "B_LOOSE": _batch("B_LOOSE", due_date="2026-01-10"),
            "B_MID": _batch("B_MID", due_date="2026-01-06"),
            "B_MID2": _batch("B_MID2", due_date="2026-01-07"),
        }
        # downtime 集中压 LOOSE 的远端窗口,使其净预算坍缩到 TIGHT 之下
        downtime_map = {
            machine: [
                (datetime(2026, 1, 6, 8, 0), datetime(2026, 1, 6, 16, 0)),
                (datetime(2026, 1, 7, 8, 0), datetime(2026, 1, 7, 16, 0)),
                (datetime(2026, 1, 8, 8, 0), datetime(2026, 1, 8, 16, 0)),
                (datetime(2026, 1, 9, 8, 0), datetime(2026, 1, 9, 16, 0)),
                (datetime(2026, 1, 10, 8, 0), datetime(2026, 1, 10, 16, 0)),
            ]
        }
        seed_results = [
            SimpleNamespace(
                op_id=99, op_code="SEED1", batch_id="B_SEED", seq=10,
                machine_id=machine, operator_id="OP-1", source="internal",
                start_time=datetime(2026, 1, 5, 8, 0), end_time=datetime(2026, 1, 5, 16, 0),
                op_type_name="OT-BN",
            ),
        ]
        resource_pool = None
    elif name == "large_mixed":
        return _build_large_mixed_scenario(differential_block=True)
    elif name == "large_mixed_uniform":
        return _build_large_mixed_scenario(differential_block=False)
    else:
        raise ValueError(f"unknown scenario {name}")

    context = _build_context(ops, seed_results=seed_results)
    # 自动派工:工序未固定机器/人员且提供了 resource_pool 时需要开启
    auto_assign = any(
        not str(getattr(o, "machine_id", "") or "").strip() or not str(getattr(o, "operator_id", "") or "").strip()
        for o in ops
    )
    return {
        "name": name,
        "operations": ops,
        "batches": batches,
        "downtime_map": downtime_map,
        "seed_results": seed_results,
        "resource_pool": resource_pool,
        "context": context,
        "auto_assign": bool(auto_assign),
    }


def _build_large_mixed_scenario(*, differential_block: bool) -> Dict[str, Any]:
    """更大、更难、heuristic-limited 的场景:10 个内制批次、每批 2 道工序(有前后置),
    共享 2 台瓶颈机器(自动派工);交期松紧分布广。

    differential_block=True:把 downtime/seed 重度压在"松交期"批次会用到的远端窗口,
      使净残余预算相对毛窗口发生跨批次排名翻转(净更能识别远端被占用导致的真实紧张)。
    differential_block=False:占用均匀铺开(对照组,毛/净排名基本不翻转)。

    这种规模下 60 条候选 priority ordering 无法穷举解空间,heuristic(受 due_budget 口径影响)
    真正决定 best,从而让毛/净的差异更可能转化为逾期/拖期差异。
    """
    machines = ["MC-BN-1", "MC-BN-2"]
    op_type = "OT-BN"
    # 10 个批次,交期从紧到松;每批 2 道工序(seq 10 -> 20,后者依赖前者)
    due_days = [2, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    setups = [
        (4.0, 3.0), (3.0, 4.0), (5.0, 2.0), (2.0, 5.0), (4.0, 4.0),
        (3.0, 3.0), (5.0, 3.0), (2.0, 4.0), (4.0, 2.0), (3.0, 5.0),
    ]
    ops: List[Any] = []
    batches: Dict[str, Any] = {}
    pred: Dict[int, set] = {}
    succ: Dict[int, set] = {}
    op_id = 1
    for b in range(10):
        bid = f"B{b:02d}"
        prio = "high" if b < 2 else "normal"
        batches[bid] = _batch(bid, due_date=f"2026-01-{due_days[b]:02d}", priority=prio)
        first_id = op_id
        second_id = op_id + 1
        ops.append(_op(first_id, bid, seq=10, machine_id=None, operator_id=None, op_type_id=op_type, setup_hours=setups[b][0]))
        ops.append(_op(second_id, bid, seq=20, machine_id=None, operator_id=None, op_type_id=op_type, setup_hours=setups[b][1]))
        pred[first_id] = set()
        succ[first_id] = {second_id}
        pred[second_id] = {first_id}
        succ[second_id] = set()
        op_id += 2

    if differential_block:
        # 把占用压在远端窗口(松批次会落到的日期),近端(紧批次)几乎不占
        downtime_map = {
            "MC-BN-1": [
                (datetime(2026, 1, d, 8, 0), datetime(2026, 1, d, 16, 0)) for d in (6, 7, 8, 9, 10)
            ],
            "MC-BN-2": [
                (datetime(2026, 1, d, 8, 0), datetime(2026, 1, d, 14, 0)) for d in (7, 8, 9)
            ],
        }
        seed_results = [
            SimpleNamespace(op_id=901, op_code="SEED1", batch_id="B_SEED", seq=10,
                            machine_id="MC-BN-1", operator_id="OP-A", source="internal",
                            start_time=datetime(2026, 1, 5, 8, 0), end_time=datetime(2026, 1, 5, 16, 0), op_type_name=op_type),
            SimpleNamespace(op_id=902, op_code="SEED2", batch_id="B_SEED", seq=10,
                            machine_id="MC-BN-2", operator_id="OP-B", source="internal",
                            start_time=datetime(2026, 1, 6, 8, 0), end_time=datetime(2026, 1, 6, 16, 0), op_type_name=op_type),
        ]
    else:
        # 均匀占用:每天都占一点,毛/净排名基本同序(对照)
        downtime_map = {
            "MC-BN-1": [(datetime(2026, 1, d, 8, 0), datetime(2026, 1, d, 11, 0)) for d in range(1, 11)],
            "MC-BN-2": [(datetime(2026, 1, d, 8, 0), datetime(2026, 1, d, 10, 0)) for d in range(1, 11)],
        }
        seed_results = [
            SimpleNamespace(op_id=901, op_code="SEED1", batch_id="B_SEED", seq=10,
                            machine_id="MC-BN-1", operator_id="OP-A", source="internal",
                            start_time=datetime(2026, 1, 2, 14, 0), end_time=datetime(2026, 1, 2, 16, 0), op_type_name=op_type),
        ]
    resource_pool = {
        "machines_by_op_type": {op_type: machines},
        "operators_by_machine": {"MC-BN-1": ["OP-A"], "MC-BN-2": ["OP-B"]},
        "machines_by_operator": {"OP-A": ["MC-BN-1"], "OP-B": ["MC-BN-2"]},
    }
    context = _build_context(ops, seed_results=seed_results, pred=pred, succ=succ)
    return {
        "name": "large_mixed" + ("" if differential_block else "_uniform"),
        "operations": ops,
        "batches": batches,
        "downtime_map": downtime_map,
        "seed_results": seed_results,
        "resource_pool": resource_pool,
        "context": context,
        "auto_assign": True,
    }


def _build_context(
    ops: List[Any],
    *,
    seed_results: Optional[List[Any]] = None,
    pred: Optional[Dict[int, set]] = None,
    succ: Optional[Dict[int, set]] = None,
) -> Dict[str, Any]:
    """构造 graph_ready_context(无前驱/后继依赖,单工序批次),含 bottleneck_machine_score。

    种子工序(seed_results)必须在 context 里登记为 fixed_op_ids,且
    fixed_op_sources_by_op_id 的 key 集合需与 fixed_op_ids 完全一致,否则
    validate_graph_ready_context 会以 graph_ready_seed_fixed_mismatch 整段拒绝图评分。
    """
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


# ---------------------------------------------------------------------------
# 自检:某批次毛 vs 净的 due_budget 实测值
# ---------------------------------------------------------------------------
def selfcheck(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """对每个工序打印毛/净两口径下的 due_budget_hours,确认两者不等。"""
    cal = _EightHourCalendar()
    rows = {}
    for basis in ("gross", "net"):
        with budget_basis(basis):
            enriched = enrich_graph_ready_v2_metrics(
                {int(o.id): dict(scenario["context"]["node_metrics_by_op_id"][int(o.id)]) for o in scenario["operations"]},
                operations=scenario["operations"],
                batches=scenario["batches"],
                start_dt=_START,
                calendar_service=cal,
                downtime_map=scenario["downtime_map"],
                seed_results=scenario["seed_results"],
                resource_pool=scenario["resource_pool"],
                strict_mode=False,
            )
        rows[basis] = {
            int(oid): {
                "due_deadline_hours": enriched[oid]["due_deadline_hours"],
                "due_budget_hours": enriched[oid]["due_budget_hours"],
                "residual_capacity_window_hours": enriched[oid]["residual_capacity_window_hours"],
                "residual_capacity_hours": enriched[oid]["residual_capacity_hours"],
                "residual_capacity_blocked_hours": enriched[oid]["residual_capacity_blocked_hours"],
                "due_budget_basis": enriched[oid]["due_budget_basis"],
                "due_pressure": enriched[oid]["due_pressure"],
                "slack_hours": enriched[oid]["slack_hours"],
            }
            for oid in sorted(enriched)
        }
    # 对账:每个工序 gross vs net 的 budget 差
    diff = {}
    any_differ = False
    for oid in rows["gross"]:
        g = rows["gross"][oid]["due_budget_hours"]
        n = rows["net"][oid]["due_budget_hours"]
        diff[oid] = {"gross": g, "net": n, "net_minus_gross": round(n - g, 4)}
        if abs(n - g) > 1e-6:
            any_differ = True
    return {"per_basis": rows, "diff": diff, "any_differ": any_differ}


# ---------------------------------------------------------------------------
# 真实排产入口:run_graph_ready_candidates,走 objective_aware_portfolio(v2 候选池)
# ---------------------------------------------------------------------------
def _default_config(*, auto_assign: bool = False):
    values = default_snapshot_values()
    values.update({
        "sort_strategy": "priority_first",
        "dispatch_mode": "sgs",
        "dispatch_rule": "slack",
        "auto_assign_enabled": "yes" if auto_assign else "no",
        "objective": _OBJECTIVE,
        "algo_mode": "improve",
        "time_budget_seconds": 5,
        "ortools_enabled": "no",
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
    })
    return SimpleNamespace(**values)


class _Clock:
    def __init__(self) -> None:
        self._now = 1000.0

    def __call__(self) -> float:
        self._now += 0.01
        return self._now


def _make_scheduler(*, auto_assign: bool = False):
    return GreedyScheduler(calendar_service=_EightHourCalendar(), config_service=_default_config(auto_assign=auto_assign))


def _schedule_with_scheduler(scheduler, **kwargs):
    return scheduler.schedule(**kwargs)


def _baseline_candidate(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """基线:不启用图评分,普通 SGS priority_first 排一遍(纯交期/优先级 dispatch)。"""
    scheduler = _make_scheduler(auto_assign=bool(scenario.get("auto_assign")))
    order = sorted(scenario["batches"].keys())
    results, summary, strategy, params = scheduler.schedule(
        operations=scenario["operations"],
        batches=scenario["batches"],
        strategy=SortStrategy.PRIORITY_FIRST,
        strategy_params={},
        start_dt=_START,
        machine_downtimes=scenario["downtime_map"],
        dispatch_mode="sgs",
        dispatch_rule="slack",
        batch_order_override=order,
        seed_results=scenario["seed_results"],
        resource_pool=scenario["resource_pool"],
        strict_mode=False,
    )
    metrics = compute_metrics(results, scenario["batches"])
    return {
        "results": results,
        "summary": summary,
        "strategy": strategy,
        "params": params,
        "dispatch_mode": "sgs",
        "dispatch_rule": "slack",
        "order": order,
        "metrics": metrics,
        "score": (float(summary.failed_ops),) + objective_score(_OBJECTIVE, metrics),
        "algo_stats": snapshot_algo_stats(scheduler),
        "candidate_origin": "baseline",
        "runtime_ms": 0,
    }


def run_one(scenario: Dict[str, Any], *, basis: str, seed: int) -> Dict[str, Any]:
    """在给定口径(monkeypatch)下,对单个 scenario + seed 跑真实 graph-ready 候选搜索,返回 best 指标。"""
    scheduler = _make_scheduler(auto_assign=bool(scenario.get("auto_assign")))
    baseline = _baseline_candidate(scenario)
    state = OptimizationSearchReportState(
        algorithm_profile=f"due_budget_{basis}",
        seed=int(seed),
        time_budget_seconds=5,
        objective_name=_OBJECTIVE,
        started_at=1000.0,
        candidate_profile={"acceptance": "improve_only"},
        strict_mode=False,
    )
    state.mark_candidate_accepted(baseline, origin="baseline")
    attempts: List[Dict[str, Any]] = []
    improvement_trace: List[Dict[str, Any]] = []
    # 用生产候选构造配置(objective_aware_portfolio -> v2 候选池)
    candidate_profile = build_candidate_profile(
        algo_mode="improve",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        time_budget_seconds=5,
        version=int(seed),
        strict_mode=False,
        ortools_enabled=False,
        graph_sgs_required=True,
    )
    order = sorted(scenario["batches"].keys())
    with budget_basis(basis):
        best = run_graph_ready_candidates(
            algo_mode="improve",
            best=baseline,
            version=int(seed),
            scheduler=scheduler,
            algo_ops_to_schedule=scenario["operations"],
            batches=scenario["batches"],
            start_dt=_START,
            end_date=None,
            downtime_map=scenario["downtime_map"],
            seed_sr_list=scenario["seed_results"],
            base_strategy=SortStrategy.PRIORITY_FIRST,
            base_params={},
            build_order=lambda _s, _p: list(order),
            dispatch_rule_cfg="slack",
            resource_pool=scenario["resource_pool"],
            objective_name=_OBJECTIVE,
            deadline=1e12,
            attempts=attempts,
            improvement_trace=improvement_trace,
            optimizer_algo_stats=snapshot_algo_stats(scheduler),
            t_begin=1000.0,
            readiness_gate_enabled=False,
            strict_mode=False,
            graph_ready_context=scenario["context"],
            clock=_Clock(),
            schedule_fn=_schedule_with_scheduler,
            search_report_state=state,
            candidate_construction=candidate_profile.candidate_construction,
        )
    if best is None:
        raise AssertionError("no best candidate")
    m = best["metrics"]
    bm = baseline["metrics"]
    return {
        "basis": basis,
        "seed": int(seed),
        "overdue_count": int(m.overdue_count),
        "total_tardiness_hours": round(float(m.total_tardiness_hours), 4),
        "weighted_tardiness_hours": round(float(m.weighted_tardiness_hours), 4),
        "failed_ops": int(getattr(best["summary"], "failed_ops", 0) or 0),
        "makespan_hours": round(float(m.makespan_hours), 4),
        "best_origin": str(state.best_origin or ""),
        "best_order": [str(getattr(r, "batch_id", "")) for r in best["results"]],
        "evaluated_candidates": int(state.evaluated_candidates),
        "distinct_candidates": int(len(state.candidate_fingerprints)),
        # 基线参考(口径无关,基线不走图评分)
        "baseline_overdue_count": int(bm.overdue_count),
        "baseline_total_tardiness_hours": round(float(bm.total_tardiness_hours), 4),
        "baseline_failed_ops": int(getattr(baseline["summary"], "failed_ops", 0) or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--scenarios", nargs="*", default=["tight_bottleneck", "two_machine_pool", "heavy_seed_choke"])
    parser.add_argument("--objective", type=str, default="min_overdue")
    parser.add_argument("--tag", type=str, default="")
    parser.add_argument("--output-dir", default=str(ARTIFACT_ROOT / "data"))
    parser.add_argument("--selfcheck-only", action="store_true")
    args = parser.parse_args()

    global _OBJECTIVE
    _OBJECTIVE = args.objective
    print(f"[objective={_OBJECTIVE}]")

    out: Dict[str, Any] = {"selfcheck": {}, "runs": {}}

    for sname in args.scenarios:
        scen = build_scenario(sname)
        sc = selfcheck(scen)
        out["selfcheck"][sname] = sc
        diffs = [(oid, d) for oid, d in sc["diff"].items() if abs(d["net_minus_gross"]) > 1e-6]
        print(f"\n===== SELFCHECK scenario={sname} any_differ={sc['any_differ']} "
              f"({len(diffs)}/{len(sc['diff'])} ops have net<gross) =====")
        # 大实例只打前若干条样本,小实例全打
        sample = sc["diff"].items() if len(sc["diff"]) <= 12 else diffs[:10]
        for oid, d in sample:
            print(f"  op {oid}: gross_budget={d['gross']:.3f}  net_budget={d['net']:.3f}  net-gross={d['net_minus_gross']:+.3f}")

    import os
    out_dir = os.path.abspath(args.output_dir)
    os.makedirs(out_dir, exist_ok=True)
    tag = getattr(args, "tag", "") or _OBJECTIVE

    if args.selfcheck_only:
        p = os.path.join(out_dir, f"selfcheck_{tag}.json")
        with open(p, "w") as f:
            json.dump(out["selfcheck"], f, indent=2, default=str)
        print(f"\n[selfcheck-only] wrote {p}")
        return

    for sname in args.scenarios:
        scen = build_scenario(sname)
        rows = []
        for seed in range(args.seeds):
            for basis in ("gross", "net"):
                rows.append(run_one(scen, basis=basis, seed=seed))
        out["runs"][sname] = rows

    # 汇总打印
    print("\n\n############ RESULTS ############")
    for sname, rows in out["runs"].items():
        print(f"\n===== scenario={sname} =====")
        print(f"{'seed':>4} | {'gross_ovd':>9} {'gross_tard':>10} {'gross_fail':>10} | {'net_ovd':>7} {'net_tard':>9} {'net_fail':>8} | {'d_ovd':>6} {'d_tard':>8}")
        by_seed: Dict[int, Dict[str, Any]] = {}
        for r in rows:
            by_seed.setdefault(r["seed"], {})[r["basis"]] = r
        agg = {"gross_ovd": 0, "net_ovd": 0, "gross_tard": 0.0, "net_tard": 0.0, "gross_fail": 0, "net_fail": 0}
        for seed in sorted(by_seed):
            g = by_seed[seed]["gross"]
            n = by_seed[seed]["net"]
            d_ovd = n["overdue_count"] - g["overdue_count"]
            d_tard = round(n["total_tardiness_hours"] - g["total_tardiness_hours"], 3)
            print(f"{seed:>4} | {g['overdue_count']:>9} {g['total_tardiness_hours']:>10.2f} {g['failed_ops']:>10} | "
                  f"{n['overdue_count']:>7} {n['total_tardiness_hours']:>9.2f} {n['failed_ops']:>8} | {d_ovd:>+6} {d_tard:>+8.2f}")
            agg["gross_ovd"] += g["overdue_count"]
            agg["net_ovd"] += n["overdue_count"]
            agg["gross_tard"] += g["total_tardiness_hours"]
            agg["net_tard"] += n["total_tardiness_hours"]
            agg["gross_fail"] += g["failed_ops"]
            agg["net_fail"] += n["failed_ops"]
        ns = len(by_seed)
        d_ovd_avg = (agg["net_ovd"] - agg["gross_ovd"]) / ns
        d_tard_avg = (agg["net_tard"] - agg["gross_tard"]) / ns
        print(f"  AVG  | gross: ovd={agg['gross_ovd']/ns:.2f} tard={agg['gross_tard']/ns:.2f} fail={agg['gross_fail']/ns:.2f}"
              f"  || net: ovd={agg['net_ovd']/ns:.2f} tard={agg['net_tard']/ns:.2f} fail={agg['net_fail']/ns:.2f}")
        verdict = "NET BETTER (fewer overdue)" if d_ovd_avg < 0 else ("NET WORSE (more overdue)" if d_ovd_avg > 0 else ("NET BETTER on tard" if d_tard_avg < 0 else ("NET WORSE on tard" if d_tard_avg > 0 else "NO DIFFERENCE")))
        print(f"  DELTA(net-gross): d_ovd_avg={d_ovd_avg:+.2f} d_tard_avg={d_tard_avg:+.2f}  ==> {verdict}")
        meta = build_scenario(sname).get("_meta")
        if meta:
            print(f"  instance meta: {meta}")
        # 基线参考
        b = next(iter(by_seed.values()))["gross"]
        print(f"  baseline(no-graph): ovd={b['baseline_overdue_count']} tard={b['baseline_total_tardiness_hours']:.2f} fail={b['baseline_failed_ops']}")

    outpath = os.path.join(out_dir, f"experiment_{tag}.json")
    with open(outpath, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nwrote {outpath}")
    # 还原核验
    assert v2feat._deadline_budget_hours is _ORIG_DEADLINE_BUDGET, "monkeypatch 未还原!"
    print("monkeypatch restored OK:", v2feat._deadline_budget_hours is _ORIG_DEADLINE_BUDGET)


if __name__ == "__main__":
    main()
