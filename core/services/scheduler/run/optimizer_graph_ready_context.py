from __future__ import annotations

from typing import Any, Dict, List, NoReturn, Optional, cast

from core.infrastructure.errors import ValidationError
from core.shared.strict_parse import parse_required_int

from .optimizer_graph_ready_profiles import GRAPH_READY_REQUIRED_CONTEXT_FIELDS, finite_number


def validate_graph_ready_context(
    graph_ready_context: Any,
    *,
    algo_ops_to_schedule: List[Any],
    seed_sr_list: Optional[List[Any]] = None,
) -> None:
    if not isinstance(graph_ready_context, dict) or not graph_ready_context.get("enabled"):
        _raise("图 ready 候选缺少可用图上下文。", "graph_ready_unavailable")
    for field in GRAPH_READY_REQUIRED_CONTEXT_FIELDS:
        if field not in graph_ready_context:
            _raise(f"图 ready 候选缺少字段：{field}", _missing_reason(field))

    schedulable_ids = _op_id_set(graph_ready_context.get("schedulable_op_ids"), field="schedulable_op_ids")
    fixed_ids = _op_id_set(graph_ready_context.get("fixed_op_ids"), field="fixed_op_ids")
    _validate_schedulable_ids(schedulable_ids, fixed_ids, algo_ops_to_schedule=algo_ops_to_schedule)
    _validate_fixed_sources(graph_ready_context, fixed_ids=fixed_ids, seed_sr_list=seed_sr_list)

    known_ids = set(schedulable_ids).union(fixed_ids)
    predecessor_map = _link_map(graph_ready_context.get("predecessor_op_ids_by_op_id"), field="predecessor_op_ids_by_op_id")
    successor_map = _link_map(graph_ready_context.get("successor_op_ids_by_op_id"), field="successor_op_ids_by_op_id")
    _complete_link_maps(predecessor_map, successor_map, known_ids=known_ids)
    _validate_link_scope(predecessor_map, known_ids=known_ids, reason="graph_ready_predecessor_out_of_scope")
    _validate_link_scope(successor_map, known_ids=known_ids, reason="graph_ready_successor_out_of_scope")
    _validate_bidirectional_links(predecessor_map, successor_map)
    _detect_cycle(schedulable_ids=schedulable_ids, predecessor_map=predecessor_map)
    _validate_sort_keys(graph_ready_context.get("sort_key_by_op_id"), schedulable_ids=schedulable_ids)
    _validate_priority_keys(graph_ready_context.get("graph_priority_key_by_op_id"), schedulable_ids=schedulable_ids)


