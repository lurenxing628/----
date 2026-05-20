from __future__ import annotations

from typing import Any, Dict, List, Tuple

_GRAPH_WARNING_DATA_LIST_SAMPLE_LIMIT = 20
_GRAPH_WARNING_DATA_DICT_FIELD_LIMIT = 20
_GRAPH_WARNING_TEXT_SAMPLE_LIMIT = 500


def _truncated(values: List[Any], limit: int) -> bool:
    return len(values) > int(limit)


def _sample(values: List[Any], limit: int) -> List[Any]:
    return list(values[: int(limit)])


def _project_warning_data_value(value: Any) -> Tuple[Any, bool]:
    if value is None or isinstance(value, (int, float, bool)):
        return value, False
    if isinstance(value, str):
        if len(value) <= _GRAPH_WARNING_TEXT_SAMPLE_LIMIT:
            return value, False
        return {
            "text_sample": value[:_GRAPH_WARNING_TEXT_SAMPLE_LIMIT],
            "text_length": int(len(value)),
            "text_truncated": True,
        }, True
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        projected_items: List[Any] = []
        truncated_any = _truncated(value, _GRAPH_WARNING_DATA_LIST_SAMPLE_LIMIT)
        for item in _sample(value, _GRAPH_WARNING_DATA_LIST_SAMPLE_LIMIT):
            projected_item, item_truncated = _project_warning_data_value(item)
            projected_items.append(projected_item)
            truncated_any = truncated_any or item_truncated
        return projected_items, truncated_any
    if isinstance(value, dict):
        items = list(value.items())
        projected: Dict[str, Any] = {}
        truncated_any = _truncated(items, _GRAPH_WARNING_DATA_DICT_FIELD_LIMIT)
        for raw_key, raw_value in items[:_GRAPH_WARNING_DATA_DICT_FIELD_LIMIT]:
            projected_value, value_truncated = _project_warning_data_value(raw_value)
            projected[str(raw_key)] = projected_value
            truncated_any = truncated_any or value_truncated
        if len(items) > _GRAPH_WARNING_DATA_DICT_FIELD_LIMIT:
            projected["_field_count"] = int(len(items))
            projected["_fields_truncated"] = True
        return projected, truncated_any
    return {"unsupported_value_type": type(value).__name__}, True


def _project_warning_message(message: Any) -> Tuple[str, bool]:
    text = str(message or "")
    if len(text) <= _GRAPH_WARNING_TEXT_SAMPLE_LIMIT:
        return text, False
    return text[:_GRAPH_WARNING_TEXT_SAMPLE_LIMIT], True


def _project_warning_data(raw_data: Any) -> Tuple[Dict[str, Any], bool]:
    if not isinstance(raw_data, dict):
        return {"unsupported_data_type": type(raw_data).__name__}, True
    projected: Dict[str, Any] = {}
    items = list(raw_data.items())
    truncated_any = _truncated(items, _GRAPH_WARNING_DATA_DICT_FIELD_LIMIT)
    for key, value in items[:_GRAPH_WARNING_DATA_DICT_FIELD_LIMIT]:
        key_text = str(key)
        if isinstance(value, list):
            sample, sample_truncated = _project_warning_data_value(value)
            projected[f"{key_text}_sample"] = sample
            projected[f"{key_text}_count"] = int(len(value))
            truncated = _truncated(value, _GRAPH_WARNING_DATA_LIST_SAMPLE_LIMIT)
            projected[f"{key_text}_truncated"] = bool(truncated or sample_truncated)
            truncated_any = truncated_any or truncated or sample_truncated
        else:
            projected_value, value_truncated = _project_warning_data_value(value)
            projected[key_text] = projected_value
            truncated_any = truncated_any or value_truncated
    if len(items) > _GRAPH_WARNING_DATA_DICT_FIELD_LIMIT:
        projected["_field_count"] = int(len(items))
        projected["_fields_truncated"] = True
    return projected, truncated_any


def project_graph_warning(warning: Dict[str, Any]) -> Dict[str, Any]:
    data, warning_data_truncated = _project_warning_data(warning.get("data"))
    message, message_truncated = _project_warning_message(warning["message"])
    return {
        "code": warning["code"],
        "message": message,
        "message_length": len(str(warning["message"] or "")),
        "message_truncated": bool(message_truncated),
        "data": data,
        "warning_data_truncated": bool(warning_data_truncated or message_truncated),
    }


def graph_node_metrics_sample(
    *,
    node_metrics: Dict[str, Dict[str, Any]],
    topological_order: List[str],
    limit: int,
) -> List[Dict[str, Any]]:
    if topological_order:
        sample_node_ids = topological_order[: int(limit)]
    else:
        sample_node_ids = sorted(node_metrics)[: int(limit)]
    return [
        {
            "node_id": node_id,
            "is_on_critical_path": bool(node_metrics[node_id]["is_on_critical_path"]),
            "critical_path_rank": node_metrics[node_id]["critical_path_rank"],
            "impact_count": int(node_metrics[node_id]["impact_count"]),
            "generation_index": int(node_metrics[node_id]["generation_index"]),
            "downstream_critical_minutes": int(node_metrics[node_id]["downstream_critical_minutes"]),
        }
        for node_id in sample_node_ids
        if node_id in node_metrics
    ]


__all__ = [
    "graph_node_metrics_sample",
    "project_graph_warning",
]
