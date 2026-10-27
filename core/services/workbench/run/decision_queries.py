"""Filtering and stable pagination over the decision's complete frozen impacts."""

from typing import Union

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_run_candidate import reference, reject
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.decision_metrics import METRIC_VERSION

from .decision_impact import (
    BATCH_CHANGES,
    BATCH_SORTS,
    DELIVERY_FILTERS,
    OPERATION_CHANGES,
    OPERATION_SORTS,
    filter_options,
)
from .decision_source import DecisionSource


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
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        reject("invalid_input", "分页页码和每页数量需要填写正整数。", 422)
    if type(value) is bool or str(parsed) != str(value) or parsed < 1 or size and parsed not in (20, 50):
        reject("invalid_input", "页码需要为正整数，每页请选择20或50条。", 422)
    return parsed


def decision_details(source, section, filters, *, page: Union[int, str] = 1, size: Union[int, str] = 20, all_rows=False):
    if source.selected_ref is None:
        reject("invalid_input", "请选择候选方案后查看明细。", 422)
    options = filter_options(source, section)
    for batch in (filters["batch_ref"], filters.get("selected_batch_ref")):
        if batch is not None and batch not in source.scope["batch_refs"]:
            reject("entity_not_found", "所选批次不在这次排产的归档范围。", 404)
    if filters["resource_ref"] is not None and filters["resource_ref"] not in {item["ref"] for item in options["resources"]}:
        reject("entity_not_found", "所选资源不在这次排产的归档安排。", 404)
    if section == "batches":
        batches, summary = source.batch_impacts
        selected_batch = next((row for row in batches if row["batch_ref"] == filters.get("selected_batch_ref")), None)
        rows = batches
    else:
        summary = source.batch_impact_summary
        rows = source.operation_impacts
    rows = [row for row in rows if _matches(row, filters)]
    rows = _ordered(rows, filters)
    page, size = parse_page(page), parse_page(size, size=True)
    offset = (page - 1) * size
    result = {"run_ref": source.run["run_ref"], "scope": source.scope, "baseline": source.baseline,
              "candidate": {"candidate_ref": source.selected_ref, "label": source.selected["artifact"].get("label"),
                            "status": source.selected["status"], "result_available": source.result_available(source.selected_ref)},
              "filters": filters, "filter_options": options, "items": rows if all_rows else rows[offset:offset + size],
              "page": {"number": page, "size": size, "total": len(rows), "has_more": offset + size < len(rows)},
              "summary": {**summary, "scope": "full_admission"}, "metric_version": METRIC_VERSION}
    if section == "batches":
        result["selected_batch"] = selected_batch
    return result


def _matches(row, filters):
    if filters["batch_ref"] is not None and row["batch_ref"] != filters["batch_ref"]:
        return False
    change = filters["change_kind"]
    if change == "changed":
        if not any(kind not in ("unchanged", "unknown") for kind in row["change_kinds"]):
            return False
    elif change != "all" and change not in row["change_kinds"]:
        return False
    delivery = filters.get("delivery_filter", "all")
    if delivery != "all":
        attention = row["attention_kinds"]
        if delivery == "attention" and not attention:
            return False
        if delivery == "on_time" and row["after"]["is_overdue"] is not False:
            return False
        if delivery not in ("attention", "on_time") and delivery not in attention:
            return False
    resource = filters["resource_ref"]
    if resource is not None:
        sides = [segment for side in (row["before"], row["after"]) if side is not None for segment in side.get("segments", [side])]
        if not any((side.get(kind) or {}).get("ref") == resource for side in sides for kind in ("machine", "operator")):
            return False
    return True


def _sort_value(row, sort):
    if sort == "current_priority":
        attention = row["attention_kinds"]
        rank = next((index for index, kind in enumerate(("overdue", "deferred", "unplanned")) if kind in attention), 3)
        return rank, -(row["after"]["delay_hours"] or 0)
    if sort == "after_delay_hours":
        return row["after"]["delay_hours"]
    if sort == "change_kind":
        return ",".join(row["change_kinds"])
    if sort in ("worsened", "improved"):
        changes = set(row["change_kinds"])
        if changes == {"unknown"}:
            return None
        worsening = sort == "worsened"
        rank = ((3 if "completion_worsened" in changes else 2 if "new_overdue" in changes else 1 if "later" in changes else 0)
                if worsening else (3 if "completion_improved" in changes else 2 if "relieved_overdue" in changes else 1 if "earlier" in changes else 0))
        sign = 1 if worsening else -1
        return rank, sign * (row["delay_delta_hours"] or 0), sign * (row["finish_delta_hours"] or 0)
    return row.get(sort)


def _ordered(rows, filters):
    identity = "batch_ref" if filters["section"] == "batches" else "operation_ref"
    known, unknown = [], []
    for row in sorted(rows, key=lambda item: item[identity]):
        value = _sort_value(row, filters["sort"])
        if value is None:
            unknown.append(row)
        else:
            known.append((value, row))
    known.sort(key=lambda pair: pair[0], reverse=filters["order"] == "desc")
    return [pair[1] for pair in known] + unknown


def read_decision_details(conn, run_ref, section, *, selected_candidate_ref=None, comparison_mode="candidates", reference_candidate_ref=None,
                          range_start=None, range_end=None, resource_view="selected_batches", batch_ref=None, resource_ref=None,
                          change_kind="all", sort=None, order=None, delivery_filter="all", selected_batch_ref=None,
                          page: Union[int, str] = 1, size: Union[int, str] = 20):
    if selected_candidate_ref is None:
        reject("invalid_input", "明细需要指定所选候选方案。", 422)
    filters = normalize_filters(section, batch_ref=batch_ref, resource_ref=resource_ref, change_kind=change_kind, sort=sort, order=order,
                                delivery_filter=delivery_filter, selected_batch_ref=selected_batch_ref)
    store = CandidateStore(conn)
    with store.snapshot(), read_evidence_scope(conn):
        source = DecisionSource(store, run_ref, selected_candidate_ref=selected_candidate_ref, comparison_mode=comparison_mode,
                                reference_candidate_ref=reference_candidate_ref, range_start=range_start, range_end=range_end, resource_view=resource_view)
        data = decision_details(source, section, filters, page=page, size=size)
        return data, source.state()
