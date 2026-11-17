"""Paged preparation requirements and actual type events under one archive."""

from typing import Union

from core.models.content import read_stored_json
from core.models.workbench_run_candidate import local_time, reference, reject
from core.services.workbench.facts.decision_metrics import METRIC_VERSION
from core.services.workbench.facts.preparation_projection import preparation_delta

from .decision_impact import drill_target
from .decision_queries import parse_page, saved_filter_options, saved_option_resources, us_bounds
from .decision_session import decision_read, decision_snapshot_scope

PREPARATION_SORTS = ("sequence", "batch_id", "after_setup_hours", "after_required_hours", "setup_delta_hours")
CHANGEOVER_SORTS = ("next_start", "machine_label", "next_batch_id")
ALLOCATIONS = ("all", "new_schedule", "unplanned", "deferred", "retained", "execution", "completed", "external", "unknown")
_PREP_HOURS = ("setup_standard_hours", "processing_standard_hours", "required_standard_hours")
_PREP_ARR_FIELDS = ("row_ref", "start", "end", "machine", "operator", "source")


def normalize_preparation_filters(section, *, batch_ref=None, machine_ref=None, allocation_state="all", work_scope="all", event_side="all", sort=None, order="asc"):
    if section not in ("preparation", "changeovers"):
        reject("invalid_input", "请选择准备需求或工种切换明细。", 422)
    sorts = PREPARATION_SORTS if section == "preparation" else CHANGEOVER_SORTS
    sort = sort or sorts[0]
    if sort not in sorts or order not in ("asc", "desc") or allocation_state not in ALLOCATIONS or work_scope not in ("all", "remaining") or event_side not in ("all", "selected", "reference"):
        reject("invalid_input", "准备与切换筛选或排序条件无效，请重新选择。", 422)
    if section == "preparation" and event_side != "all" or section == "changeovers" and (batch_ref is not None or allocation_state != "all" or work_scope != "all"):
        reject("invalid_input", "筛选条件不适用于当前准备与切换页签。", 422)
    for value in (batch_ref, machine_ref):
        if value is not None:
            reference(value)
    result = {"section": section, "machine_ref": machine_ref, "sort": sort, "order": order}
    result.update({"batch_ref": batch_ref, "allocation_state": allocation_state, "work_scope": work_scope} if section == "preparation" else {"event_side": event_side})
    return result


def preparation_options(source, section):
    machines = saved_option_resources(source, view="full_candidate", kinds=("machine",))
    if section == "preparation":
        for row in source.repo.saved_catalog_machines(source.run["run_ref"]):
            if row["ref"] not in machines:
                machines[row["ref"]] = {"ref": row["ref"], "label": row["label"], "kind": "machine"}
    batches = saved_filter_options(source, "batches")["batches"] if section == "preparation" else []
    return {"machines": sorted(machines.values(), key=lambda row: (row["label"] or "", row["ref"])), "batches": batches}


def _prep_side(prep, arr_obj, saved_machine, *, formal: bool):
    task = arr_obj["segment"] if arr_obj is not None else None
    if task is not None:
        machine = task["machine"] if task["machine"] is not None and task["machine"]["ref"] is not None else None
        basis = "saved_arrangement"
    else:
        machine = None if formal else saved_machine
        basis = "admission_requirement" if machine is not None else None
    return {
        **prep,
        "machine": machine,
        "machine_basis": basis,
        "arrangement": {field: task[field] for field in _PREP_ARR_FIELDS} if task is not None else None,
    }


