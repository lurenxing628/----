"""Paged preparation requirements and actual type events under one archive."""

from typing import Union

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_command import canonical_json
from core.models.workbench_run_candidate import MAX_RESPONSE_BYTES, reference, reject
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_values import bounded_size

from .decision_impact import filter_options
from .decision_metrics import METRIC_VERSION
from .decision_queries import _page
from .decision_source import DecisionSource

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
    machines = {}
    before = source.official["tasks"] if source.comparison_mode == "admission_official" else source.before_tasks
    tasks = before + [task for candidate in source.rows for task in source.tasks(candidate["candidate_ref"])]
    for task in tasks:
        machine = task["machine"]
        if machine is not None and machine["ref"] is not None:
            machines[machine["ref"]] = {**machine, "kind": "machine"}
    if section == "preparation":
        for ref in source.scope["operation_refs"]:
            operation = source.facts.tables["BatchOperations"].get(source.facts.operations[ref], {})
            key = operation.get("machine_id")
            saved_ref = source.facts.entity_refs.get(("machine", key)) if type(key) is str else None
            if saved_ref is not None and saved_ref not in machines:
                machines[saved_ref] = {"ref": saved_ref, "label": source.facts.tables["Machines"].get(key, {}).get("name"), "kind": "machine"}
    return {"machines": sorted(machines.values(), key=lambda row: (row["label"] or "", row["ref"])),
            "batches": filter_options(source, "batches")["batches"]}


def preparation_details(source, filters, *, page: Union[int, str] = 1, size: Union[int, str] = 20, all_rows=False):
    section = filters["section"]
    if source.selected_ref is None:
        reject("invalid_input", "请选择已产出的候选方案后查看明细。", 422)
    options = preparation_options(source, section)
    if filters.get("batch_ref") is not None and filters["batch_ref"] not in source.scope["batch_refs"]:
        reject("entity_not_found", "所选批次不在这次排产归档的受理范围。", 404)
    if filters["machine_ref"] is not None and filters["machine_ref"] not in {row["ref"] for row in options["machines"]}:
        reject("entity_not_found", "所选设备不在这次排产归档的安排与需求范围。", 404)
    projection = source.preparation if section == "preparation" else source.changeovers
    rows = projection.impacts()
    if section == "preparation" and filters["work_scope"] == "remaining":
        remaining = source.completion.remaining_operation_refs(source.selected_ref)
        rows = [row for row in rows if row["operation_ref"] in remaining]
    rows = [row for row in rows if _matches(row, filters)]
    identity = "operation_ref" if section == "preparation" else "event_ref"
    ordered, unknown = [], []
    for row in sorted(rows, key=lambda item: item[identity]):
        (unknown if _sort_value(row, filters["sort"]) is None else ordered).append(row)
    ordered.sort(key=lambda item: _sort_value(item, filters["sort"]), reverse=filters["order"] == "desc")
    rows = ordered + unknown
    page, size = _page(page), _page(size, size=True)
    offset = (page - 1) * size
    return {"run_ref": source.run["run_ref"], "scope": source.scope, "baseline": source.baseline,
            "candidate": {"candidate_ref": source.selected_ref, "label": source.selected["artifact"].get("label")},
            "filters": filters, "filter_options": options, "items": rows if all_rows else rows[offset:offset + size],
            "page": {"number": page, "size": size, "total": len(rows), "has_more": offset + size < len(rows)},
            "summary": projection.public_summary(), "metric_version": METRIC_VERSION}


def _matches(row, filters):
    if filters["section"] == "changeovers":
        return ((filters["machine_ref"] is None or row["machine_ref"] == filters["machine_ref"])
                and (filters["event_side"] == "all" or row["event_side"] == filters["event_side"]))
    if filters["batch_ref"] is not None and row["batch_ref"] != filters["batch_ref"]:
        return False
    if filters["allocation_state"] != "all" and row["after"]["allocation_state"] != filters["allocation_state"]:
        return False
    return filters["machine_ref"] is None or any(machine["ref"] == filters["machine_ref"] for side in (row["before"], row["after"]) for machine in side["machines"])


def _sort_value(row, sort):
    if sort in ("after_setup_hours", "after_required_hours"):
        return row["after"]["setup_standard_hours" if sort == "after_setup_hours" else "required_standard_hours"]
    if sort == "setup_delta_hours":
        return row["deltas"]["setup_standard_hours"]["value"]
    if sort == "next_batch_id":
        return row["next"]["batch_label"]
    return row.get(sort)


def read_preparation_details(conn, run_ref, section, *, selected_candidate_ref=None, comparison_mode="candidates", reference_candidate_ref=None,
                             range_start=None, range_end=None, resource_view="selected_batches", batch_ref=None, machine_ref=None,
                             allocation_state="all", work_scope="all", event_side="all", sort=None, order="asc",
                             page: Union[int, str] = 1, size: Union[int, str] = 20):
    if selected_candidate_ref is None:
        reject("invalid_input", "明细需要指定所选候选方案。", 422)
    filters = normalize_preparation_filters(section, batch_ref=batch_ref, machine_ref=machine_ref, allocation_state=allocation_state,
                                            work_scope=work_scope, event_side=event_side, sort=sort, order=order)
    store = CandidateStore(conn)
    with store.snapshot(), read_evidence_scope(conn):
        source = DecisionSource(store, run_ref, selected_candidate_ref=selected_candidate_ref, comparison_mode=comparison_mode,
                                reference_candidate_ref=reference_candidate_ref, range_start=range_start, range_end=range_end, resource_view=resource_view)
        data = preparation_details(source, filters, page=page, size=size)
        bounded_size(len(canonical_json(data).encode("utf-8")), MAX_RESPONSE_BYTES)
        return data, source.state()
