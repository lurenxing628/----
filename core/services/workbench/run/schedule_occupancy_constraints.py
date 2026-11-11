"""Pure in-memory resource occupancy collection and sweep-line overlap checks."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from heapq import heappop, heappush
from typing import (
    TYPE_CHECKING,
    AbstractSet,
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

from core.models.content import content_text
from core.models.workbench_trial import issue, reject
from core.services.execution.projection import is_point_work

if TYPE_CHECKING:
    from core.services.scheduler.run.schedule_input_contracts import ExecutionGuardState

MAX_OCCUPANCY_ISSUES = 50000


@dataclass(frozen=True)
class ProvenOutsidePoints:
    op_ids: AbstractSet[int]


@dataclass(frozen=True)
class UnprovenOutsidePoints:
    problem: Dict[str, Any]


OutsidePointVersion = Union[ProvenOutsidePoints, UnprovenOutsidePoints]
OutsidePointVersions = Mapping[int, OutsidePointVersion]


def collect_resource_segments(
    rows: Sequence[Any], execution_guard: ExecutionGuardState
) -> Dict[Tuple[str, str], Tuple[Tuple[datetime, Optional[datetime], int], ...]]:
    execution_facts = execution_guard.execution_facts
    segmented_op_ids = {
        op_id
        for op_id in execution_guard.execution_completed_op_ids
        if execution_facts[op_id].execution_resource_segments
    }
    timelines: Dict[Tuple[str, str], List[Tuple[datetime, Optional[datetime], int]]] = defaultdict(
        list,
        {key: list(segments) for key, segments in execution_guard.execution_resource_segments.items()},
    )
    for row in rows:
        if row.source == "internal" and row.start_time < row.end_time and row.op_id not in segmented_op_ids:
            timelines["machine_id", row.machine_id].append((row.start_time, row.end_time, row.op_id))
            timelines["operator_id", row.operator_id].append((row.start_time, row.end_time, row.op_id))
    return {key: tuple(sorted(intervals)) for key, intervals in timelines.items()}


def resource_overlap_issue(
    resource_segments: Mapping[Tuple[str, str], Sequence[Tuple[datetime, Optional[datetime], int]]]
) -> Optional[Dict[str, Any]]:
    for intervals in resource_segments.values():
        previous_end = None
        for start, end, _ in intervals:
            if previous_end is not None and start < previous_end:
                return {
                    "code": "candidate_resource_overlap",
                    "message": "候选内设备或人员安排重叠，不能正式采用。",
                }
            previous_end = end
    return None


def _scan_single_resource(
    kind: str,
    raw_intervals: Sequence[Tuple[datetime, datetime, Any, Optional[str], Optional[str]]],
    add_issue: Callable[[Dict[str, Any]], None],
) -> None:
    intervals = sorted(raw_intervals, key=lambda value: (value[0], value[1]))
    active: Dict[int, Tuple[Any, Optional[str], Optional[str]]] = {}
    trial: Dict[int, Tuple[Any, Optional[str], Optional[str]]] = {}
    expiry: List[Tuple[datetime, int]] = []
    for index, (start, end, operation, task, role) in enumerate(intervals):
        while expiry and expiry[0][0] <= start:
            _, expired = heappop(expiry)
            active.pop(expired)
            trial.pop(expired, None)
        # Preserve chronological issue order, pairing outside work and real production only with
        # trial work. Overlaps among them do not belong to this check.
        candidates = active if task is not None else trial
        for other_operation, other_task, other_role in candidates.values():
            if operation == other_operation:
                continue
            held = role if task is None else other_role
            if held != "actual":
                add_issue(
                    issue(
                        kind + "_overlap",
                        "设备安排重叠。" if kind == "machine" else "人员安排重叠。",
                        task or other_task,
                        other_task if task else None,
                    )
                )
            if held in ("outside_actual", "actual"):
                add_issue(issue("execution_resource_overlap", "安排与真实生产资源占用重叠。", task or other_task))
        active[index] = (operation, task, role)
        if task is not None:
            trial[index] = (operation, task, role)
        heappush(expiry, (end, index))


def scan_resource_overlaps(
    occupied: Mapping[Tuple[str, Any], Sequence[Tuple[datetime, datetime, Any, Optional[str], Optional[str]]]],
    add_issue: Callable[[Dict[str, Any]], None],
) -> None:
    for (kind, _), raw_intervals in occupied.items():
        if any(task is not None for _, _, _, task, _ in raw_intervals):
            _scan_single_resource(kind, raw_intervals, add_issue)


def collect_occupancy_issues(
    rows: Sequence[Mapping[str, Any]],
    live: Mapping[str, Any],
    *,
    trial_intervals: Mapping[str, Any],
    latest_schedule: Mapping[int, Mapping[str, Any]],
    outside_point_versions: OutsidePointVersions,
) -> List[Dict[str, Any]]:
    """Collect deduplicated resource occupancy, overlap and unproven-release blockers."""
    found: Dict[str, Dict[str, Any]] = {}

    def add(item: Dict[str, Any]) -> None:
        key = content_text(item)
        if key not in found:
            found[key] = item
            if len(found) > MAX_OCCUPANCY_ISSUES:
                reject("validation_too_large", "真实冲突数量超过50000条，本次没有截断冲突或提交调整。", 413)

    occupancy = trial_intervals["current_occupancy_by_row"]
    reported = live["execution_reported"]
    ids = {(kind, ref): key for (kind, key), ref in live["preflight_facts"].refs.items()}
    actual, release, unproven = _execution_occupancy(rows, live, reported, ids, add)
    occupied = _trial_intervals(rows, occupancy, actual, ids)
    placed = _outside_intervals(
        occupied, rows, live, reported, ids, latest_schedule, outside_point_versions, add
    )
    _actual_intervals(occupied, reported, actual, placed, ids)
    scan_resource_overlaps(occupied, add)
    _unproven_issues(rows, occupancy, release, unproven, add)
    return list(found.values())


def _archived_operations(rows: Sequence[Mapping[str, Any]], live: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    archived = {row["operation_ref"]: row["original"]["operation"] for row in rows}
    origin = live["origin"]
    for ref, member in origin.unarranged.items():
        archived.setdefault(ref, member["operation"])
    if origin.facts is not None:
        ops = origin.facts.tables["BatchOperations"]
        for op_id, ref in origin.facts.operation_refs.items():
            if op_id in ops:
                archived.setdefault(ref, ops[op_id])
    ops = origin.admission_operations
    for op_id, ref in origin.admission_refs_by_op_id.items():
        if op_id in ops:
            archived.setdefault(ref, ops[op_id])
    return archived


def _record_report_span(
    ref: str,
    source: Any,
    complete: bool,
    point: bool,
    report: Mapping[str, Any],
    span: Tuple[Any, Any],
    ids: Mapping[Tuple[str, Any], Any],
    release: Dict[Tuple[str, Any], Set[str]],
    unproven: Dict[Tuple[str, Any], Set[str]],
    add_issue: Callable[[Dict[str, Any]], None],
) -> None:
    if complete and point and report["effective_processing_hours"] == 0 and span[0] == span[1]:
        return
    for kind in ("machine", "operator"):
        resource = report["actual_" + kind + "_ref"]
        if resource is None:
            add_issue(_retired_source_unknown() if source is None else _resource_unknown())
        elif (kind, resource) not in ids:
            add_issue(_resource_unknown())
        elif not complete:
            release[kind, resource].add(ref)
        elif span[1] <= span[0]:
            unproven[kind, resource].add(ref)


def _execution_occupancy(
    rows: Sequence[Mapping[str, Any]],
    live: Mapping[str, Any],
    reported: Mapping[str, Any],
    ids: Mapping[Tuple[str, Any], Any],
    add_issue: Callable[[Dict[str, Any]], None],
) -> Tuple[Set[str], Dict[Tuple[str, Any], Set[str]], Dict[Tuple[str, Any], Set[str]]]:
    operations = live["execution_operations"]
    archived: Optional[Dict[str, Mapping[str, Any]]] = None
    actual: Set[str] = set()
    release: Dict[Tuple[str, Any], Set[str]] = defaultdict(set)
    unproven: Dict[Tuple[str, Any], Set[str]] = defaultdict(set)
    for ref, parsed in reported.items():
        execution = parsed.execution
        if execution["execution_state"] == "unreported":
            continue
        op = operations[ref]
        if not op["identity_active"] or op["id"] is None:
            if archived is None:
                archived = _archived_operations(rows, live)
            op = archived.get(ref) or op
        source = op["source"]
        if source == "external":
            continue
        point = (
            is_point_work(source, op["setup_hours"], op["unit_hours"], execution["target_quantity"])
            if source == "internal"
            else False
        )
        complete = execution["execution_state"] == "complete"
        if complete:
            actual.add(ref)
        for report, span in parsed.spans:
            _record_report_span(ref, source, complete, point, report, span, ids, release, unproven, add_issue)
    return actual, release, unproven


def _identified(
    segments: Sequence[Any],
    arrangement: Optional[Mapping[str, Any]],
    ids: Mapping[Tuple[str, Any], Any],
) -> List[Tuple[datetime, datetime, Any, Any]]:
    result: List[Tuple[datetime, datetime, Any, Any]] = []
    for start, end, *refs in segments:
        keys = [
            arrangement[kind + "_id"]
            if arrangement is not None and ref == arrangement[kind + "_ref"]
            else ids.get((kind, ref))
            for kind, ref in zip(("machine", "operator"), refs)
        ]
        result.append((start, end, keys[0], keys[1]))
    return result


def _positive_local_interval(start_raw: Any, end_raw: Any) -> Tuple[datetime, datetime]:
    start, end = datetime.fromisoformat(start_raw), datetime.fromisoformat(end_raw)
    if start.tzinfo is not None or end.tzinfo is not None or end <= start:
        raise ValueError("Invalid positive factory-local interval")
    return start, end


def _outside_interval_invalid() -> Dict[str, Any]:
    return issue("outside_scope_interval_invalid", "范围外正式安排的时间不对，判断不了设备人员有没有空。")


def _outside_occupancy(
    row: Mapping[str, Any],
    outside_point_versions: OutsidePointVersions,
) -> Tuple[Optional[Tuple[datetime, datetime]], Optional[Dict[str, Any]]]:
    """A proven point occupies nothing; an unproven interval reports a blocker."""
    if row["start_time"] == row["end_time"]:
        version_state = outside_point_versions[row["version"]]
        if isinstance(version_state, UnprovenOutsidePoints):
            return None, version_state.problem
        if row["op_id"] in version_state.op_ids:
            return None, None
        return None, _outside_interval_invalid()
    try:
        return _positive_local_interval(row["start_time"], row["end_time"]), None
    except (TypeError, ValueError):
        return None, _outside_interval_invalid()


def latest_schedule_rows(
    schedule_rows: Sequence[Mapping[str, Any]],
) -> Dict[int, Mapping[str, Any]]:
    latest: Dict[int, Mapping[str, Any]] = {}
    for row in sorted(schedule_rows, key=lambda item: (item["version"], item["id"])):
        latest[row["op_id"]] = row
    return latest


def _outside_intervals(
    occupied: Dict[Tuple[str, Any], List[Tuple[datetime, datetime, Any, Optional[str], Optional[str]]]],
    rows: Sequence[Mapping[str, Any]],
    live: Mapping[str, Any],
    reported: Mapping[str, Any],
    ids: Mapping[Tuple[str, Any], Any],
    latest_schedule: Mapping[int, Mapping[str, Any]],
    outside_point_versions: OutsidePointVersions,
    add_issue: Callable[[Dict[str, Any]], None],
) -> Set[str]:
    placed: Set[str] = set()
    selected = {row["operation_ref"] for row in rows}
    refs = live["preflight_facts"].operation_refs
    operations = live["execution_operations"]
    for op_id, row in latest_schedule.items():
        ref = refs[op_id]
        if ref in selected or operations[ref]["source"] == "external":
            continue
        parsed = reported[ref]
        if parsed.execution["execution_state"] == "complete":
            segments: Sequence[Tuple[datetime, datetime, Any, Any]] = _identified(parsed.segments, None, ids)
            role = "outside_actual"
            placed.add(ref)
        else:
            span, problem = _outside_occupancy(row, outside_point_versions)
            if problem is not None:
                add_issue(problem)
            if span is None:
                continue
            segments = ((*span, row["machine_id"], row["operator_id"]),)
            role = "outside"
        _occupy(occupied, segments, ref, None, role)
    return placed


def _actual_intervals(
    occupied: Dict[Tuple[str, Any], List[Tuple[datetime, datetime, Any, Optional[str], Optional[str]]]],
    reported: Mapping[str, Any],
    actual: AbstractSet[str],
    placed: AbstractSet[str],
    ids: Mapping[Tuple[str, Any], Any],
) -> None:
    for ref, parsed in reported.items():
        if ref in actual and ref not in placed:
            _occupy(occupied, _identified(parsed.segments, None, ids), ref, None, "actual")


def _occupy(
    occupied: Dict[Tuple[str, Any], List[Tuple[datetime, datetime, Any, Optional[str], Optional[str]]]],
    segments: Sequence[Tuple[datetime, datetime, Any, Any]],
    operation: str,
    task: Optional[str],
    role: Optional[str],
) -> None:
    for start, end, machine_id, operator_id in segments:
        for kind, key in (("machine", machine_id), ("operator", operator_id)):
            if key is not None:
                occupied[kind, key].append((start, end, operation, task, role))


def _trial_intervals(
    rows: Sequence[Mapping[str, Any]],
    occupancy: Mapping[str, Sequence[Any]],
    actual: AbstractSet[str],
    ids: Mapping[Tuple[str, Any], Any],
) -> Dict[Tuple[str, Any], List[Tuple[datetime, datetime, Any, Optional[str], Optional[str]]]]:
    occupied: Dict[Tuple[str, Any], List[Tuple[datetime, datetime, Any, Optional[str], Optional[str]]]] = defaultdict(list)
    for row in rows:
        if row["original"]["operation"]["source"] == "internal":
            arrangement = None if row["operation_ref"] in actual else row["current"]
            segments = _identified(occupancy.get(row["row_ref"], ()), arrangement, ids)
            _occupy(occupied, segments, row["operation_ref"], row["task_ref"], None)
    return occupied


def _row_unproven_issues(
    row: Mapping[str, Any],
    row_segments: Sequence[Any],
    checks: Sequence[Tuple[Mapping[Tuple[str, Any], Set[str]], str, str]],
    add_issue: Callable[[Dict[str, Any]], None],
) -> None:
    for _, _, *refs in row_segments:
        for kind, resource in zip(("machine", "operator"), refs):
            for holders_by_resource, code, message in checks:
                holders = holders_by_resource.get((kind, resource))
                if holders and (len(holders) > 1 or row["operation_ref"] not in holders):
                    add_issue(issue(code, message, row["task_ref"]))


def _unproven_issues(
    rows: Sequence[Mapping[str, Any]],
    occupancy: Mapping[str, Sequence[Any]],
    release: Mapping[Tuple[str, Any], Set[str]],
    unproven: Mapping[Tuple[str, Any], Set[str]],
    add_issue: Callable[[Dict[str, Any]], None],
) -> None:
    checks = (
        (release, "execution_resource_release_unknown", "同一资源仍有未确认整道完工的实际生产，不能推测释放时间。"),
        (unproven, "execution_resource_interval_unknown", "已有实际生产占用时间不完整，无法证明资源可用。"),
    )
    for row in rows:
        if row["original"]["operation"]["source"] == "internal":
            _row_unproven_issues(row, occupancy.get(row["row_ref"], ()), checks, add_issue)


def _resource_unknown() -> Dict[str, Any]:
    return issue("execution_resource_unknown", "现场数据里没有设备人员编号，范围外的占用情况无法判断。")


def _retired_source_unknown() -> Dict[str, Any]:
    return issue("execution_operation_source_unknown", "已删除工序缺少原工艺来源，无法判断未填设备人员的报工是否占用内部资源。")
