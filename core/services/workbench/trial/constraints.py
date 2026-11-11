"""Trial interval parsing, archived occupancy spans and outside-scope point evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Mapping, Sequence, Tuple

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial import issue
from core.services.workbench.facts.zero_duration_evidence import trial_point_evidence
from core.services.workbench.plan.point_evidence import official_point_work
from core.services.workbench.run.schedule_occupancy_constraints import (
    OutsidePointVersion,
    ProvenOutsidePoints,
    UnprovenOutsidePoints,
    latest_schedule_rows,
)

from .arrangements import same_arrangement
from .occupancy import ReportedExecution, arranged_occupancy, reported_archive


def _interval_with_point(value, *, original):
    start, end = datetime.fromisoformat(value["start"]), datetime.fromisoformat(value["end"])
    if start.tzinfo is not None or end.tzinfo is not None or end < start:
        raise ValueError("Invalid positive factory-local interval")
    if start == end:
        return (start, end), trial_point_evidence(original, value)
    return (start, end), None


def build_current_trial_spans(rows):
    """Each row's current interval and interval parse error, without execution occupancy."""
    current_by_op = {}
    current_by_row = {}
    current_errors_by_op = {}
    current_points_by_op = {}
    current_points_by_row = {}
    for row in rows:
        op_ref = row["operation_ref"]
        row_ref = row["row_ref"]
        try:
            curr_span, witness = _interval_with_point(row["current"], original=row["original"])
        except (TypeError, ValueError) as exc:
            curr_span = None
            witness = None
            current_errors_by_op[op_ref] = exc.with_traceback(None)
        if curr_span is not None:
            current_by_op[op_ref] = curr_span
        if witness is not None:
            current_points_by_op[witness.op_id] = witness
            current_points_by_row[row_ref] = witness
        current_by_row[row_ref] = curr_span
    return {
        "current_by_op": current_by_op,
        "current_by_row": current_by_row,
        "current_errors_by_op": current_errors_by_op,
        "current_points_by_op": current_points_by_op,
        "current_points_by_row": current_points_by_row,
    }


def build_trial_intervals(rows, *, reported: Mapping[str, ReportedExecution]):
    """Each row's current and original interval and the resources they occupy.

    reported is the current side's parsed execution mapping. The original side keeps its source-time
    ``row["original"]["execution"]``.
    原始侧与当前侧是同一个执行快照对象时（正式计划来源在建草稿时核验）共用一次解析；不同快照（已保存草稿、
    候选归档、点工序证据）各自解析，绝不按工序编号或内容合并。
    """
    spans = build_current_trial_spans(rows)
    current_by_row = spans["current_by_row"]
    current_points_by_row = spans["current_points_by_row"]
    original_by_row = {}
    original_by_source_row = {}
    original_points_by_row = {}
    current_occupancy, original_occupancy = {}, {}
    for row in rows:
        original = row["original"]
        current = row["current"]
        orig_arr = original["arrangement"]
        op_ref = row["operation_ref"]
        row_ref = row["row_ref"]
        curr_span = current_by_row[row_ref]
        curr_reported = reported[op_ref]
        if curr_span is not None:
            current_occupancy[row_ref] = arranged_occupancy(curr_span, current, curr_reported)
        if (
            curr_span is not None
            and current["start"] == orig_arr["start"]
            and current["end"] == orig_arr["end"]
            and (current["start"] != current["end"] or same_arrangement(current, orig_arr))
        ):
            orig_span = curr_span
            if row_ref in current_points_by_row:
                original_points_by_row[row_ref] = current_points_by_row[row_ref]
        else:
            try:
                orig_span, orig_witness = _interval_with_point(orig_arr, original=original)
            except (TypeError, ValueError):
                orig_span = None
                orig_witness = None
            if orig_witness is not None:
                original_points_by_row[row_ref] = orig_witness
        if orig_span is not None:
            shared = original["execution"] is curr_reported.execution
            orig_reported = curr_reported if shared else reported_archive(original["execution"])
            original_occupancy[row_ref] = arranged_occupancy(orig_span, orig_arr, orig_reported)
        original_by_row[row_ref] = orig_span
        original_by_source_row[row["source_row_ref"]] = orig_span
    return {
        **spans,
        "original_by_row": original_by_row,
        "original_by_source_row": original_by_source_row,
        "original_points_by_row": original_points_by_row,
        "current_occupancy_by_row": current_occupancy,
        "original_occupancy_by_row": original_occupancy,
    }


def build_archived_trial_intervals(rows, *, execution: Mapping[str, Dict[str, Any]]):
    """Each row's current and original interval and occupancy from archived execution snapshots."""
    return build_trial_intervals(
        rows,
        reported={row["operation_ref"]: reported_archive(execution[row["operation_ref"]]) for row in rows},
    )


def prepare_outside_schedule_state(
    conn: Any,
    rows: Sequence[Mapping[str, Any]],
    live: Mapping[str, Any],
    reported: Mapping[str, ReportedExecution],
) -> Tuple[Dict[int, Mapping[str, Any]], Dict[int, OutsidePointVersion]]:
    """Resolve latest schedule rows once and preload proven official zero-duration point work ids."""
    selected = {row["operation_ref"] for row in rows}
    refs = live["preflight_facts"].operation_refs
    operations = live["execution_operations"]
    latest = latest_schedule_rows(live["facts"]["tables"]["Schedule"])
    point_versions: Dict[int, OutsidePointVersion] = {}
    for op_id, row in latest.items():
        ref = refs[op_id]
        if (
            ref in selected
            or operations[ref]["source"] == "external"
            or reported[ref].execution["execution_state"] == "complete"
            or row["start_time"] != row["end_time"]
        ):
            continue
        version = row["version"]
        if version in point_versions:
            continue
        try:
            point_versions[version] = ProvenOutsidePoints(frozenset(official_point_work(conn, version)))
        except WorkbenchCommandRejected as exc:
            # 读取容量超限是整个请求的 413，不是这道工序“没有依据”。
            if exc.status == 413:
                raise
            point_versions[version] = UnprovenOutsidePoints(
                issue("outside_scope_point_unproven", "范围外那道零工时工序没有可核对的依据。")
            )
    return latest, point_versions
