from __future__ import annotations

from collections.abc import Mapping as MappingABC
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .id_policy import GraphNodeIdError, make_operation_node_id
from .types import OperationGraphNode


class GraphInputContractError(ValueError):
    pass


def build_operation_nodes_from_rows(
    rows: Iterable[Any],
    *,
    batches: Mapping[str, Any],
    resource_pool: Optional[Mapping[str, Any]] = None,
) -> List[OperationGraphNode]:
    nodes: List[OperationGraphNode] = []
    pool = _ResourcePoolView(resource_pool)
    for row in rows:
        nodes.append(_build_operation_node(row, batches=batches, resource_pool=pool))
    return nodes


class _ResourcePoolView:
    def __init__(self, resource_pool: Optional[Mapping[str, Any]]) -> None:
        self.machines_by_op_type = _mapping_part(resource_pool, "machines_by_op_type")
        self.operators_by_machine = _mapping_part(resource_pool, "operators_by_machine")
        self.machines_by_operator = _mapping_part(resource_pool, "machines_by_operator")


def _build_operation_node(row: Any, *, batches: Mapping[str, Any], resource_pool: _ResourcePoolView) -> OperationGraphNode:
    scope = _operation_scope(row)
    batch_id = _require_text(row, "batch_id", scope=scope)
    op_code = _require_text(row, "op_code", scope=scope)
    batch = _require_batch(batches, batch_id, scope=scope)
    seq = _require_int(row, "seq", scope=scope)
    source = _require_source(row, scope=scope)
    ext_group_total_days = _optional_positive_float(
        _read_field(row, "ext_group_total_days"),
        field="ext_group_total_days",
        scope=scope,
    )
    duration_minutes = _operation_duration_minutes(
        row,
        batch,
        source=source,
        ext_group_total_days=ext_group_total_days,
        scope=scope,
    )
    candidate_machine_ids = _candidate_machine_ids(row, resource_pool=resource_pool)
    candidate_operator_ids = _candidate_operator_ids(
        row,
        candidate_machine_ids=candidate_machine_ids,
        resource_pool=resource_pool,
    )
    node_data: Dict[str, Any] = {
        "node_id": _operation_node_id(row, batch_id=batch_id, op_code=op_code, scope=scope),
        "batch_id": batch_id,
        "op_code": op_code,
        "seq": seq,
        "name": _optional_text(_read_field(row, "op_type_name")) or "",
        "duration_minutes": duration_minutes,
        "part_no": _optional_text(_read_field(batch, "part_no")),
        "source": source,
        "due_date": _optional_due_date(_read_field(batch, "due_date")),
        "op_type_id": _optional_text(_read_field(row, "op_type_id")),
        "machine_id": _optional_text(_read_field(row, "machine_id")),
        "operator_id": _optional_text(_read_field(row, "operator_id")),
        "supplier_id": _optional_text(_read_field(row, "supplier_id")),
        "ext_group_id": _optional_text(_read_field(row, "ext_group_id")),
        "ext_merge_mode": _optional_text(_read_field(row, "ext_merge_mode")) or "",
        "ext_group_total_days": ext_group_total_days,
        "merge_context_degraded": bool(_read_field(row, "merge_context_degraded")),
        "candidate_machine_ids": candidate_machine_ids,
        "candidate_operator_ids": candidate_operator_ids,
        "raw": _raw_snapshot(row),
    }
    priority = _optional_text(_read_field(batch, "priority"))
    if priority:
        node_data["priority"] = priority
    status = _optional_text(_read_field(row, "status"))
    if status:
        node_data["status"] = status
    return OperationGraphNode(**node_data)


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


def _read_field(row: Any, field: str) -> Any:
    if isinstance(row, dict):
        return row.get(field)
    return getattr(row, field, None)


def _operation_scope(row: Any) -> str:
    row_id = _read_field(row, "id")
    row_id_text = _optional_text(row_id)
    if row_id_text:
        return f"graph_input.op[{row_id_text}]"
    batch_id = _optional_text(_read_field(row, "batch_id")) or "?"
    seq = _optional_text(_read_field(row, "seq")) or "?"
    return f"graph_input.batch[{batch_id}].seq[{seq}]"


def _require_batch(batches: Mapping[str, Any], batch_id: str, *, scope: str) -> Any:
    batch = batches.get(batch_id)
    if batch is None:
        raise GraphInputContractError(f"{scope} 找不到批次 {batch_id}")
    return batch


def _require_text(row: Any, field: str, *, scope: str) -> str:
    text = _optional_text(_read_field(row, field))
    if not text:
        raise GraphInputContractError(f"{scope} 缺少必填字段 {field}")
    return text


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _require_source(row: Any, *, scope: str) -> str:
    source = _require_text(row, "source", scope=scope).lower()
    if source not in ("internal", "external"):
        raise GraphInputContractError(f"{scope} 字段 source 只允许 internal/external：{source!r}")
    return source


