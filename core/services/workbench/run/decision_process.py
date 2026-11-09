"""Selectors over one run's saved shared optimization process."""

from typing import Union

from core.models.workbench_run_candidate import reference, reject
from core.services.workbench.facts.unified_process import PROCESS_CANDIDATE_FIELDS, project_unified_process

from .decision_queries import parse_page
from .decision_session import decision_read, decision_snapshot_scope


def normalize_process_filters(*, process_candidate_ref=None, objective=None, record_kind="attempts", sort=None, order="asc"):
    sorts = {"attempts": ("rank", "elapsed_ms"), "progress": ("elapsed_ms", "event_index", "primary_value")}
    if record_kind not in sorts:
        reject("invalid_input", "请选择搜索动作或进步事件。", 422)
    sort = sort or sorts[record_kind][0]
    if sort not in sorts[record_kind] or order not in ("asc", "desc"):
        reject("invalid_input", "过程排序条件无效，请重新选择。", 422)
    if process_candidate_ref is not None:
        reference(process_candidate_ref)
    return {"section": "process", "process_candidate_ref": process_candidate_ref, "objective": objective,
            "record_kind": record_kind, "sort": sort, "order": order}


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


def resolve_process_filters(source, filters):
    """只根据候选头和本次运行的 run_options 确定 anchor 与目标方向，不读取存档；快照绑定在读取与投影之前。"""
    explicit = filters["process_candidate_ref"]
    source._candidate_reference(explicit)
    anchor = explicit or source.selected_ref
    if anchor is None:
        reject("entity_not_found", "这次排产还没有保存候选计算记录。", 404)
    options = source.scope["run_options"]
    objective = options["primary_objective"] if filters["objective"] is None else filters["objective"]
    if objective not in options["target_objectives"]:
        reject("invalid_input", "请选择本次排产的优化方向。", 422)
    return {**filters, "process_candidate_ref": anchor, "objective": objective}


def process_details(source, filters, *, page: Union[int, str] = 1, size: Union[int, str] = 20):
    """One page of the resolved view's records projected from the saved process."""
    page, size = parse_page(page), parse_page(size, size=True)
    offset = (page - 1) * size
    saved = _shared_projection(source, filters["process_candidate_ref"], filters["objective"])
    rows = _shared_ordered(saved["actions"] if filters["record_kind"] == "attempts" else saved["progress"]["points"], filters)
    screen = {key: value for key, value in saved.items() if key != "actions"}
    return {"run_ref": source.run["run_ref"], "capture_ref": source.run["run_ref"], "scope": source.scope, "baseline": source.baseline,
            **screen, "items": rows[offset:offset + size],
            "page": {"number": page, "size": size, "total": len(rows), "has_more": offset + size < len(rows)}, "filters": filters}


def process_export_records(source, filters, *, include_all_objectives):
    """The same selector supplies all retained rows, independent of screen page.

    filters are the exported process view's resolved filters.
    """
    saved = _shared_projection(source, filters["process_candidate_ref"], filters["objective"])
    process = source.saved_process
    actions_filters = filters if filters["record_kind"] == "attempts" else {**filters, "record_kind": "attempts", "sort": "rank"}
    progress_filters = filters if filters["record_kind"] == "progress" else {**filters, "record_kind": "progress", "sort": "elapsed_ms"}
    selected = {**saved,
        "actions": _shared_ordered(saved["actions"], actions_filters),
        "progress": {**saved["progress"], "points": _shared_ordered(saved["progress"]["points"], progress_filters)}}
    return {"process": process,
            "export_objectives": process["target_objectives"] if include_all_objectives else [filters["objective"]],
            "projected": selected}


def read_process_details(conn, run_ref, *, bind_snapshot, process_candidate_ref=None, objective=None, record_kind="attempts",
                         sort=None, order="asc", page: Union[int, str] = 1, size: Union[int, str] = 20, **query):
    filters = normalize_process_filters(process_candidate_ref=process_candidate_ref, objective=objective, record_kind=record_kind, sort=sort, order=order)
    with decision_read(conn, run_ref, **query) as source:
        filters = resolve_process_filters(source, filters)
        snapshot = bind_snapshot(decision_snapshot_scope(source, filters=filters), source.state())
        return process_details(source, filters, page=page, size=size), snapshot
