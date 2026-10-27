"""Selectors over one run's saved shared optimization process."""

from typing import Union

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_run_candidate import reference, reject
from core.services.scheduler.run.optimizer.shared_process import UNIFIED_PROCESS_VERSION
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.unified_process import PROCESS_CANDIDATE_FIELDS, project_unified_process

from .decision_queries import parse_page
from .decision_source import DecisionSource


def normalize_process_filters(*, process_candidate_ref=None, objective=None, record_kind="attempts", sort=None, order="asc"):
    sorts = {"attempts": ("rank", "elapsed_ms"), "progress": ("elapsed_ms", "event_index", "primary_value")}
    if record_kind not in sorts:
        reject("invalid_input", "请选择搜索动作或进步事件。", 422)
    sort = sort or sorts[record_kind][0]
    if sort not in sorts[record_kind] or order not in ("asc", "desc"):
        reject("invalid_input", "过程排序条件无效，请重新选择。", 422)
    if process_candidate_ref is not None:
        reference(process_candidate_ref)
    filters = {"section": "process", "process_candidate_ref": process_candidate_ref, "record_kind": record_kind, "sort": sort, "order": order}
    if objective is not None:
        filters["objective"] = objective
    return filters


def _shared_projection(source, anchor, objective):
    candidates = [source.saved_candidate_catalog(row["candidate_ref"], fields=PROCESS_CANDIDATE_FIELDS) for row in source.rows]
    candidate = next(row for row in candidates if row["candidate_ref"] == anchor)
    return project_unified_process(source.saved_process, objective=objective, candidate=candidate, candidates=candidates)


def _shared_ordered(rows, filters):
    # The existing rank/event_index query keys select actual action/event order.
    actions = filters["record_kind"] == "attempts"
    key = {"rank": "action_id", "event_index": "source_event_id"}.get(filters["sort"], filters["sort"])
    identity = "action_id" if actions else "source_event_id"
    ordered = sorted(rows, key=lambda row: row[identity])
    known = [row for row in ordered if row[key] is not None]
    unknown = [row for row in ordered if row[key] is None]
    known.sort(key=lambda row: row[key], reverse=filters["order"] == "desc")
    return known + unknown


def process_details(source, filters, *, page: Union[int, str] = 1, size: Union[int, str] = 20, all_rows=False):
    anchor = filters["process_candidate_ref"] or source.selected_ref or (source.rows[0]["candidate_ref"] if source.rows else None)
    if anchor is None:
        reject("entity_not_found", "这次排产还没有保存候选计算记录。", 404)
    source._candidate_reference(anchor, require_result=False)
    filters = {**filters, "process_candidate_ref": anchor}
    page, size = parse_page(page), parse_page(size, size=True)
    offset = (page - 1) * size
    saved = _shared_projection(source, anchor, filters.get("objective"))
    filters["objective"] = saved["selected_objective"]["name"]
    rows = _shared_ordered(saved["actions"] if filters["record_kind"] == "attempts" else saved["progress"]["points"], filters)
    return {"run_ref": source.run["run_ref"], "capture_ref": source.run["run_ref"], "scope": source.scope, "baseline": source.baseline,
            **saved, "items": rows if all_rows else rows[offset:offset + size],
            "page": {"number": page, "size": size, "total": len(rows), "has_more": offset + size < len(rows)}, "filters": filters}


def process_export_records(source, filters=None, *, include_all_objectives=False, selected=None):
    """The same selector supplies all retained rows, independent of screen page."""
    process = source.saved_process
    if selected is None:
        selected = process_details(source, filters or normalize_process_filters(), all_rows=True)
    current = selected["filters"]
    selected = {**selected,
        "actions": selected["items"] if current["record_kind"] == "attempts" else _shared_ordered(
            selected["actions"], {**current, "record_kind": "attempts", "sort": "rank"}),
        "progress": {**selected["progress"],
            "points": selected["items"] if current["record_kind"] == "progress" else _shared_ordered(
                selected["progress"]["points"], {**current, "record_kind": "progress", "sort": "elapsed_ms"})}}
    return [{"process_version": UNIFIED_PROCESS_VERSION, "process": process,
             "export_objectives": process["target_objectives"] if include_all_objectives or filters is None else [selected["selected_objective"]["name"]],
             "projected": selected}]


def read_process_details(conn, run_ref, *, process_candidate_ref=None, objective=None, record_kind="attempts", sort=None, order="asc",
                         page: Union[int, str] = 1, size: Union[int, str] = 20, **query):
    filters = normalize_process_filters(process_candidate_ref=process_candidate_ref, objective=objective, record_kind=record_kind, sort=sort, order=order)
    store = CandidateStore(conn)
    with store.snapshot(), read_evidence_scope(conn):
        source = DecisionSource(store, run_ref, **query)
        data = process_details(source, filters, page=page, size=size)
        return data, source.state()