def _require_int(row: Any, field: str, *, scope: str) -> int:
    value = _read_field(row, field)
    if isinstance(value, bool):
        raise GraphInputContractError(f"{scope} 字段 {field} 不是整数：{value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        signless_text = text[1:] if text[:1] in ("+", "-") else text
        if signless_text and signless_text.isdigit():
            return int(text)
    raise GraphInputContractError(f"{scope} 字段 {field} 不是整数：{value!r}")


def _require_nonnegative_float(value: Any, *, field: str, scope: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise GraphInputContractError(f"{scope} 字段 {field} 不是数字：{value!r}") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise GraphInputContractError(f"{scope} 字段 {field} 必须是有限数字：{value!r}")
    if number < 0:
        raise GraphInputContractError(f"{scope} 字段 {field} 不能为负数：{value!r}")
    return number


def _require_positive_float(value: Any, *, field: str, scope: str) -> float:
    number = _require_nonnegative_float(value, field=field, scope=scope)
    if number <= 0:
        raise GraphInputContractError(f"{scope} 字段 {field} 必须大于 0：{value!r}")
    return number


def _optional_positive_float(value: Any, *, field: str, scope: str) -> Optional[float]:
    if value in (None, ""):
        return None
    return _require_positive_float(value, field=field, scope=scope)


def _operation_duration_minutes(
    row: Any,
    batch: Any,
    *,
    source: str,
    ext_group_total_days: Optional[float],
    scope: str,
) -> int:
    if source == "internal":
        setup_hours = _require_nonnegative_float(_read_field(row, "setup_hours"), field="setup_hours", scope=scope)
        unit_hours = _require_nonnegative_float(_read_field(row, "unit_hours"), field="unit_hours", scope=scope)
        quantity = _require_nonnegative_float(_read_field(batch, "quantity"), field="quantity", scope=scope)
        return _round_minutes((setup_hours + unit_hours * quantity) * 60, scope=scope)
    if _is_merged_external(row) and ext_group_total_days is not None:
        return _round_minutes(ext_group_total_days * 24 * 60, scope=scope)
    ext_days = _require_positive_float(_read_field(row, "ext_days"), field="ext_days", scope=scope)
    return _round_minutes(ext_days * 24 * 60, scope=scope)


def _is_merged_external(row: Any) -> bool:
    merge_mode = (_optional_text(_read_field(row, "ext_merge_mode")) or "").lower()
    return merge_mode == "merged"


def _round_minutes(value: float, *, scope: str) -> int:
    minutes = int(round(value))
    if minutes < 0:
        raise GraphInputContractError(f"{scope} duration_minutes 不能为负数：{value!r}")
    return minutes


def _operation_node_id(row: Any, *, batch_id: str, op_code: str, scope: str) -> str:
    try:
        return make_operation_node_id(batch_id, op_code, _read_field(row, "id"))
    except GraphNodeIdError as exc:
        raise GraphInputContractError(f"{scope} 节点 ID 无法生成：{exc}") from exc


def _candidate_machine_ids(row: Any, *, resource_pool: _ResourcePoolView) -> Tuple[str, ...]:
    fixed_machine = _optional_text(_read_field(row, "machine_id"))
    fixed_operator = _optional_text(_read_field(row, "operator_id"))
    op_type_id = _optional_text(_read_field(row, "op_type_id"))
    if fixed_machine:
        candidates = [fixed_machine]
    elif fixed_operator:
        candidates = _machines_for_fixed_operator(fixed_operator, resource_pool=resource_pool)
    elif op_type_id and op_type_id in resource_pool.machines_by_op_type:
        candidates = _text_list(resource_pool.machines_by_op_type.get(op_type_id))
    else:
        candidates = []
    if op_type_id and op_type_id in resource_pool.machines_by_op_type:
        allowed = set(_text_list(resource_pool.machines_by_op_type.get(op_type_id)))
        candidates = [machine_id for machine_id in candidates if machine_id in allowed]
    return _unique_text_tuple(candidates)


def _machines_for_fixed_operator(fixed_operator: str, *, resource_pool: _ResourcePoolView) -> List[str]:
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
    row: Any,
    *,
    candidate_machine_ids: Tuple[str, ...],
    resource_pool: _ResourcePoolView,
) -> Tuple[str, ...]:
    fixed_operator = _optional_text(_read_field(row, "operator_id"))
    if fixed_operator:
        if not candidate_machine_ids:
            return (fixed_operator,)
        for machine_id in candidate_machine_ids:
            if fixed_operator in _text_list(resource_pool.operators_by_machine.get(machine_id)):
                return (fixed_operator,)
        return ()
    if not candidate_machine_ids:
        return ()
    candidates: List[str] = []
    for machine_id in candidate_machine_ids:
        candidates.extend(_text_list(resource_pool.operators_by_machine.get(machine_id)))
    return _unique_text_tuple(candidates)


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


def _optional_due_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return _optional_text(value)


def _raw_snapshot(row: Any) -> Mapping[str, Any]:
    fields = (
        "id",
        "batch_id",
        "op_code",
        "seq",
        "source",
        "op_type_id",
        "machine_id",
        "operator_id",
        "supplier_id",
        "ext_group_id",
        "ext_merge_mode",
        "merge_context_degraded",
    )
    return {field: _json_snapshot_value(_read_field(row, field)) for field in fields}


def _json_snapshot_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return str(value)


__all__ = ["GraphInputContractError", "build_operation_nodes_from_rows"]
