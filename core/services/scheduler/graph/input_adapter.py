from __future__ import annotations

from typing import AbstractSet, Iterable, List, Mapping, Optional, Tuple, cast

from core.algorithm_contracts.resource_pool import ResourcePool
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.algorithm_contracts.value_domains import INTERNAL, MERGED
from core.algorithm_runtime.operation_effort import internal_required_hours
from core.algorithm_runtime.piece_input import external_group_key
from core.models.batch import Batch

from .id_policy import make_operation_node_id
from .types import OperationGraphNode


def build_operation_nodes_from_rows(
    rows: Iterable[OpForScheduleAlgo],
    *,
    batches: Mapping[str, Batch],
    resource_pool: ResourcePool,
    frozen_op_ids: AbstractSet[int],
) -> List[OperationGraphNode]:
    return [_build_operation_node(row, batches=batches, resource_pool=resource_pool, frozen_op_ids=frozen_op_ids)
            for row in rows]


def _external_group_key(row: OpForScheduleAlgo) -> Optional[Tuple[str, ...]]:
    if row.source == INTERNAL or row.ext_merge_mode != MERGED:
        return None
    return external_group_key(row)


def _build_operation_node(
    row: OpForScheduleAlgo,
    *,
    batches: Mapping[str, Batch],
    resource_pool: ResourcePool,
    frozen_op_ids: AbstractSet[int],
) -> OperationGraphNode:
    # 算法工序由排产输入构建一次给出规范值（编号、文本、来源、工时、外协周期都已校验），批次同样来自读取边界；
    # 这里只做图节点投影，不再逐字段复核。
    return OperationGraphNode(
        node_id=make_operation_node_id(row.id),
        batch_id=row.batch_id,
        piece_id=row.piece_id,
        op_code=row.op_code,
        seq=row.seq,
        duration_minutes=_operation_duration_minutes(row, batches[row.batch_id]),
        source=row.source,
        is_frozen=row.id in frozen_op_ids,
        machine_id=row.machine_id if row.source == INTERNAL else None,
        candidate_machine_ids=(
            resource_pool.static_machine_candidates(row.machine_id, row.operator_id, row.op_type_id)
            if row.source == INTERNAL else ()
        ),
        external_group_key=_external_group_key(row),
        raw={"id": row.id},
    )


def _operation_duration_minutes(row: OpForScheduleAlgo, batch: Batch) -> int:
    if row.source == INTERNAL:
        # Every internal row, the run's retained and completed ones included, by the one standard-work formula.
        return _round_minutes(internal_required_hours(row, batch) * 60)
    # 合并外协按整组周期；其余外协按本道周期。两者都由排产输入构建按冻结周期记录给成正数。
    if row.ext_merge_mode == MERGED:
        return _round_minutes(cast(float, row.ext_group_total_days) * 24 * 60)
    return _round_minutes(cast(float, row.ext_days) * 24 * 60)


def _round_minutes(value: float) -> int:
    return int(round(value))


__all__ = ["build_operation_nodes_from_rows"]