def _materialize_prep_row(source, row, window_bounds):
    cat = read_stored_json(row["label_json"], dict)
    ref = cat["operation_ref"]
    b_arr = read_stored_json(row["b_arr_json"], dict) if row["b_arr_json"] is not None else None
    a_arr = read_stored_json(row["a_arr_json"], dict) if row["a_arr_json"] is not None else None
    previous = _prep_side(read_stored_json(row["b_prep_json"], dict), b_arr, cat["saved_machine"],
                          formal=source.comparison_mode == "admission_official")
    selected = _prep_side(read_stored_json(row["a_prep_json"], dict), a_arr, cat["saved_machine"], formal=False)
    deltas = {
        field: preparation_delta(
            {"value": selected[field], "total_count": 1, "covered_operation_refs": [ref]},
            {"value": previous[field], "total_count": 1, "covered_operation_refs": [ref]},
        )
        for field in _PREP_HOURS
    }
    sel_drill = drill_target(source, tasks=(), batch_ref=cat["batch_ref"], operation_ref=ref,
                             window_bounds=window_bounds,
                             task_bounds=us_bounds(a_arr["bounds_us"]) if a_arr is not None else None)
    ref_drill = drill_target(source, tasks=(), batch_ref=cat["batch_ref"], operation_ref=ref, before=True,
                             window_bounds=window_bounds,
                             task_bounds=us_bounds(b_arr["bounds_us"]) if b_arr is not None else None)
    for drill in (sel_drill, ref_drill):
        if drill is not None:
            drill.update(resource_view=source.resource_view, comparison_tab="preparation")
    return {
        **{field: cat[field] for field in ("operation_ref", "batch_ref", "batch_label", "part_label", "sequence", "process_label", "piece_id")},
        "batch_id": cat["batch_label"], "before": previous, "after": selected, "deltas": deltas,
        "data_gaps": cat["data_gaps"], "drill": {"selected": sel_drill, "reference": ref_drill},
    }


def preparation_details(source, filters, *, page: Union[int, str] = 1, size: Union[int, str] = 20, all_rows=False):
    section = filters["section"]
    if source.selected_ref is None:
        reject("invalid_input", "请选择已产出的候选方案后查看明细。", 422)
    options = preparation_options(source, section)
    if section == "preparation" and filters["batch_ref"] is not None and filters["batch_ref"] not in source.batch_refs:
        reject("entity_not_found", "所选批次不在这次排产归档的受理范围。", 404)
    if filters["machine_ref"] is not None and filters["machine_ref"] not in {row["ref"] for row in options["machines"]}:
        reject("entity_not_found", "所选设备不在这次排产归档的安排与需求范围。", 404)
    page, size = parse_page(page), parse_page(size, size=True)
    offset = (page - 1) * size
    if section == "preparation":
        projection = source.preparation
        rows, total = source.repo.page_preparation_operations(
            source.run["run_ref"], source.side_key("reference"), source.selected_ref,
            filters=filters, offset=offset, limit=size, all_rows=all_rows,
        )
        window_bounds = (local_time(source.scope["range_start"]), local_time(source.scope["range_end"]))
        items = [_materialize_prep_row(source, row, window_bounds) for row in rows]
    else:
        projection = source.changeovers
        items, total = projection.paged_impacts(filters, offset=offset, size=size, all_rows=all_rows)
    return {"run_ref": source.run["run_ref"], "scope": source.scope, "baseline": source.baseline,
            "candidate": {"candidate_ref": source.selected_ref, "label": source.selected["label"]},
            "filters": filters, "filter_options": options, "items": items,
            "page": {"number": page, "size": size, "total": total, "has_more": offset + size < total},
            "summary": projection.public_summary(), "metric_version": METRIC_VERSION}


def read_preparation_details(conn, run_ref, section, *, bind_snapshot, selected_candidate_ref=None, batch_ref=None,
                             machine_ref=None, allocation_state="all", work_scope="all", event_side="all", sort=None,
                             order="asc", page: Union[int, str] = 1, size: Union[int, str] = 20, **query):
    if selected_candidate_ref is None:
        reject("invalid_input", "明细需要指定所选候选方案。", 422)
    filters = normalize_preparation_filters(section, batch_ref=batch_ref, machine_ref=machine_ref, allocation_state=allocation_state,
                                            work_scope=work_scope, event_side=event_side, sort=sort, order=order)
    with decision_read(conn, run_ref, selected_candidate_ref=selected_candidate_ref, **query) as source:
        snapshot = bind_snapshot(decision_snapshot_scope(source, filters=filters), source.state())
        return preparation_details(source, filters, page=page, size=size), snapshot
