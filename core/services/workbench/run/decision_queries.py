"""Filtering and stable SQL pagination over the decision's complete frozen impacts."""

from typing import Union

from core.models.content import read_stored_json
from core.models.workbench_run_candidate import local_time, reference, reject
from core.services.workbench.facts.candidate_tasks import unplanned_reason
from core.services.workbench.facts.common_completed_delivery import common_completed_delivery
from core.services.workbench.facts.decision_metrics import METRIC_VERSION
from core.services.workbench.facts.delivery_projection import delivery_summary
from core.shared.local_datetime import us_to_datetime
from core.shared.strict_parse import JS_SAFE_INT_MAX, parse_bounded_positive_int

from .decision import operation_change_metrics_from_sql
from .decision_impact import (
    BATCH_CHANGES,
    BATCH_SORTS,
    DELIVERY_FILTERS,
    OPERATION_CHANGES,
    OPERATION_SORTS,
    drill_target,
    operation_delta,
)
from .decision_session import decision_read, decision_snapshot_scope


def normalize_filters(section, *, batch_ref=None, resource_ref=None, change_kind="all", sort=None, order=None,
                      delivery_filter="all", selected_batch_ref=None):
    if section not in ("batches", "operations"):
        reject("invalid_input", "请选择批次交付或工序变化明细。", 422)
    changes = BATCH_CHANGES if section == "batches" else OPERATION_CHANGES
    sorts = BATCH_SORTS if section == "batches" else OPERATION_SORTS
    sort = sort or ("worsened" if section == "batches" else "sequence")
    order = order or ("asc" if sort == "current_priority" else "desc" if section == "batches" else "asc")
    if change_kind not in changes or sort not in sorts or order not in ("asc", "desc"):
        reject("invalid_input", "明细的变化类型或排序条件无效，请重新选择。", 422)
    if section == "batches" and resource_ref is not None:
        reject("invalid_input", "资源筛选用于工序变化明细，请切换明细页签。", 422)
    if delivery_filter not in DELIVERY_FILTERS or section != "batches" and (delivery_filter != "all" or selected_batch_ref is not None):
        reject("invalid_input", "当前交付筛选和保留批次用于批次交付明细。", 422)
    for ref in (batch_ref, resource_ref, selected_batch_ref):
        if ref is not None:
            reference(ref)
    return {"section": section, "batch_ref": batch_ref, "resource_ref": resource_ref, "change_kind": change_kind,
            "sort": sort, "order": order, "delivery_filter": delivery_filter, "selected_batch_ref": selected_batch_ref}


def parse_page(value, *, size=False):
    parsed = parse_bounded_positive_int(value, max_value=JS_SAFE_INT_MAX)
    if parsed is None or (size and parsed not in (20, 50)):
        reject("invalid_input", "页码需要为正整数，每页请选择20或50条。" if size else "分页页码和每页数量需要填写正整数。", 422)
    return parsed


def saved_option_resources(source, *, view="selected_batches", kinds=("machine", "operator")):
    resources = {}
    if source.comparison_mode == "admission_official":
        for row in source.official["resource_views"][view]["arranged_resources"]:
            if row["kind"] in kinds and row["ref"] is not None:
                resources[row["ref"]] = {"ref": row["ref"], "label": row["label"], "kind": row["kind"]}
    for candidate in source.rows:
        view_data = source._candidate_models[candidate["candidate_ref"]]["summary"]["resource_views"][view]
        for row in view_data["arranged_resources"]:
            if row["kind"] in kinds and row["ref"] is not None:
                resources[row["ref"]] = {"ref": row["ref"], "label": row["label"], "kind": row["kind"]}
    return resources


def saved_filter_options(source, section):
    delivery_rows = {row["batch_ref"]: row["batch_id"] for row in source.completion.delivery(source.selected_ref)}
    batches = [{"ref": ref, "label": delivery_rows[ref]} for ref in source.batch_refs]
    resources = saved_option_resources(source, view="selected_batches", kinds=("machine", "operator")) if section == "operations" else {}
    return {"batches": batches, "resources": sorted(resources.values(), key=lambda item: (item["kind"], item["label"] or "", item["ref"]))}


def us_bounds(pair):
    return (us_to_datetime(pair[0]), us_to_datetime(pair[1])) if pair is not None else None


def _saved_batch_summary(source):
    before = source.completion.delivery("reference")
    after = source.completion.delivery(source.selected_ref)
    common = common_completed_delivery(before, after)
    changes = operation_change_metrics_from_sql(source, source.selected_ref)
    return {"before": delivery_summary(before), "after": delivery_summary(after),
            "common_completed_batch_count": len(common["common_completed_batch_refs"]),
            "common_delivery": common["common_delivery"], "operation_changes": changes}


