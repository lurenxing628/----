"""Lazy batch membership and remaining requirements for one candidate anchor."""

from typing import Union

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_run_candidate import reject
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.decision_candidate import candidate_reason
from core.services.workbench.facts.decision_metrics import METRIC_VERSION
from core.services.workbench.facts.preparation_projection import preparation_summary, public_preparation_metrics

from .decision_completion import compact_completion
from .decision_queries import parse_page
from .decision_recommendation import detail_drill
from .decision_source import DecisionSource

COMPLETION_FILTERS = {
    "all": None,
    "complete": "complete_batch_refs",
    "unfinished": "incomplete_batch_refs",
    "ordinary": "ordinary_incomplete_batch_refs",
    "deferred": "deferred_batch_refs",
    "unknown": "unknown_batch_refs",
}


def normalize_completion_filters(*, completion_filter="all", sort="batch_id", order="asc"):
    if completion_filter not in COMPLETION_FILTERS or sort != "batch_id" or order not in ("asc", "desc"):
        reject("invalid_input", "工序安排的筛选类别或排序条件无效，请重新选择。", 422)
    return {"section": "completion-batches", "completion_filter": completion_filter, "sort": sort, "order": order}


def _remaining_drill(source, key, available, rows, *, batch_ref=None):
    if not available or not rows:
        return None
    query = {"work_scope": "remaining"}
    if batch_ref is not None:
        query["batch_ref"] = batch_ref
    return detail_drill(source, key, "preparation", query)


def _batch_row(source, key, item, scope, reason):
    available = scope["source_available"]
    remaining = source.completion.remaining_batches(key).get(item["batch_ref"], {})
    count = remaining.get("operation_count", 0)
    metrics = remaining.get("metrics")
    if metrics is None:
        rows = remaining.get("operations", [])
        count = len(rows)
        metrics = preparation_summary(rows, available=available)["metrics"]
    return {"batch_ref": item["batch_ref"], "batch_label": item["batch_id"],
            "part_no": item["part_no"], "part_label": item["part_label"], "quantity": item["quantity"],
            "completion_state": item["completion_state"] if available else "unknown",
            "schedule_complete": item["schedule_complete"] if available else None,
            "scheduled_operation_count": item["scheduled_operation_count"] if available else None,
            "unplanned_operation_count": len(remaining.get("unplanned_operation_refs", [])) if available else None,
            "deferred_operation_count": len(remaining.get("deferred_operation_refs", [])) if available else None,
            "remaining_work": {"operation_count": count if available else None,
                               "metrics": public_preparation_metrics(metrics)},
            "issues": list(item["issues"]) if available else [reason["code"]],
            "remaining_drill": _remaining_drill(source, key, available, count, batch_ref=item["batch_ref"])}


def completion_batches(source, filters, *, page: Union[int, str] = 1, size: Union[int, str] = 20):
    key = source.selected_ref
    if key is None:
        reject("invalid_input", "请选择本次排产中的候选后查看工序安排。", 422)
    candidate = source._candidate_reference(key, require_result=False)
    scope = source.completion.scope(key)
    available = scope["source_available"]
    reason = candidate_reason(candidate)
    membership = COMPLETION_FILTERS[filters["completion_filter"]]
    refs = set(source.scope["batch_refs"] if membership is None else scope[membership])
    items = [row for row in source.completion.delivery(key) if row["batch_ref"] in refs]
    items.sort(key=lambda row: row["batch_ref"])
    known = [row for row in items if row["batch_id"] is not None]
    unknown = [row for row in items if row["batch_id"] is None]
    known.sort(key=lambda row: row["batch_id"], reverse=filters["order"] == "desc")
    items = known + unknown
    page, size = parse_page(page), parse_page(size, size=True)
    offset = (page - 1) * size
    selected = items[offset:offset + size]
    remaining = source.completion.remaining_operation_refs(key)
    return {"run_ref": source.run["run_ref"], "scope": source.scope, "baseline": source.baseline,
            "candidate": {"candidate_ref": key, "label": candidate["artifact"].get("label"), "persisted_status": candidate["status"]},
            "source": {"role": "completion_anchor", "grain": "full_admission_per_candidate_batch",
                       "candidate_ref": key, "available": available, "reason": reason},
            "filters": filters, "items": [_batch_row(source, key, item, scope, reason) for item in selected],
            "page": {"number": page, "size": size, "total": len(items), "has_more": offset + size < len(items)},
            "summary": compact_completion(scope, _remaining_drill(source, key, available, remaining)),
            "metric_version": METRIC_VERSION}


def read_completion_batches(conn, run_ref, *, completion_filter="all", sort="batch_id", order="asc",
                            page: Union[int, str] = 1, size: Union[int, str] = 20, **query):
    filters = normalize_completion_filters(completion_filter=completion_filter, sort=sort, order=order)
    store = CandidateStore(conn)
    with store.snapshot(), read_evidence_scope(conn):
        source = DecisionSource(store, run_ref, **query)
        data = completion_batches(source, filters, page=page, size=size)
        return data, source.state()
