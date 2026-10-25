from __future__ import annotations

from collections.abc import Mapping as MappingABC
from datetime import date
from typing import AbstractSet, Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union, cast

from core.algorithm_contracts.operator_eligibility import qualified_operators
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
        self.skills_pool = resource_pool
        self.machines_by_op_type = _mapping_part(resource_pool, "machines_by_op_type")
        self.operators_by_machine = _mapping_part(resource_pool, "operators_by_machine")
        self.machines_by_operator = _mapping_part(resource_pool, "machines_by_operator")
        self._candidates: Dict[Tuple[Optional[str], Optional[str], str],
                               Tuple[Tuple[str, ...], Tuple[str, ...]]] = {}

    def candidates_for(self, row: OpForScheduleAlgo) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        key = (row.machine_id, row.operator_id, row.op_type_id)
        if key not in self._candidates:
            machines = _candidate_machine_ids(row, resource_pool=self)
            operators = _candidate_operator_ids(row, candidate_machine_ids=machines, resource_pool=self)
            self._candidates[key] = machines, operators
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
    candidate_machine_ids, candidate_operator_ids = resource_pool.candidates_for(row)
    frozen = row.id in frozen_op_ids
    return OperationGraphNode(
        node_id=make_operation_node_id(row.batch_id, row.op_code, row.id),
        batch_id=row.batch_id,
        piece_id=row.piece_id,
        op_code=row.op_code,
        seq=row.seq,
        name=row.op_type_name,
        duration_minutes=_operation_duration_minutes(row, batch),
        part_no=batch.part_no,
        priority=batch.priority,
        source=row.source,
        due_date=_due_date_text(batch.due_date),
        is_frozen=frozen,
        fixed_source="freeze_window" if frozen else "",
        op_type_id=row.op_type_id,
        machine_id=row.machine_id,
        operator_id=row.operator_id,
        supplier_id=row.supplier_id,
        ext_group_id=row.ext_group_id,
        ext_merge_mode="" if row.ext_merge_mode is None else row.ext_merge_mode,
        ext_group_total_days=row.ext_group_total_days,
        candidate_machine_ids=candidate_machine_ids,
        candidate_operator_ids=candidate_operator_ids,
        raw={"id": row.id, "batch_id": row.batch_id, "op_code": row.op_code, "seq": row.seq, "source": row.source,
             "op_type_id": row.op_type_id, "machine_id": row.machine_id, "operator_id": row.operator_id,
             "supplier_id": row.supplier_id, "ext_group_id": row.ext_group_id, "ext_merge_mode": row.ext_merge_mode},
    )


def _mapping_part(source: Optional[Mapping[str, Any]], key: str) -> Mapping[Any, Any]:
    if source is None:
        return {}
    if not isinstance(source, MappingABC):
        raise GraphInputContractError("resource_pool 必须是映射。")
    if key not in source:
        return {}
    value = source[key]
    if isinstance(value, MappingABC):
        return value
    raise GraphInputContractError(f"resource_pool.{key} 必须是映射。")


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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
        candidates = [fixed_machine]
    elif fixed_operator:
        candidates = _machines_for_fixed_operator(fixed_operator, resource_pool=resource_pool)
    elif op_type_id and op_type_id in resource_pool.machines_by_op_type:
        return _unique_text_tuple(_text_list(resource_pool.machines_by_op_type.get(op_type_id)))
    else:
        return ()
    if op_type_id and op_type_id in resource_pool.machines_by_op_type:
        allowed = set(_text_list(resource_pool.machines_by_op_type.get(op_type_id)))
        candidates = [machine_id for machine_id in candidates if machine_id in allowed]
    return _unique_text_tuple(candidates)


def _machines_for_fixed_operator(fixed_operator: str, *, resource_pool: GraphResourcePreparation) -> List[str]:
    candidates = _text_list(resource_pool.machines_by_operator.get(fixed_operator))
    if candidates:
        return candidates
    found: List[str] = []
    for machine_id, operator_ids in resource_pool.operators_by_machine.items():
        machine_text = _optional_text(machine_id)
        if machine_text and fixed_operator in _text_list(operator_ids):
            found.append(machine_text)
    return found


def _candidate_operator_ids(
    row: OpForScheduleAlgo,
    *,
    candidate_machine_ids: Tuple[str, ...],
    resource_pool: GraphResourcePreparation,
) -> Tuple[str, ...]:
    fixed_operator = row.operator_id
    if fixed_operator:
        if not candidate_machine_ids:
            return tuple(qualified_operators(resource_pool.skills_pool, [fixed_operator], row.op_type_id))
        for machine_id in candidate_machine_ids:
            if fixed_operator in _text_list(resource_pool.operators_by_machine.get(machine_id)):
                return tuple(qualified_operators(resource_pool.skills_pool, [fixed_operator], row.op_type_id))
        return ()
    if not candidate_machine_ids:
        return ()
    candidates: List[str] = []
    for machine_id in candidate_machine_ids:
        candidates.extend(_text_list(resource_pool.operators_by_machine.get(machine_id)))
    return _unique_text_tuple(qualified_operators(resource_pool.skills_pool, candidates, row.op_type_id))


def _text_list(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        text = _optional_text(values)
        return [text] if text else []
    return [text for text in (_optional_text(value) for value in values or []) if text]


def _unique_text_tuple(values: Iterable[Any]) -> Tuple[str, ...]:
    ordered: List[str] = []
    seen = set()
    for value in values:
        text = _optional_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return tuple(ordered)


def _due_date_text(value: Union[str, date, None]) -> Optional[str]:
    # Batches.due_date 是 DATE 列：连接按声明类型把它读成 date；读取边界 batch_model 已核对过，
    # 只剩 date 与规范的 ISO 文本两种形态，这里统一成文本。
    if isinstance(value, date):
        return value.isoformat()
    return value


__all__ = ["GraphInputContractError", "GraphResourcePreparation", "build_operation_nodes_from_rows"]
