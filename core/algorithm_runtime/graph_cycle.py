"""Kahn 拓扑环检测的唯一共享实现（审计 D13 / A09 同族收敛）。

背景：sgs_graph（算法层图上下文入口校验）与 optimizer_graph_ready_context
（optimizer 侧图 ready 候选校验器）各持有一份同语义环检测。2026-07-19 审计
D13 只把 sgs 侧从"每弹出一个节点全表扫描 remaining"的 O(V²) 写法修成 Kahn，
optimizer 侧残留旧写法（实测 8000 点 839ms vs sgs 侧 3.85ms），且两份拷贝已
实际发生一次"修一漏一"的语义漂移。本模块把环检测算法收敛为单一实现，返回
不可达（成环）节点集合，报错文案与错误载荷由各调用方自定（两处的
message/field/details.reason 口径不同，不属于共享算法的职责）。

依赖边界取舍：放在 core/algorithm_runtime 而不是让 optimizer 侧 import
sgs_graph 的函数——core/algorithms 与 core/services 都允许 import
core/algorithm_runtime（反向禁止），且本 leaf 目录被
tests/algorithm/test_algorithms_a3_dependency_boundary.py 锁死不得 import
core.algorithms / core.services；若走 sgs_graph 公开函数方案，会让 services
层耦合 dispatch 内部模块并把 `_` 前缀内部 API 变成跨层合同，防漂移能力更弱。

本模块只依赖标准库。
"""

from __future__ import annotations

from typing import Dict, List, Set


def kahn_unreachable_op_ids(
    *,
    schedulable_ids: Set[int],
    predecessor_map: Dict[int, set],
    successor_map: Dict[int, set],
) -> Set[int]:
    """按 Kahn 拓扑释放后仍不可达的待排节点集合；空集等价于 DAG。

    - predecessor_map 中落在 schedulable_ids 之外的前置（固定/已完成工序）视为已满足，
      与 sgs_graph / optimizer 两侧既有语义一致。
    - 复杂度 O(V+E)：借 successor_map 做后继定向释放，不做全表扫描。
    - 调用方必须先保证 predecessor_map / successor_map 双向一致（两处生产调用点
      都在环检测之前完成该校验：sgs_graph._validate_graph_ready_links 与
      optimizer_graph_ready_context._validate_bidirectional_links）。
    """
    remaining = {
        op_id: {predecessor_id for predecessor_id in predecessor_map.get(op_id, set()) if predecessor_id in schedulable_ids}
        for op_id in schedulable_ids
    }
    ready: List[int] = [op_id for op_id, predecessor_ids in remaining.items() if not predecessor_ids]
    visited: Set[int] = set()
    while ready:
        current = ready.pop()
        if current in visited:
            continue
        visited.add(current)
        for op_id in successor_map.get(current, set()):
            predecessor_ids = remaining.get(op_id)
            if predecessor_ids is None or current not in predecessor_ids:
                continue
            predecessor_ids.discard(current)
            if not predecessor_ids and op_id not in visited:
                ready.append(op_id)
    return set(schedulable_ids) - visited


__all__ = ["kahn_unreachable_op_ids"]
