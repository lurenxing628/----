"""回归测试：sgs_graph 环检测 Kahn O(V+E) 改造与旧 O(V²) 全表扫描实现语义完全等价（审计 D13）。

旧实现（每弹出一个节点全表扫描 remaining）以内联 oracle 形式保留在本文件里，
新实现改用上游已校验双向一致的 successor_map 做标准 Kahn 释放。
对随机图与边界图（空图/自环/多环/孤立点/图外固定前置）断言两者 raise/不 raise、
错误文案与 field 完全一致；另经 _prepare_graph_ready_state 公共入口锁环检测契约，
并加 4000 节点单链墙钟护栏防止退化回全表扫描。
"""

from __future__ import annotations

import random
import time
from types import SimpleNamespace
from typing import Dict, List

import pytest

from core.algorithms.greedy.dispatch.sgs_graph import (
    _detect_graph_ready_cycle,
    _prepare_graph_ready_state,
)
from core.infrastructure.errors import ValidationError

CHAIN_GUARD_NODE_COUNT = 4000
# 新 O(V+E) 实现单链实测 ~3ms；旧 O(V²) 实现同规模实测 >200ms。
# 300ms 上限给慢机留了两个数量级余量，同时仍能挡住全表扫描回归。
CHAIN_GUARD_LIMIT_MS = 300.0


def _legacy_detect_graph_ready_cycle(*, schedulable_ids: set, predecessor_map: Dict[int, set]) -> None:
    """旧实现逐字 oracle（sgs_graph.py 2026-07-19 版 242-265 行）：全表扫描释放后继。"""
    remaining = {
        op_id: {predecessor_id for predecessor_id in predecessor_map.get(op_id, set()) if predecessor_id in schedulable_ids}
        for op_id in schedulable_ids
    }
    ready = [op_id for op_id, predecessor_ids in remaining.items() if not predecessor_ids]
    visited = set()
    while ready:
        current = ready.pop()
        if current in visited:
            continue
        visited.add(current)
        for op_id, predecessor_ids in remaining.items():
            if current not in predecessor_ids:
                continue
            predecessor_ids.discard(current)
            if not predecessor_ids and op_id not in visited:
                ready.append(op_id)
    if visited != set(schedulable_ids):
        raise ValidationError("图 ready 队列上下文包含环形前后置关系。", field="graph_ready_context")


def _derive_successor_map(predecessor_map: Dict[int, set]) -> Dict[int, set]:
    """按生产链路 _validate_graph_ready_links 保证的双向一致性从前置映射推出后继映射。"""
    successors: Dict[int, set] = {op_id: set() for op_id in predecessor_map}
    for op_id, predecessor_ids in predecessor_map.items():
        for predecessor_id in predecessor_ids:
            successors.setdefault(predecessor_id, set()).add(op_id)
    return successors


def _outcome(func, **kwargs):
    try:
        func(**kwargs)
    except ValidationError as exc:
        return ("raised", str(exc), exc.field)
    return ("ok", None, None)


def _assert_equivalent(schedulable_ids: set, predecessor_map: Dict[int, set]) -> None:
    successor_map = _derive_successor_map(predecessor_map)
    legacy = _outcome(
        _legacy_detect_graph_ready_cycle,
        schedulable_ids=set(schedulable_ids),
        predecessor_map={k: set(v) for k, v in predecessor_map.items()},
    )
    current = _outcome(
        _detect_graph_ready_cycle,
        schedulable_ids=set(schedulable_ids),
        predecessor_map={k: set(v) for k, v in predecessor_map.items()},
        successor_map=successor_map,
    )
    assert current == legacy, (
        f"新旧环检测结果不一致：new={current} legacy={legacy} "
        f"schedulable={sorted(schedulable_ids)} predecessors={predecessor_map}"
    )


def test_empty_graph_equivalent_and_passes() -> None:
    _assert_equivalent(set(), {})


