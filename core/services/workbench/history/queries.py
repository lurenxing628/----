"""One read-only history snapshot with SQL pagination and on-demand pair reads."""

from core.models.workbench_decision_history import (
    HISTORY_VERSION,
    MAX_HISTORY_EXPORT_ROWS,
    history_snapshot_scope,
    normalize_history_query,
    reject_history,
)
from core.services.workbench.facts.decision_metrics import metric_definitions
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.history_entries.catalog import read_history_entries_page, read_history_snapshot_context

from .metric_gate import COVERAGE_FIELDS, gate_history_metric
from .projection import (
    comparison_conclusion,
    condition_pair,
    configuration_pair,
    project_entry,
    reason,
    trend_projection,
    window_comparable,
)
from .reading import HistoryReader


def _anchor_descriptor(anchors, reference):
    if reference is None:
        return None
    value = anchors.get(reference)
    if value is None:
        reject_history("所选历史条目或基准运行已不存在，请刷新历史。", "entity_not_found", 404)
    return value


def _read(conn, values, *, all_rows, section=None, bind_snapshot=None):
    query = normalize_history_query(values)
    definitions = metric_definitions()
    by_metric = {row["key"]: row for row in definitions}
    if set(query["metric_keys"]) - set(by_metric):
        reject_history("指标列表含目录外项目，请从历史指标目录重新选择。")
    selected_ref = query["selected_entry_ref"]
    reference_ref = "run:" + query["reference_run_ref"] if query["reference_run_ref"] else None
    anchor_refs = [ref for ref in (selected_ref, reference_ref) if ref is not None]
    need_entries = section in (None, "entries")
    need_comparison = section in (None, "conditions", "configurations")
    with candidate_read_snapshot(conn):
        totals, state, anchors = read_history_snapshot_context(conn, query, anchor_refs)
        if all_rows and need_entries and totals["filtered"] > MAX_HISTORY_EXPORT_ROWS:
            reject_history("筛选出的历史超过 " + str(MAX_HISTORY_EXPORT_ROWS) + " 条，没有开始下载。请缩小日期或状态范围后再导出。",
                           "history_capacity_exceeded", 413)
        selected_descriptor = _anchor_descriptor(anchors, selected_ref)
        reference_descriptor = _anchor_descriptor(anchors, reference_ref)
        reader, projected, pairs = HistoryReader(conn), {}, {}
        state["source_anchors"] = [
            reader.source_state(descriptor)
            for descriptor in (selected_descriptor, reference_descriptor)
            if descriptor is not None
        ]
        scope = history_snapshot_scope(query)
        snapshot = bind_snapshot(scope, state) if bind_snapshot is not None else scope

        page_rows = read_history_entries_page(conn, query, all_rows=all_rows) if need_entries else []
        start = (query["page"] - 1) * query["size"]
        filtered_total = totals["filtered"]
        page = {
            "number": query["page"],
            "size": query["size"],
            "total": filtered_total,
            "has_more": False if all_rows else start + query["size"] < filtered_total,
        }
        descriptors = {**anchors, **{row["entry_ref"]: row for row in page_rows}}

        def entry(descriptor):
            if descriptor is None:
                return None
            key = descriptor["entry_ref"]
            if key not in projected:
                projected[key] = project_entry(reader, descriptor, query)
            return projected[key]

        entries = [entry(row) for row in page_rows] if need_entries else []
        if section is None:
            selected, reference = entry(selected_descriptor), entry(reference_descriptor)
        elif need_comparison:
            selected = {"entry_ref": selected_descriptor["entry_ref"]} if selected_descriptor is not None else None
            reference = {"entry_ref": reference_descriptor["entry_ref"]} if reference_descriptor is not None else None
        else:
            selected, reference = None, None
        if need_comparison:
            if section == "configurations":
                pair = configuration_pair(reader, reference_descriptor, selected_descriptor)
            else:
                pair = condition_pair(
                    reader,
                    reference_descriptor,
                    selected_descriptor,
                    selected if section is None else None,
                    query,
                    pairs,
                    include_rows=True,
                    include_configurations=section is None,
                    all_rows=all_rows,
                )
            conditions = pair["conditions"]
            has_pair = selected is not None and reference is not None
            deltas = {}
            if section is None:
                for key in query["metric_keys"]:
                    if selected is not None and reference is not None:
                        deltas[key] = gate_history_metric(
                            by_metric[key],
                            reference["metrics"][key],
                            selected["metrics"][key],
                            production_state=pair["conditions"]["state"],
                            objective_state=pair["objective"]["state"],
                            window_comparable=window_comparable(reference, selected, by_metric[key]),
                        )
                    else:
                        deltas[key] = {
                            "value": None,
                            "state": "unavailable",
                            "direction": "neutral",
                            "reference_value": reference["metrics"][key]["value"] if reference else None,
                            "selected_value": selected["metrics"][key]["value"] if selected else None,
                            "reason": reason("history_pair_required", "比较指标需要实际历史条目和明确基准运行。"),
                        }
            conclusion = (
                comparison_conclusion(query["comparison"], pair, deltas, has_pair)
                if section is None or not has_pair
                else None
            )
            comparison = {
                "mode": query["comparison"],
                "conditions": conditions,
                "configurations": pair["configurations"],
                "objective": pair["objective"],
                "metric_deltas": deltas,
                "conclusion": conclusion,
            }
        else:
            comparison = None
        trend = (
            {"point_scope": "current_page", "order": "asc", "points": []}
            if all_rows
            else trend_projection(
                reader, entries, descriptors, reference, reference_descriptor, query, by_metric, pairs
            )
        )
        absolute = query["range_start"] is not None
        policy = {
            "mode": "absolute" if absolute else "fixed_days",
            "start": query["range_start"],
            "end": query["range_end"],
            "days": None if absolute else query["resource_window_days"],
            "anchor": "common_absolute_window" if absolute else "source_start",
            "time_basis": "factory_local",
            "boundary": "half_open",
        }
        data = {
            "history_version": HISTORY_VERSION,
            "filters": {key: value for key, value in query.items() if key != "snapshot_ref"},
            "entries": entries,
            "page": page,
            "totals": totals,
            "metric_definitions": definitions,
            "selection": {"entry": selected, "reference": reference},
            "comparison": comparison,
            "trend": trend,
            "resource_window": policy,
        }
        return data, snapshot, state


