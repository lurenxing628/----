"""One actual-type changeover rule for numeric evaluation and saved events.

Adapters supply actual type identities and times. Labels never identify a type.
Each device's complete nonzero internal sequence establishes predecessors before
the next arrangement's start is selected into a half-open window.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Tuple

from .value_domains import EXTERNAL, INTERNAL


@dataclass(frozen=True)
class ChangeoverArrangement:
    machine_ref: Optional[str]
    operation_ref: Optional[str]
    row_ref: Optional[str]
    type_ref: Optional[str]
    type_label: Optional[str]
    start: Optional[datetime]
    end: Optional[datetime]
    source: Optional[str]
    machine_label: Optional[str] = None
    point_event: bool = False
    sort_key: Tuple[Any, ...] = ()


def type_transition(previous_type_ref, next_type_ref, previous_operation_ref=None, next_operation_ref=None):
    """Known adjacent identity change; a missing actual identity stays unknown."""
    if not previous_type_ref or not next_type_ref:
        return None
    if previous_operation_ref is not None and previous_operation_ref == next_operation_ref:
        return 0
    return int(previous_type_ref != next_type_ref)


def _selected(row, start, end, operations):
    if operations is not None and row.operation_ref is not None and row.operation_ref not in operations:
        return False
    return row.start is None or (start is None or row.start >= start) and (end is None or row.start < end)


def _timed(row):
    return row.start is not None and row.end is not None and row.start < row.end


def _problems(row):
    result = []
    for field, value, code, message in (
        ("source", row.source == INTERNAL, "arrangement_source_unknown", "保存安排的内制来源缺项，切换顺序未知。"),
        ("machine_ref", row.machine_ref, "resource_identity_unknown", "保存安排缺少永久设备身份，切换顺序未知。"),
        ("operation_ref", row.operation_ref, "operation_identity_unknown", "保存安排缺少永久工序身份，切换顺序未知。"),
        ("row_ref", row.row_ref, "arrangement_identity_unknown", "保存安排缺少任务行身份，切换事件的定位资料缺项。"),
        ("type_ref", row.type_ref, "process_type_unknown", "保存安排缺少实际工种身份，切换次数保留已知小计。"),
        ("task_time", _timed(row), "arrangement_time_unknown", "保存安排的有效时间缺项，切换顺序未知。"),
    ):
        if not value:
            result.append({"code": code, "message": message, "field": field,
                           **{key: value for key, value in (("machine_ref", row.machine_ref),
                                                            ("operation_ref", row.operation_ref), ("row_ref", row.row_ref))
                              if value is not None}})
    return result


def _event(machine_ref, previous, current, sequence, *, conflict):
    overlap = previous.end > current.start
    return {"machine_ref": machine_ref, "machine_label": current.machine_label,
            "previous_operation_ref": previous.operation_ref, "next_operation_ref": current.operation_ref,
            "previous_row_ref": previous.row_ref, "next_row_ref": current.row_ref,
            "previous_type_ref": previous.type_ref, "next_type_ref": current.type_ref,
            "previous_type": previous.type_label, "next_type": current.type_label,
            "previous_start": previous.start.isoformat(), "previous_end": previous.end.isoformat(),
            "next_start": current.start.isoformat(), "next_end": current.end.isoformat(),
            "sequence": sequence, "overlap": overlap, "conflict": conflict,
            "state": "partial" if conflict else "complete"}


def _conflicts(ordered):
    """One witness per conflicting start; equal-operation segments do not clash.

    The two longest prior ends suffice to find the longest other operation.
    Their ends never decrease, so this scan stays linear after sequence sorting.
    """
    leaders, result = [], []
    for ordinal, row in ordered:
        if row.source != INTERNAL or row.operation_ref is None:
            continue
        others = [item for item in leaders if item[1].operation_ref != row.operation_ref]
        if others and others[0][1].end > row.start:
            result.append((others[0], (ordinal, row)))
        previous = next((item for item in leaders if item[1].operation_ref == row.operation_ref), None)
        if previous is None or previous[1].end <= row.end:
            leaders = [item for item in leaders if item[1].operation_ref != row.operation_ref] + [(ordinal, row)]
            leaders = sorted(leaders, key=lambda item: item[1].end, reverse=True)[:2]
    return result


def project_changeover_events(arrangements, *, start=None, end=None, work_available=True,
                             next_operation_refs=None):
    """Confirmed sorted events plus completeness over the actual saved sequence."""
    if not work_available:
        return {"events": [], "count": None, "known_count": None, "changed_machine_count": None,
                "known_changed_machine_count": None, "state": "unavailable", "unknown_count": 1,
                "conflict": None, "conflict_count": None,
                "issues": [{"code": "arrangements_unavailable", "message": "比较对象缺少保存安排，工种切换次数未知。"}],
                "metric_version": "type_changeover_v1", "source": "saved_arrangement_sequence"}
    operations = set(next_operation_refs) if next_operation_refs is not None else None
    rows, machines, unplaced, problems = {}, {}, [], {}
    for row in arrangements:
        if row.source == EXTERNAL or row.point_event and row.start is not None and row.start == row.end:
            continue
        ordinal = len(rows)
        rows[ordinal] = row
        problems[ordinal] = _problems(row)
        if row.machine_ref is not None and _timed(row):
            machines.setdefault(row.machine_ref, []).append((ordinal, row))
        else:
            unplaced.append((ordinal, row))
    relevant, conflicted, scoped_conflicts, events = set(), set(), [], []
    ordered_machines = {}
    all_selected, machines_with_selected = set(), set()
    for ref, values in machines.items():
        ordered = sorted(values, key=lambda item: (item[1].start, item[1].end, item[1].sort_key))
        ordered_machines[ref] = ordered
        selected = {ordinal for ordinal, row in ordered if _selected(row, start, end, operations)}
        if selected:
            all_selected.update(selected)
            machines_with_selected.add(ref)
        relevant.update(selected)
        for (previous_ordinal, _previous), (_current_ordinal, _current) in zip(ordered, ordered[1:]):
            if _current_ordinal in selected:
                relevant.add(previous_ordinal)
        conflicts = _conflicts(ordered)
        for previous, current in conflicts:
            conflicted.update((previous[0], current[0]))
            if previous[0] in relevant or current[0] in relevant:
                scoped_conflicts.append((ref, previous, current))
    blocked = set()
    for ordinal, row in unplaced:
        # A timed future row cannot precede any next.start inside this window.
        if row.start is not None and end is not None and row.start >= end:
            continue
        selected_machine = row.machine_ref is None or row.machine_ref in machines_with_selected
        if _selected(row, start, end, operations) or selected_machine:
            relevant.add(ordinal)
            blocked.add(row.machine_ref)
    inconsistent = set()
    types = {}
    for row in rows.values():
        if row.machine_ref is not None and row.operation_ref is not None and row.type_ref:
            key = row.machine_ref, row.operation_ref
            types.setdefault(key, set()).add(row.type_ref)
    for key, values in types.items():
        if len(values) > 1:
            inconsistent.add(key)
    for ordinal, row in rows.items():
        if (row.machine_ref, row.operation_ref) in inconsistent:
            problems[ordinal].append({"code": "operation_type_inconsistent", "message": "同一永久工序的安排片段保存了不同工种身份，切换统计保留缺项。",
                                      "field": "type_ref", "machine_ref": row.machine_ref,
                                      "operation_ref": row.operation_ref, "row_ref": row.row_ref})
    for ref, ordered in ordered_machines.items():
        if None in blocked or ref in blocked:
            continue
        for sequence, (previous_entry, current_entry) in enumerate(zip(ordered, ordered[1:]), 1):
            previous_ordinal, previous = previous_entry
            current_ordinal, current = current_entry
            if current_ordinal not in all_selected:
                continue
            if problems[previous_ordinal] or problems[current_ordinal]:
                continue
            if type_transition(previous.type_ref, current.type_ref, previous.operation_ref, current.operation_ref) != 1:
                continue
            conflict = previous_ordinal in conflicted or current_ordinal in conflicted
            events.append(_event(ref, previous, current, sequence, conflict=conflict))
    events.sort(key=lambda item: (item["next_start"], item["machine_ref"], item["sequence"], item["next_row_ref"]))
    issues, seen = [], set()
    for ordinal in sorted(relevant):
        for item in problems[ordinal]:
            key = item["code"], item.get("row_ref"), item.get("operation_ref"), item.get("machine_ref")
            if key not in seen:
                issues.append(item)
                seen.add(key)
    for ref, previous, current in scoped_conflicts:
        issues.append({"code": "arrangement_conflict", "message": "设备上的不同工序安排重叠，工种切换统计附冲突状态。",
                       "machine_ref": ref, "previous_operation_ref": previous[1].operation_ref,
                       "next_operation_ref": current[1].operation_ref,
                       "previous_row_ref": previous[1].row_ref, "next_row_ref": current[1].row_ref})
    unknown = {ordinal for ordinal in relevant if problems[ordinal]}
    affected = unknown | (conflicted & relevant)
    complete = not affected
    state = "complete" if complete else "partial" if machines else "unavailable"
    unknown_geometry = any(item["field"] in ("source", "machine_ref", "operation_ref", "task_time")
                           for ordinal in unknown for item in problems[ordinal] if "field" in item)
    changed = len({event["machine_ref"] for event in events})
    return {"events": events, "count": len(events) if complete else None, "known_count": len(events),
            "changed_machine_count": changed if complete else None, "known_changed_machine_count": changed,
            "state": state, "unknown_count": len(affected),
            "conflict": True if scoped_conflicts else None if unknown_geometry else False,
            "conflict_count": len(scoped_conflicts), "issues": issues,
            "metric_version": "type_changeover_v1", "source": "saved_arrangement_sequence"}


def count_known_changeovers(by_machine) -> int:
    """Count known type transitions across internal machine sequences with the same validity rules as event projection."""
    total = 0
    for machine_ref, machine_rows in by_machine.items():
        if not machine_ref:
            continue
        timed = []
        types_by_op = {}
        blocked = False
        for row in machine_rows:
            start, end = row.start_time, row.end_time
            if start is not None and start == end:
                continue
            if start is None or end is None or not (start < end):
                blocked = True
                break
            timed.append(row)
            if row.op_id > 0 and row.op_type_id:
                types_by_op.setdefault(row.op_id, set()).add(row.op_type_id)
        if blocked or len(timed) < 2:
            continue
        inconsistent = {op_id for op_id, values in types_by_op.items() if len(values) > 1}
        timed.sort(key=lambda item: (item.start_time, item.end_time, item.op_id))
        for previous, current in zip(timed, timed[1:]):
            if previous.op_id <= 0 or current.op_id <= 0 or previous.op_id == current.op_id:
                continue
            if previous.op_id in inconsistent or current.op_id in inconsistent:
                continue
            if not previous.op_type_id or not current.op_type_id:
                continue
            if previous.op_type_id != current.op_type_id:
                total += 1
    return total