def _materialize_batch_row(source, row, window_bounds):
    b_det, a_det = read_stored_json(row["b_detail_json"], dict), read_stored_json(row["a_detail_json"], dict)
    previous, current = b_det["delivery"], a_det["delivery"]
    labels = {k: current[k] for k in ("batch_ref", "batch_id", "part_no", "part_label",
                                      "priority", "quantity", "due_date", "due_state", "due_issue")}
    attention = (["overdue"] if current["is_overdue"] is True else []) + (
        ["deferred"] if (current["deferred_operation_count"] or 0) > 0 else []) + (
        ["unplanned"] if (current["ordinary_unscheduled_operation_count"] or 0) > 0 else [])
    op_total, op_changed, op_unknown = row["op_total"], row["op_changed"], row["op_unknown"]
    op_state = "unavailable" if op_total == 0 or op_unknown == op_total else "partial" if op_unknown else "complete"
    drill = {
        "selected": drill_target(source, tasks=(), batch_ref=row["batch_ref"], window_bounds=window_bounds,
                                 task_bounds=us_bounds(a_det["task_bounds_us"])),
        "reference": drill_target(source, tasks=(), batch_ref=row["batch_ref"], before=True, window_bounds=window_bounds,
                                  task_bounds=us_bounds(b_det["task_bounds_us"])),
    }
    return {
        **labels, "before": previous, "after": current,
        "finish_delta_hours": row["finish_delta_hours"], "delay_delta_hours": row["delay_delta_hours"],
        "change_kinds": row["change_kinds_csv"].split(","), "attention_kinds": attention,
        "operation_change_count": op_changed, "operation_unknown_count": op_unknown,
        "operation_changes_state": op_state, "drill": drill,
    }


def _side_state(arrangement, *, available: bool, deferred: bool, disposition=None):
    if not available:
        return {"status": "unavailable", "reason": {"code": "arrangement_source_unavailable", "message": "该来源没有产出可查看的任务安排。"}}
    if arrangement is not None:
        return {"status": "arranged", "reason": None}
    status = "deferred" if deferred else "missing"
    reason = unplanned_reason(disposition) if disposition is not None else {
        "code": "material_deferred" if deferred else "operation_unscheduled",
        "message": "排产时因缺料保留为待料未排。" if deferred else "这份归档没有给该工序安排时间。",
    }
    return {"status": status, "reason": reason}


def _single_interval_map(view, start_us, end_us):
    return {} if view is None else {view["row_ref"]: (us_to_datetime(start_us), us_to_datetime(end_us))}


def _materialize_operation_row(source, row, window_bounds, *, ref_avail: bool):
    cat = read_stored_json(row["label_json"], dict)
    b_arr = read_stored_json(row["b_arr_json"], dict) if row["b_arr_json"] is not None else None
    a_arr = read_stored_json(row["a_arr_json"], dict) if row["a_arr_json"] is not None else None
    before = b_arr["segment"] if b_arr is not None else None
    after = a_arr["segment"] if a_arr is not None else None
    disp = cat["disposition"]
    before_state = _side_state(
        before, available=ref_avail, deferred=bool(row["b_def"]),
        disposition=disp if source.comparison_mode == "candidates" else None,
    )
    after_state = _side_state(after, available=True, deferred=bool(row["a_def"]), disposition=disp)
    if not ref_avail:
        delta = {
            **{k: None for k in ("start_delta_hours", "end_delta_hours", "machine_changed",
                                 "operator_changed", "supplier_changed", "source_changed", "status_changed")},
            "change_kinds": ["unknown"], "changed_fields": [],
        }
    else:
        delta = operation_delta(
            before, after, before_status=before_state["status"], after_status=after_state["status"],
            task_intervals=_single_interval_map(after, row["a_start"], row["a_end"]),
            reference_task_intervals=_single_interval_map(before, row["b_start"], row["b_end"]),
        )
    constraints = {
        "protected_at_admission": disp["status"] == "protected",
        "selected_locked": after["locked"] if after else None,
        "reference_locked": before["locked"] if before else None,
        "lock_basis": "saved_arrangement_marker",
        "protection_basis": "admission_execution_and_dispositions",
        **cat["execution_constraints"],
        "reasons": disp["issues"],
    }
    drill = {
        "selected": drill_target(source, tasks=(), batch_ref=cat["batch_ref"], operation_ref=cat["operation_ref"],
                                 window_bounds=window_bounds,
                                 task_bounds=us_bounds(a_arr["bounds_us"]) if a_arr is not None else None),
        "reference": drill_target(source, tasks=(), batch_ref=cat["batch_ref"], operation_ref=cat["operation_ref"],
                                  before=True, window_bounds=window_bounds,
                                  task_bounds=us_bounds(b_arr["bounds_us"]) if b_arr is not None else None),
    }
    return {
        **{k: cat[k] for k in ("operation_ref", "batch_ref", "batch_label", "part_label",
                               "sequence", "process_label", "piece_id", "quantity")},
        "batch_id": cat["batch_label"], "before": before, "after": after,
        "before_state": before_state, "after_state": after_state, **delta,
        "effort": cat["effort"],
        "runtime_effort": {"before": read_stored_json(row["b_prep_json"], dict), "after": read_stored_json(row["a_prep_json"], dict)},
        "constraints": constraints, "data_gaps": cat["data_gaps"], "drill": drill,
    }