def _public_metric(item):
    return {key: value for key, value in item.items() if key not in COVERAGE_FIELDS}


def _public_scope(scope):
    return {
        **{key: value for key, value in scope.items() if key not in ("batch_refs", "operation_refs")},
        "batch_quantity": _public_metric(scope["batch_quantity"]),
    }


def _public_resource_window(window):
    cohort = window["cohort"]
    return {
        **window,
        "cohort": {
            "machine_count": len(cohort["machine_refs"]) if cohort["machine_refs"] is not None else None,
            "operator_count": len(cohort["operator_refs"]) if cohort["operator_refs"] is not None else None,
        },
    }


def _public_entry(item):
    if item is None:
        return None
    return {
        **item,
        "metrics": {key: _public_metric(value) for key, value in item["metrics"].items()},
        "scope": _public_scope(item["scope"]),
        "reading_context": {
            **item["reading_context"],
            "resource_window": _public_resource_window(item["reading_context"]["resource_window"]),
        },
    }


def _public_trend_point(point):
    return {
        **point,
        "metrics": {key: _public_metric(value) for key, value in point["metrics"].items()},
        "scope": _public_scope(point["scope"]),
        "resource_window": _public_resource_window(point["resource_window"]),
    }


def read_decision_history(conn, query, *, bind_snapshot=None):
    data, snapshot, state = _read(conn, query, all_rows=False, bind_snapshot=bind_snapshot)
    data = {
        **data,
        "entries": [_public_entry(row) for row in data["entries"]],
        "selection": {
            "entry": _public_entry(data["selection"]["entry"]),
            "reference": _public_entry(data["selection"]["reference"]),
        },
        "trend": {
            **data["trend"],
            "points": [_public_trend_point(point) for point in data["trend"]["points"]],
        },
    }
    return data, snapshot, state


def read_history_all(conn, query, *, section=None, bind_snapshot=None):
    return _read(conn, query, all_rows=True, section=section, bind_snapshot=bind_snapshot)
