"""Kahn 拓扑环检测：返回按拓扑释放后仍不可达（成环）的待排节点集合。

报错文案与错误载荷由调用方自定，不属于本算法的职责。唯一生产调用方是
sgs_graph.prepare_graph_ready_topology（静态拓扑编译）。

放在 core/algorithm_runtime：core/algorithms 与 core/services 都可以 import 本目录，
本目录不反向依赖它们。本模块只依赖标准库。
"""

from __future__ import annotations

from typing import AbstractSet, List, Mapping, Set


def kahn_unreachable_op_ids(
    *,
    schedulable_ids: AbstractSet[int],
    successor_map: Mapping[int, AbstractSet[int]],
    initial_remaining_counts: Mapping[int, int],
) -> AbstractSet[int]:
    """按 Kahn 拓扑释放后仍不可达的待排节点集合；空集等价于 DAG。复杂度 O(V+E)。

    - 生产者从同一边集同步构造前驱与后继映射；sgs_graph.prepare_graph_ready_topology
      负责节点集合范围准入并预计算待排节点初始入度（initial_remaining_counts），本函数在此基础上执行 Kahn 拓扑剥离环检测。
    - 落在 schedulable_ids 之外的前置（固定/已报工工序）在预计算初始入度时已视为满足。
    - 落在 schedulable_ids 之外的后继（固定/已报工工序）不参与释放。
    """
    remaining = dict(initial_remaining_counts)
    ready: List[int] = [op_id for op_id, count in remaining.items() if count == 0]
    visited: Set[int] = set()
    while ready:
        current = ready.pop()
        visited.add(current)
        for op_id in successor_map[current]:
            count = remaining.get(op_id)
            if not count:
                continue
            remaining[op_id] = count - 1
            if count == 1:
                ready.append(op_id)
    return schedulable_ids - visited


__all__ = ["kahn_unreachable_op_ids"]