def _sql_paged_details(source, section, filters, *, offset: int, size: int, all_rows: bool):
    run_ref = source.run["run_ref"]
    ref_side, sel_side = source.side_key("reference"), source.selected_ref
    ref_avail = source.arrangement_available("reference")
    window_bounds = (local_time(source.scope["range_start"]), local_time(source.scope["range_end"]))
    summary = _saved_batch_summary(source)
    if section == "batches":
        rows, total, sel_raw = source.repo.page_side_batches(
            run_ref, ref_side, sel_side, ref_avail=ref_avail,
            filters=filters, offset=offset, limit=size, all_rows=all_rows,
            selected_batch_ref=filters["selected_batch_ref"],
        )
        items = [_materialize_batch_row(source, row, window_bounds) for row in rows]
        selected_batch = _materialize_batch_row(source, sel_raw, window_bounds) if sel_raw is not None else None
        return items, total, summary, selected_batch
    rows, total = source.repo.page_side_operations(
        run_ref, ref_side, sel_side, ref_avail=ref_avail,
        filters=filters, offset=offset, limit=size, all_rows=all_rows,
    )
    items = [_materialize_operation_row(source, row, window_bounds, ref_avail=ref_avail) for row in rows]
    return items, total, summary, None


def decision_details(source, section, filters, *, page: Union[int, str] = 1, size: Union[int, str] = 20, all_rows=False):
    if source.selected_ref is None:
        reject("invalid_input", "请选择候选方案后查看明细。", 422)
    options = saved_filter_options(source, section)
    for batch in (filters["batch_ref"], filters["selected_batch_ref"]):
        if batch is not None and batch not in source.batch_refs:
            reject("entity_not_found", "所选批次不在这次排产的归档范围。", 404)
    if filters["resource_ref"] is not None and filters["resource_ref"] not in {item["ref"] for item in options["resources"]}:
        reject("entity_not_found", "所选资源不在这次排产的归档安排。", 404)
    page, size = parse_page(page), parse_page(size, size=True)
    offset = (page - 1) * size
    items, total, summary, selected_batch = _sql_paged_details(
        source, section, filters, offset=offset, size=size, all_rows=all_rows,
    )
    result = {"run_ref": source.run["run_ref"], "scope": source.scope, "baseline": source.baseline,
              "candidate": {"candidate_ref": source.selected_ref, "label": source.selected["label"]},
              "filters": filters, "filter_options": options, "items": items,
              "page": {"number": page, "size": size, "total": total, "has_more": offset + size < total},
              "summary": {**summary, "scope": "full_admission"}, "metric_version": METRIC_VERSION}
    if section == "batches":
        result["selected_batch"] = selected_batch
    return result


def read_decision_details(conn, run_ref, section, *, bind_snapshot, selected_candidate_ref=None, batch_ref=None,
                          resource_ref=None, change_kind="all", sort=None, order=None, delivery_filter="all",
                          selected_batch_ref=None, page: Union[int, str] = 1, size: Union[int, str] = 20, **query):
    if selected_candidate_ref is None:
        reject("invalid_input", "明细需要指定所选候选方案。", 422)
    filters = normalize_filters(section, batch_ref=batch_ref, resource_ref=resource_ref, change_kind=change_kind, sort=sort, order=order,
                                delivery_filter=delivery_filter, selected_batch_ref=selected_batch_ref)
    with decision_read(conn, run_ref, selected_candidate_ref=selected_candidate_ref, **query) as source:
        snapshot = bind_snapshot(decision_snapshot_scope(source, filters=filters), source.state())
        return decision_details(source, section, filters, page=page, size=size), snapshot
