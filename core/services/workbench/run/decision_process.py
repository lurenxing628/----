"""One selector for saved representative attempts and retained progress points."""

from typing import Union

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_command import canonical_json
from core.models.workbench_run_candidate import MAX_RESPONSE_BYTES, reference, reject
from core.services.workbench.facts.candidate_process import PROCESS_VERSION, candidate_process
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_values import bounded_size

from .decision_queries import _page
from .decision_source import DecisionSource


def normalize_process_filters(*, process_candidate_ref=None, record_kind="attempts", sort=None, order="asc"):
    sorts = {"attempts": ("rank", "elapsed_ms", "primary_value"), "progress": ("elapsed_ms", "event_index", "primary_value")}
    if record_kind not in sorts:
        reject("invalid_input", "请选择代表尝试或进步事件。", 422)
    sort = sort or sorts[record_kind][0]
    if sort not in sorts[record_kind] or order not in ("asc", "desc"):
        reject("invalid_input", "过程排序条件无效，请重新选择。", 422)
    if process_candidate_ref is not None:
        reference(process_candidate_ref)
    return {"section": "process", "process_candidate_ref": process_candidate_ref, "record_kind": record_kind, "sort": sort, "order": order}


def _projection(source):
    if not hasattr(source, "_process_projection"):
        source._process_projection = {row["candidate_ref"]: candidate_process(row, source.rows) for row in source.rows}
    return source._process_projection


def _ordered(rows, filters):
    identity = "saved_index" if filters["record_kind"] == "attempts" else "event_index"
    rows = sorted(rows, key=lambda row: (row["source_candidate_ref"] or "", row[identity] if row[identity] is not None else float("inf")))
    known = [row for row in rows if row[filters["sort"]] is not None]
    unknown = [row for row in rows if row[filters["sort"]] is None]
    known.sort(key=lambda row: row[filters["sort"]], reverse=filters["order"] == "desc")
    return known + unknown


def process_details(source, filters, *, page: Union[int, str] = 1, size: Union[int, str] = 20, all_rows=False):
    anchor = filters["process_candidate_ref"] or source.selected_ref or (source.rows[0]["candidate_ref"] if source.rows else None)
    if anchor is None:
        reject("entity_not_found", "这次排产还没有保存候选计算记录。", 404)
    source._candidate_reference(anchor, require_result=False)
    filters = {**filters, "process_candidate_ref": anchor}
    projected = _projection(source)
    saved = projected[anchor]
    rows = _ordered(saved["attempts"] if filters["record_kind"] == "attempts" else saved["progress"]["points"], filters)
    page, size = _page(page), _page(size, size=True)
    offset = (page - 1) * size
    return {"run_ref": source.run["run_ref"], "capture_ref": source.run["run_ref"], "scope": source.scope, "baseline": source.baseline,
        "candidates": [projected[row["candidate_ref"]]["candidate"] for row in source.rows],
        **{key: saved[key] for key in ("candidate", "source", "summary", "objective", "progress", "stages", "attempts")},
        "items": rows if all_rows else rows[offset:offset + size],
        "page": {"number": page, "size": size, "total": len(rows), "has_more": offset + size < len(rows)},
        "filters": filters, "process_version": PROCESS_VERSION}


def process_export_records(source, filters=None):
    """The same selector supplies all retained rows, independent of screen page."""
    projected = _projection(source)
    if filters is None:
        refs = [row["candidate_ref"] for row in source.rows]
        filters = normalize_process_filters()
    else:
        selected = process_details(source, filters, all_rows=True)
        refs = [selected["candidate"]["candidate_ref"]]
        filters = selected["filters"]
    return [{**projected[ref], "candidate": projected[ref]["candidate"],
             "attempts": _ordered(projected[ref]["attempts"], {**filters, "record_kind": "attempts",
                 "sort": filters["sort"] if filters["record_kind"] == "attempts" else "rank"}),
             "progress": {**projected[ref]["progress"], "points": _ordered(projected[ref]["progress"]["points"],
                 {**filters, "record_kind": "progress", "sort": filters["sort"] if filters["record_kind"] == "progress" else "elapsed_ms"})}}
            for ref in refs]


def read_process_details(conn, run_ref, *, process_candidate_ref=None, record_kind="attempts", sort=None, order="asc",
                         page: Union[int, str] = 1, size: Union[int, str] = 20, **query):
    filters = normalize_process_filters(process_candidate_ref=process_candidate_ref, record_kind=record_kind, sort=sort, order=order)
    store = CandidateStore(conn)
    with store.snapshot(), read_evidence_scope(conn):
        source = DecisionSource(store, run_ref, **query)
        data = process_details(source, filters, page=page, size=size)
        bounded_size(len(canonical_json(data).encode("utf-8")), MAX_RESPONSE_BYTES)
        return data, source.state()
