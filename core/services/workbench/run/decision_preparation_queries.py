"""Paged preparation requirements and actual type events under one archive."""

from typing import Union

from core.models.workbench_run_candidate import reference, reject
from core.services.workbench.facts.decision_metrics import METRIC_VERSION
from core.services.workbench.facts.preparation_projection import preparation_delta

from .decision_impact import filter_options, option_resources
from .decision_queries import parse_page
from .decision_session import decision_read, decision_snapshot_scope

PREPARATION_SORTS = ("sequence", "batch_id", "after_setup_hours", "after_required_hours", "setup_delta_hours")
CHANGEOVER_SORTS = ("next_start", "machine_label", "next_batch_id")
ALLOCATIONS = ("all", "new_schedule", "unplanned", "deferred", "retained", "execution", "completed", "external", "unknown")


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
    machines = option_resources(source, view="full_candidate", kinds=("machine",))
    if section == "preparation":
        for ref in source.scope["operation_refs"]:
            operation = source.facts.tables["BatchOperations"].get(source.facts.operations[ref], {})
            key = operation.get("machine_id")
            saved_ref = source.facts.entity_refs.get(("machine", key)) if type(key) is str else None
            if saved_ref is not None and saved_ref not in machines:
                machines[saved_ref] = {"ref": saved_ref, "label": source.facts.tables["Machines"].get(key, {}).get("name"), "kind": "machine"}
    return {"machines": sorted(machines.values(), key=lambda row: (row["label"] or "", row["ref"])),
            "batches": filter_options(source, "batches")["batches"] if section == "preparation" else []}


def _preparation_matches(source, projection, ref, after_row, filters):
    if filters["batch_ref"] is not None and source.operation_batch_ref(ref) != filters["batch_ref"]:
        return False
    if filters["allocation_state"] != "all" and after_row["allocation_state"] != filters["allocation_state"]:
        return False
    return filters["machine_ref"] is None or projection.matches_machine(ref, filters["machine_ref"])


def _preparation_sort_value(projection, ref, before_row, after_row, sort):
    if sort in ("after_setup_hours", "after_required_hours"):
        return after_row["setup_standard_hours" if sort == "after_setup_hours" else "required_standard_hours"]
    if sort == "setup_delta_hours":
        return preparation_delta(
            {"value": after_row["setup_standard_hours"], "total_count": 1, "covered_operation_refs": [ref]},
            {"value": before_row["setup_standard_hours"], "total_count": 1, "covered_operation_refs": [ref]},
        )["value"]
    labels = projection.label_for(ref)
    return labels["batch_label"] if sort == "batch_id" else labels[sort]


def preparation_details(source, filters, *, page: Union[int, str] = 1, size: Union[int, str] = 20, all_rows=False):
    section = filters["section"]
    if source.selected_ref is None:
        reject("invalid_input", "请选择已产出的候选方案后查看明细。", 422)
    options = preparation_options(source, section)
    if filters.get("batch_ref") is not None and filters["batch_ref"] not in source.scope["batch_refs"]:
        reject("entity_not_found", "所选批次不在这次排产归档的受理范围。", 404)
    if filters["machine_ref"] is not None and filters["machine_ref"] not in {row["ref"] for row in options["machines"]}:
        reject("entity_not_found", "所选设备不在这次排产归档的安排与需求范围。", 404)
    page, size = parse_page(page), parse_page(size, size=True)
    offset = (page - 1) * size
    if section == "preparation":
        projection = source.preparation
        before, after = projection.rows_by_ref("reference"), projection.rows_by_ref(source.selected_ref)
        refs = list(source.scope["operation_refs"])
        if filters["work_scope"] == "remaining":
            remaining = source.completion.remaining_operation_refs(source.selected_ref)
            refs = [ref for ref in refs if ref in remaining]
        refs = [ref for ref in refs if _preparation_matches(source, projection, ref, after[ref], filters)]
        ordered, unknown = [], []
        for ref in sorted(refs):
            value = _preparation_sort_value(projection, ref, before[ref], after[ref], filters["sort"])
            if value is None:
                unknown.append(ref)
            else:
                ordered.append((value, ref))
        ordered.sort(key=lambda pair: pair[0], reverse=filters["order"] == "desc")
        sorted_refs = [pair[1] for pair in ordered] + unknown
        total = len(sorted_refs)
        page_refs = sorted_refs if all_rows else sorted_refs[offset:offset + size]
        items = projection.impacts(page_refs)
    else:
        projection = source.changeovers
        items, total = projection.paged_impacts(filters, offset=offset, size=size, all_rows=all_rows)
    return {"run_ref": source.run["run_ref"], "scope": source.scope, "baseline": source.baseline,
            "candidate": {"candidate_ref": source.selected_ref, "label": source.selected["artifact"].get("label")},
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
