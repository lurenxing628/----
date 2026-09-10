"""合同测试：optimizer 侧图 ready 环检测改共享 Kahn 实现（审计 A09，D13 同族）。

旧实现（每弹出一个节点全表扫描 remaining 的 O(V²) 写法）以内联 oracle 形式保留，
对随机 DAG / 含环图 / 图外固定前置断言新旧 raise/不 raise 与错误载荷
（message/field/details.reason）完全一致；另锁两条防漂移合同：
- sgs_graph 与 optimizer_graph_ready_context 引用的是同一个共享函数对象
  （core/algorithm_runtime/graph_cycle.kahn_unreachable_op_ids），杜绝再次
  "修一漏一"的双拷贝语义漂移；
- 4000 节点单链墙钟护栏，防止退化回全表扫描。
"""

from __future__ import annotations

import random
import time
from typing import Dict

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_graph_ready_context import _detect_cycle

CHAIN_GUARD_NODE_COUNT = 4000
# 共享 Kahn 实现单链实测 ~3ms；旧 O(V²) 实现同规模实测 >200ms。
# 300ms 上限给慢机留两个数量级余量，同时仍能挡住全表扫描回归。
CHAIN_GUARD_LIMIT_MS = 300.0


def _legacy_detect_cycle(*, schedulable_ids: set, predecessor_map: Dict[int, set]) -> None:
    """旧实现逐字 oracle（optimizer_graph_ready_context.py 2026-07-19 版 129-149 行）。"""
    remaining = {op_id: {pre for pre in predecessor_map.get(op_id, set()) if pre in schedulable_ids} for op_id in schedulable_ids}
    ready = [op_id for op_id, predecessors in remaining.items() if not predecessors]
    visited = set()
    while ready:
        current = ready.pop()
        if current in visited:
            continue
        visited.add(current)
        for op_id, predecessors in remaining.items():
            if current not in predecessors:
                continue
            predecessors.discard(current)
            if not predecessors and op_id not in visited:
                ready.append(op_id)
    if visited != set(schedulable_ids):
        raise ValidationError(
            "图 ready 候选包含环形前后置关系。",
            field="graph_ready_context",
            details={"reason": "graph_ready_cycle_detected"},
        )


def _derive_successor_map(predecessor_map: Dict[int, set]) -> Dict[int, set]:
    successors: Dict[int, set] = {op_id: set() for op_id in predecessor_map}
    for op_id, predecessor_ids in predecessor_map.items():
        for predecessor_id in predecessor_ids:
            successors.setdefault(predecessor_id, set()).add(op_id)
    return successors


def _outcome(func, **kwargs):
    try:
        func(**kwargs)
    except ValidationError as exc:
        details = getattr(exc, "details", None) or {}
        return ("raised", str(exc), exc.field, details.get("reason"))
    return ("ok", None, None, None)


def _assert_equivalent(schedulable_ids: set, predecessor_map: Dict[int, set]) -> None:
    legacy = _outcome(
        _legacy_detect_cycle,
        schedulable_ids=set(schedulable_ids),
        predecessor_map={k: set(v) for k, v in predecessor_map.items()},
    )
    current = _outcome(
        _detect_cycle,
        schedulable_ids=set(schedulable_ids),
        predecessor_map={k: set(v) for k, v in predecessor_map.items()},
        successor_map=_derive_successor_map(predecessor_map),
    )
    assert current == legacy, (
        f"optimizer 侧新旧环检测结果不一致：new={current} legacy={legacy} "
        f"schedulable={sorted(schedulable_ids)} predecessors={predecessor_map}"
    )


def test_shared_kahn_is_single_implementation_across_both_validators() -> None:
    # 防漂移合同：两处校验器必须引用同一个共享函数对象（审计 A09 根因是双拷贝
    # "修一漏一"）；再新增第三处图校验时也应复用该实现。
    import core.algorithm_runtime.graph_cycle as shared
    import core.algorithms.greedy.dispatch.sgs_graph as sgs_graph
    import core.services.scheduler.run.optimizer_graph_ready_context as optimizer_context

    assert sgs_graph.kahn_unreachable_op_ids is shared.kahn_unreachable_op_ids
    assert optimizer_context.kahn_unreachable_op_ids is shared.kahn_unreachable_op_ids


def test_empty_and_isolated_graphs_equivalent() -> None:
    _assert_equivalent(set(), {})
    _assert_equivalent({1, 2, 3}, {1: set(), 2: set(), 3: set()})


def test_self_loop_and_two_node_cycle_equivalent_and_raise() -> None:
    _assert_equivalent({1, 2}, {1: {1}, 2: set()})
    _assert_equivalent({1, 2, 3}, {1: {2}, 2: {1}, 3: set()})
    with pytest.raises(ValidationError, match="环形前后置关系") as excinfo:
        _detect_cycle(
            schedulable_ids={1, 2},
            predecessor_map={1: {2}, 2: {1}},
            successor_map={1: {2}, 2: {1}},
        )
    assert excinfo.value.details.get("reason") == "graph_ready_cycle_detected"


def test_external_fixed_predecessors_are_filtered_identically() -> None:
    # 900/901 不在 schedulable 里（固定/已完成工序），两版都视为已满足。
    _assert_equivalent({1, 2, 3}, {1: {900}, 2: {1, 901}, 3: {2}})


def test_random_graphs_equivalent_across_dag_and_cyclic_inputs() -> None:
    rng = random.Random(20260720)
    for round_index in range(200):
        node_count = rng.randint(1, 60)
        ids = list(range(1, node_count + 1))
        predecessors: Dict[int, set] = {op_id: set() for op_id in ids}
        # 随机 DAG 骨架：只允许小 id -> 大 id。
        for op_id in ids:
            for _ in range(rng.randint(0, 3)):
                if op_id > 1:
                    predecessors[op_id].add(rng.randint(1, op_id - 1))
        # 一半回合注入 1-2 条反向边制造环。
        if round_index % 2 == 0 and node_count >= 2:
            for _ in range(rng.randint(1, 2)):
                small = rng.randint(1, node_count - 1)
                large = rng.randint(small + 1, node_count)
                predecessors[small].add(large)
        # 三分之一回合掺入图外固定前置。
        if round_index % 3 == 0:
            victim = rng.choice(ids)
            predecessors[victim].add(9000 + round_index)
        _assert_equivalent(set(ids), predecessors)


def test_cycle_detection_4000_node_chain_stays_linear_no_full_scan_regression() -> None:
    ids = list(range(1, CHAIN_GUARD_NODE_COUNT + 1))
    predecessors: Dict[int, set] = {1: set()}
    for op_id in ids[1:]:
        predecessors[op_id] = {op_id - 1}
    successor_map = _derive_successor_map(predecessors)

    started = time.perf_counter()
    _detect_cycle(
        schedulable_ids=set(ids),
        predecessor_map=predecessors,
        successor_map=successor_map,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert elapsed_ms < CHAIN_GUARD_LIMIT_MS, (
        f"optimizer 侧 4000 节点单链环检测耗时 {elapsed_ms:.1f}ms 超过 {CHAIN_GUARD_LIMIT_MS}ms 护栏，"
        "疑似退化回 O(V²) 全表扫描。"
    )
