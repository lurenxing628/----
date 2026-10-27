from __future__ import annotations

from typing import AbstractSet, Any, Dict, Iterable, List, Mapping, Optional, Tuple, cast

from core.algorithm_contracts.types import OpForScheduleAlgo
from core.algorithm_contracts.value_domains import INTERNAL, MERGED
from core.models.batch import Batch

from .id_policy import make_operation_node_id
from .types import OperationGraphNode


class GraphInputContractError(ValueError):
    pass


def build_operation_nodes_from_rows(
    rows: Iterable[OpForScheduleAlgo],
    *,
    batches: Mapping[str, Batch],
    resource_pool: Optional[Mapping[str, Any]] = None,
    frozen_op_ids: AbstractSet[int] = frozenset(),
    resource_preparation: Optional[GraphResourcePreparation] = None,
) -> List[OperationGraphNode]:
    nodes: List[OperationGraphNode] = []
    pool = resource_preparation if resource_preparation is not None else GraphResourcePreparation(resource_pool)
    for row in rows:
        nodes.append(_build_operation_node(row, batches=batches, resource_pool=pool, frozen_op_ids=frozen_op_ids))
    return nodes


class GraphResourcePreparation:
    """Resource candidates shared by equal work types and fixed assignments in one graph."""

    def __init__(self, resource_pool: Optional[Mapping[str, Any]]) -> None:
        self.machines_by_op_type = {} if resource_pool is None else resource_pool["machines_by_op_type"]
        self.machines_by_operator = {} if resource_pool is None else resource_pool["machines_by_operator"]
        self._candidates: Dict[Tuple[Optional[str], Optional[str], str], Tuple[str, ...]] = {}

    def candidates_for(self, row: OpForScheduleAlgo) -> Tuple[str, ...]:
        key = (row.machine_id, row.operator_id, row.op_type_id)
        if key not in self._candidates:
            self._candidates[key] = _candidate_machine_ids(row, resource_pool=self)
        return self._candidates[key]


def _build_operation_node(
    row: OpForScheduleAlgo,
    *,
    batches: Mapping[str, Batch],
    resource_pool: GraphResourcePreparation,
    frozen_op_ids: AbstractSet[int],
) -> OperationGraphNode:
    # 算法工序由排产输入构建一次给出规范值（编号、文本、来源、工时、外协周期都已校验），批次同样来自读取边界；
    # 这里只做图节点投影，不再逐字段复核。
    batch = batches[row.batch_id]
    return OperationGraphNode(
        node_id=make_operation_node_id(row.id),
        batch_id=row.batch_id,
        piece_id=row.piece_id,
        op_code=row.op_code,
        seq=row.seq,
        duration_minutes=_operation_duration_minutes(row, batch),
        source=row.source,
        is_frozen=row.id in frozen_op_ids,
        machine_id=row.machine_id,
        candidate_machine_ids=resource_pool.candidates_for(row),
        raw={"id": row.id},
    )


def _operation_duration_minutes(row: OpForScheduleAlgo, batch: Batch) -> int:
    if row.source == INTERNAL:
        return _round_minutes((row.setup_hours + row.unit_hours * batch.quantity) * 60)
    # 合并外协按整组周期；其余外协按本道周期。两者都由排产输入构建按冻结周期记录给成正数。
    if row.ext_merge_mode == MERGED:
        return _round_minutes(cast(float, row.ext_group_total_days) * 24 * 60)
    return _round_minutes(cast(float, row.ext_days) * 24 * 60)


def _round_minutes(value: float) -> int:
    return int(round(value))


def _candidate_machine_ids(row: OpForScheduleAlgo, *, resource_pool: GraphResourcePreparation) -> Tuple[str, ...]:
    fixed_machine = row.machine_id
    fixed_operator = row.operator_id
    op_type_id = row.op_type_id
    if fixed_machine:
        candidates = (fixed_machine,)
    elif fixed_operator:
        candidates = tuple(resource_pool.machines_by_operator.get(fixed_operator, ()))
    elif op_type_id and op_type_id in resource_pool.machines_by_op_type:
        return tuple(resource_pool.machines_by_op_type[op_type_id])
    else:
        return ()
    if op_type_id and op_type_id in resource_pool.machines_by_op_type:
        allowed = set(resource_pool.machines_by_op_type[op_type_id])
        return tuple(machine_id for machine_id in candidates if machine_id in allowed)
    return candidates


__all__ = ["GraphInputContractError", "GraphResourcePreparation", "build_operation_nodes_from_rows"]