def graph_node_metrics_by_op_id(graph_ready_context: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    value = graph_ready_context.get("node_metrics_by_op_id")
    if not isinstance(value, dict):
        _raise("图 ready 候选缺少 node_metrics_by_op_id，无法按多组图权重重新评分。", "graph_ready_missing_node_metrics")
    schedulable_ids = _op_id_set(graph_ready_context.get("schedulable_op_ids"), field="schedulable_op_ids")
    out: Dict[int, Dict[str, Any]] = {}
    for op_id in sorted(schedulable_ids):
        metric = value.get(op_id)
        if not isinstance(metric, dict):
            _raise(f"图 ready 候选缺少待排工序 {op_id} 的图指标。", "graph_ready_missing_node_metrics")
        out[op_id] = dict(cast(Dict[str, Any], metric))
    return out


def bool_metric(metric: Dict[str, Any], field: str) -> bool:
    value = metric.get(field)
    if not isinstance(value, bool):
        _raise(f"图指标 {field} 必须是 bool。", "graph_ready_bad_node_metrics")
    return bool(value)


def non_negative_number(value: Any, *, field: str) -> float:
    number = finite_number(value, field=field)
    if number < 0:
        _raise(f"图指标 {field} 必须是非负数。", "graph_ready_bad_node_metrics")
    return float(number)


def required_non_negative_number(metric: Dict[str, Any], *, field: str) -> float:
    if field not in metric:
        _raise(f"图指标缺少 {field}。", "graph_ready_missing_node_metrics")
    return non_negative_number(metric.get(field), field=field)


def optional_non_negative_number(value: Any, *, field: str) -> Optional[float]:
    if value is None:
        return None
    return non_negative_number(value, field=field)


def reason_from_validation(exc: ValidationError) -> str:
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        reason = str(details.get("reason") or "").strip()
        if reason:
            return reason
    return "graph_ready_candidate_rejected"


def _validate_schedulable_ids(schedulable_ids: set, fixed_ids: set, *, algo_ops_to_schedule: List[Any]) -> None:
    if schedulable_ids.intersection(fixed_ids):
        _raise("图 ready 候选的待排工序和固定工序有重叠。", "graph_ready_schedulable_fixed_overlap")
    expected_ids = {_positive_op_id(getattr(op, "id", None), field="id") for op in list(algo_ops_to_schedule or [])}
    if schedulable_ids != expected_ids:
        _raise("图 ready 候选的待排工序和本次输入不一致。", "graph_ready_schedulable_mismatch")


def _validate_fixed_sources(graph_ready_context: Dict[str, Any], *, fixed_ids: set, seed_sr_list: Optional[List[Any]]) -> None:
    sources = graph_ready_context.get("fixed_op_sources_by_op_id")
    if sources is None:
        return
    if not isinstance(sources, dict):
        _raise("图 ready 候选固定工序来源必须是映射。", "graph_ready_bad_fixed_sources")
    source_ids = {_positive_op_id(raw_id, field="fixed_op_sources_by_op_id") for raw_id in sources}
    if source_ids != set(fixed_ids):
        _raise("图 ready 候选固定工序来源和固定工序集合不一致。", "graph_ready_fixed_source_mismatch")
    seed_ids = {_positive_op_id(getattr(item, "op_id", None), field="seed_results") for item in list(seed_sr_list or [])}
    for op_id in seed_ids:
        if op_id not in fixed_ids:
            _raise("图 ready 候选没有把种子工序标为固定。", "graph_ready_seed_fixed_mismatch")


def _complete_link_maps(predecessor_map: Dict[int, set], successor_map: Dict[int, set], *, known_ids: set) -> None:
    for op_id in known_ids:
        predecessor_map.setdefault(op_id, set())
        successor_map.setdefault(op_id, set())


def _validate_bidirectional_links(predecessor_map: Dict[int, set], successor_map: Dict[int, set]) -> None:
    for op_id, predecessors in predecessor_map.items():
        for predecessor_id in predecessors:
            if op_id not in successor_map.get(predecessor_id, set()):
                _raise("图 ready 候选前后继映射不一致。", "graph_ready_link_mismatch")
    for op_id, successors in successor_map.items():
        for successor_id in successors:
            if op_id not in predecessor_map.get(successor_id, set()):
                _raise("图 ready 候选前后继映射不一致。", "graph_ready_link_mismatch")


def _detect_cycle(*, schedulable_ids: set, predecessor_map: Dict[int, set]) -> None:
    remaining = {op_id: {pre for pre in predecessor_map.get(op_id, set()) if pre in schedulable_ids} for op_id in schedulable_ids}
    ready = [op_id for op_id, predecessors in remaining.items() if not predecessors]
    visited = set()
    while ready:
        current = ready.pop()
        if current in visited:
            continue
        visited.add(current)
        _release_successors(current, remaining=remaining, ready=ready, visited=visited)
    if visited != set(schedulable_ids):
        _raise("图 ready 候选包含环形前后置关系。", "graph_ready_cycle_detected")


def _release_successors(current: int, *, remaining: Dict[int, set], ready: List[int], visited: set) -> None:
    for op_id, predecessors in remaining.items():
        if current not in predecessors:
            continue
        predecessors.discard(current)
        if not predecessors and op_id not in visited:
            ready.append(op_id)


def _validate_sort_keys(value: Any, *, schedulable_ids: set) -> None:
    if not isinstance(value, dict):
        _raise("图 ready 候选缺少 sort_key_by_op_id。", "graph_ready_missing_sort_key")
    _validate_exact_key_set(value, schedulable_ids=schedulable_ids, reason="graph_ready_bad_sort_key")
    for op_id in sorted(schedulable_ids):
        raw = value.get(op_id)
        if not isinstance(raw, tuple) or len(raw) != 3:
            _raise("图 ready 候选 sort_key_by_op_id 必须是三元组。", "graph_ready_bad_sort_key")
        for item in raw:
            parse_required_int(item, field="sort_key_by_op_id")


def _validate_priority_keys(value: Any, *, schedulable_ids: set) -> None:
    if not isinstance(value, dict):
        _raise("图 ready 候选缺少 graph_priority_key_by_op_id。", "graph_ready_missing_priority_key")
    _validate_exact_key_set(value, schedulable_ids=schedulable_ids, reason="graph_ready_bad_priority_key")
    for op_id in sorted(schedulable_ids):
        values = _priority_key_tuple(value.get(op_id))
        if not values:
            _raise("图 ready 候选 graph_priority_key_by_op_id 不能为空。", "graph_ready_bad_priority_key")


def _priority_key_tuple(value: Any) -> tuple:
    if value is None or isinstance(value, (str, bytes)):
        _raise("图 ready 候选 graph_priority_key_by_op_id 必须是数字 tuple。", "graph_ready_bad_priority_key")
    try:
        return tuple(finite_number(item, field="graph_priority_key_by_op_id") for item in value)
    except TypeError as exc:
        raise ValidationError(
            "图 ready 候选 graph_priority_key_by_op_id 必须是数字 tuple。",
            field="graph_ready_context",
            details={"reason": "graph_ready_bad_priority_key"},
        ) from exc


def _validate_exact_key_set(value: Dict[Any, Any], *, schedulable_ids: set, reason: str) -> None:
    actual_ids = {_positive_op_id(raw_id, field="graph_ready_context") for raw_id in value}
    if actual_ids != set(schedulable_ids):
        _raise("图 ready 候选 key 集合必须和待排工序完全一致。", reason)


def _op_id_set(value: Any, *, field: str) -> set:
    if value is None or isinstance(value, (str, bytes)):
        _raise(f"图 ready 候选字段 {field} 必须是 op_id 集合。", _missing_reason(field))
    try:
        ids = [_positive_op_id(item, field=field) for item in value]
    except TypeError as exc:
        raise ValidationError(f"图 ready 候选字段 {field} 必须是 op_id 集合。", field="graph_ready_context", details={"reason": _missing_reason(field)}) from exc
    if len(ids) != len(set(ids)):
        _raise(f"图 ready 候选字段 {field} 不能有重复 op_id。", "graph_ready_duplicate_op_id")
    return set(ids)


def _link_map(value: Any, *, field: str) -> Dict[int, set]:
    if not isinstance(value, dict):
        _raise(f"图 ready 候选字段 {field} 必须是映射。", _missing_reason(field))
    out: Dict[int, set] = {}
    for raw_op_id, raw_links in value.items():
        op_id = _positive_op_id(raw_op_id, field=field)
        if raw_links is None or isinstance(raw_links, (str, bytes)):
            _raise(f"图 ready 候选字段 {field} 的值必须是 op_id 集合。", _missing_reason(field))
        try:
            out[op_id] = {_positive_op_id(item, field=field) for item in raw_links}
        except TypeError as exc:
            raise ValidationError(f"图 ready 候选字段 {field} 的值必须是 op_id 集合。", field="graph_ready_context", details={"reason": _missing_reason(field)}) from exc
    return out


def _validate_link_scope(link_map: Dict[int, set], *, known_ids: set, reason: str) -> None:
    for op_id, linked_ids in link_map.items():
        if op_id not in known_ids:
            _raise("图 ready 候选包含范围外工序。", reason)
        for linked_id in linked_ids:
            if linked_id not in known_ids:
                _raise("图 ready 候选包含范围外工序关系。", reason)


def _positive_op_id(value: Any, *, field: str) -> int:
    return parse_required_int(value, field=field, min_value=1)


def _missing_reason(field: str) -> str:
    return {
        "schedulable_op_ids": "graph_ready_missing_schedulable_ops",
        "fixed_op_ids": "graph_ready_missing_fixed_ops",
        "predecessor_op_ids_by_op_id": "graph_ready_missing_predecessors",
        "successor_op_ids_by_op_id": "graph_ready_missing_successors",
        "sort_key_by_op_id": "graph_ready_missing_sort_key",
        "graph_priority_key_by_op_id": "graph_ready_missing_priority_key",
    }.get(str(field), "graph_ready_context_invalid")


def _raise(message: str, reason: str) -> NoReturn:
    raise ValidationError(message, field="graph_ready_context", details={"reason": reason})