def test_isolated_nodes_equivalent_and_pass() -> None:
    _assert_equivalent({1, 2, 3}, {1: set(), 2: set(), 3: set()})


def test_self_loop_equivalent_and_raises() -> None:
    schedulable = {1, 2}
    predecessors = {1: {1}, 2: set()}
    _assert_equivalent(schedulable, predecessors)
    with pytest.raises(ValidationError, match="环形前后置关系"):
        _detect_graph_ready_cycle(
            schedulable_ids=schedulable,
            predecessor_map=predecessors,
            successor_map=_derive_successor_map(predecessors),
        )


def test_two_node_cycle_equivalent_and_raises() -> None:
    schedulable = {1, 2, 3}
    predecessors = {1: {2}, 2: {1}, 3: set()}
    _assert_equivalent(schedulable, predecessors)
    with pytest.raises(ValidationError, match="环形前后置关系"):
        _detect_graph_ready_cycle(
            schedulable_ids=schedulable,
            predecessor_map=predecessors,
            successor_map=_derive_successor_map(predecessors),
        )


def test_multiple_disjoint_cycles_equivalent_and_raise() -> None:
    predecessors = {
        1: {2},
        2: {1},
        3: {4},
        4: {5},
        5: {3},
        6: set(),
        7: {6},
    }
    _assert_equivalent(set(predecessors), predecessors)


def test_chain_with_branches_equivalent_and_passes() -> None:
    predecessors = {
        1: set(),
        2: {1},
        3: {1},
        4: {2, 3},
        5: {4},
        6: set(),
    }
    _assert_equivalent(set(predecessors), predecessors)


def test_external_fixed_predecessors_are_filtered_identically() -> None:
    # 900/901 不在 schedulable 里（对应固定/已完成工序），两版都应视为已满足。
    schedulable = {1, 2, 3}
    predecessors = {1: {900}, 2: {1, 901}, 3: {2}}
    _assert_equivalent(schedulable, predecessors)


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


def _op(op_id: int) -> SimpleNamespace:
    return SimpleNamespace(id=op_id, batch_id="B1", op_code=f"OP-{op_id:03d}", seq=op_id * 10)


def _prepare_state(predecessors: Dict[int, set]):
    op_ids = sorted(predecessors)
    ops_by_batch = {"B1": [_op(op_id) for op_id in op_ids]}
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": set(op_ids),
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": predecessors,
        "successor_op_ids_by_op_id": _derive_successor_map(predecessors),
        "sort_key_by_op_id": {op_id: (index, index * 10, op_id) for index, op_id in enumerate(op_ids)},
    }
    return _prepare_graph_ready_state(graph_ready_context, ops_by_batch=ops_by_batch)


def test_prepare_graph_ready_state_still_rejects_cycle_via_public_path() -> None:
    with pytest.raises(ValidationError, match="环形前后置关系"):
        _prepare_state({1: {2}, 2: {1}, 3: set()})


def test_prepare_graph_ready_state_still_accepts_dag_via_public_path() -> None:
    state = _prepare_state({1: set(), 2: {1}, 3: {1}, 4: {2, 3}})
    assert state is not None
    assert state["ready_op_ids"] == {1}


def test_cycle_detection_4000_node_chain_stays_linear_no_full_scan_regression() -> None:
    ids = list(range(1, CHAIN_GUARD_NODE_COUNT + 1))
    predecessors: Dict[int, set] = {1: set()}
    for op_id in ids[1:]:
        predecessors[op_id] = {op_id - 1}
    successor_map = _derive_successor_map(predecessors)

    started = time.perf_counter()
    _detect_graph_ready_cycle(
        schedulable_ids=set(ids),
        predecessor_map=predecessors,
        successor_map=successor_map,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert elapsed_ms < CHAIN_GUARD_LIMIT_MS, (
        f"4000 节点单链环检测耗时 {elapsed_ms:.1f}ms 超过 {CHAIN_GUARD_LIMIT_MS}ms 护栏，"
        "疑似退化回 O(V²) 全表扫描。"
    )
