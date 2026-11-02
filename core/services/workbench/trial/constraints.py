"""Whole-draft precedence and occupied-resource checks, including outside scope."""

from collections import defaultdict
from datetime import datetime
from heapq import heappop, heappush
from typing import Any, Dict, Mapping

from core.models.content import content_text
from core.models.workbench_trial import issue, reject
from core.services.execution.projection import is_point_work
from core.services.workbench.facts.zero_duration_evidence import trial_point_evidence

from .arrangements import same_arrangement
from .occupancy import ReportedExecution, arranged_occupancy, reported_archive

_MAX_ISSUES = 50000


def interval(value, *, original=None):
    start, end = datetime.fromisoformat(value["start"]), datetime.fromisoformat(value["end"])
    if start.tzinfo is not None or end.tzinfo is not None or end < start:
        raise ValueError("Invalid positive factory-local interval")
    if start == end:
        if original is None:
            raise ValueError("Equal interval lacks point evidence")
        trial_point_evidence(original, value)
    return start, end


def build_current_trial_spans(rows):
    """Each row's current interval and interval parse error, without execution occupancy."""
    current_by_op = {}
    current_by_row = {}
    current_errors_by_op = {}
    for row in rows:
        op_ref = row["operation_ref"]
        row_ref = row["row_ref"]
        try:
            curr_span = interval(row["current"], original=row["original"])
        except (TypeError, ValueError) as exc:
            curr_span = None
            current_errors_by_op[op_ref] = exc.with_traceback(None)
        if curr_span is not None:
            current_by_op[op_ref] = curr_span
        current_by_row[row_ref] = curr_span
    return {
        "current_by_op": current_by_op,
        "current_by_row": current_by_row,
        "current_errors_by_op": current_errors_by_op,
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
    original_by_row = {}
    original_by_source_row = {}
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
        else:
            try:
                orig_span = interval(orig_arr, original=original)
            except (TypeError, ValueError):
                orig_span = None
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
        "current_occupancy_by_row": current_occupancy,
        "original_occupancy_by_row": original_occupancy,
    }


def build_archived_trial_intervals(rows, *, execution: Mapping[str, Dict[str, Any]]):
    """Each row's current and original interval and occupancy from archived execution snapshots."""
    return build_trial_intervals(
        rows,
        reported={row["operation_ref"]: reported_archive(execution[row["operation_ref"]]) for row in rows},
    )


def relation_issues(rows, live, *, trial_intervals):
    by_ref = {row["operation_ref"]: row for row in rows}
    current_by_op = trial_intervals["current_by_op"]
    issues = []
    for row in rows:
        for previous_ref in row["original"]["predecessor_operation_refs"]:
            problem = _predecessor_issue(row, previous_ref, by_ref.get(previous_ref), live, current_by_op)
            if problem is not None:
                issues.append(problem)
    return issues


def _predecessor_issue(row, previous_ref, previous, live, current_by_op):
    if previous is None:
        reported_prev = live["execution_reported"][previous_ref]
        if reported_prev.execution["execution_state"] != "complete":
            return issue("predecessor_missing", "前一道工序不在这份草稿里，现场也没有它已确认完工的记录，系统定不了这道工序的开工时间。请把前一道工序也放进草稿。", row["task_ref"])
        end_dt = reported_prev.seed[1]
    else:
        end = previous["current"]["end"]
        if _same_merged_cycle(row, previous):
            if (previous["current"]["start"], end) != (row["current"]["start"], row["current"]["end"]):
                return issue("external_group_split", "合并外协组的工序必须保持同一周期。", row["task_ref"], previous["task_ref"])
            return None
        prev_span = current_by_op.get(previous_ref)
        if prev_span is None:
            return None
        end_dt = prev_span[1]
    curr_span = current_by_op.get(row["operation_ref"])
    if curr_span is None:
        return None
    start_dt = curr_span[0]
    if end_dt > start_dt:
        return issue("precedence_violation", "后序开工早于前序完工。", row["task_ref"], previous["task_ref"] if previous else None)
    return None


def _same_merged_cycle(row, previous):
    group = row["original"].get("external_group")
    prior_group = previous["original"].get("external_group")
    if not group or not prior_group:
        return False
    return (group["group_id"] == prior_group["group_id"] and group["merge_mode"] == "merged"
            and row["original"]["operation"]["piece_id"] == previous["original"]["operation"]["piece_id"])


def resource_issues(rows, live, *, conn, trial_intervals):
    """trial_intervals are the rows' live intervals.

    每种资源只做一次时间扫描，参与扫描的有试调行的现场占用、范围外工作（完成的按真实分段，其余按最新正式安排）、
    其他完成内部工序的真实分段；未完成的真实生产，以及区间无法证明的完成报工，会让同资源的试调行不论时间一律阻断；
    问题按内容只计一次，超过 _MAX_ISSUES 条返回 413。
    """
    found = {}

    def add(item):
        key = content_text(item)
        if key not in found:
            found[key] = item
            if len(found) > _MAX_ISSUES:
                reject("validation_too_large", "真实冲突数量超过50000条，本次没有截断冲突或提交调整。", 413)

    occupancy = trial_intervals["current_occupancy_by_row"]
    reported = live["execution_reported"]
    ids = {(kind, ref): key for (kind, key), ref in live["preflight_facts"].refs.items()}
    actual, release, unproven = _execution_occupancy(rows, live, reported, ids, add)
    occupied = _trial_intervals(rows, occupancy, actual, ids)
    placed = _outside_intervals(occupied, rows, live, reported, ids, add, conn=conn)
    _actual_intervals(occupied, reported, actual, placed, ids)
    _overlap_issues(occupied, add)
    _unproven_issues(rows, occupancy, release, unproven, add)
    return list(found.values())


def _archived_operations(rows, live):
    archived = {row["operation_ref"]: row["original"]["operation"] for row in rows}
    origin = live["origin"]
    for ref, member in origin.unarranged.items():
        archived.setdefault(ref, member["operation"])
    if origin.facts is not None:
        ops = origin.facts.tables["BatchOperations"]
        for op_id, ref in origin.facts.operation_refs.items():
            if op_id in ops:
                archived.setdefault(ref, ops[op_id])
    tables = origin.admission["facts"]["tables"]
    ops = {row["id"]: row for row in tables["BatchOperations"]}
    for item in tables["WorkbenchPlanSourceRefs"]:
        if item["kind"] == "operation" and item["active"] == 1:
            op = ops.get(int(item["source_key"]))
            if op is not None:
                archived.setdefault(item["ref"], op)
    return archived


def _execution_occupancy(rows, live, reported, ids, add):
    """Every live operation's real production on internal resources, from its one parse.

    Returns the completed operations, whose positive segments occupy their resources, and per permanent
    resource the operations still unfinished on it (release unknown) or completed there with an interval
    that cannot be proven.
    """
    operations = live["execution_operations"]
    archived = None
    actual, release, unproven = set(), defaultdict(set), defaultdict(set)
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
        if source == "internal":
            # 与排产执行保护同一口径：零定额点工序的零时长报工合法，不占设备人员时段。
            point = is_point_work(source, op["setup_hours"], op["unit_hours"], execution["target_quantity"])
        else:
            point = False
        complete = execution["execution_state"] == "complete"
        if complete:
            actual.add(ref)
        for report, span in parsed.spans:
            if complete and point and report["effective_processing_hours"] == 0 and span[0] == span[1]:
                continue
            for kind in ("machine", "operator"):
                resource = report["actual_" + kind + "_ref"]
                if resource is None:
                    add(_retired_source_unknown() if source is None else _resource_unknown())
                elif (kind, resource) not in ids:
                    add(_resource_unknown())
                elif not complete:
                    release[kind, resource].add(ref)
                elif span[1] <= span[0]:
                    unproven[kind, resource].add(ref)
    return actual, release, unproven


def _identified(segments, arrangement, ids):
    """Occupancy keyed by business identity, as the overlap check groups resources.

    The arrangement keeps its own identities; any other reported resource is resolved through the live
    permanent references.
    """
    result = []
    for start, end, *refs in segments:
        keys = []
        for kind, ref in zip(("machine", "operator"), refs):
            if arrangement is not None and ref == arrangement[kind + "_ref"]:
                key = arrangement[kind + "_id"]
            else:
                key = ids.get((kind, ref))
            keys.append(key)
        result.append((start, end, *keys))
    return result


def _outside_intervals(occupied, rows, live, reported, ids, add, *, conn):
    """Completed outside work occupies its actual report segments; other outside work its latest official row.

    Returns the operations placed by their actual segments.
    """
    placed = set()
    selected = {row["operation_ref"] for row in rows}
    refs = live["preflight_facts"].operation_refs
    operations = live["execution_operations"]
    latest, point_versions = {}, {}
    for row in sorted(live["facts"]["tables"]["Schedule"], key=lambda row: (row["version"], row["id"])):
        latest[row["op_id"]] = row
    for op_id, row in latest.items():
        ref = refs[op_id]
        if ref in selected:
            continue
        if operations[ref]["source"] == "external":
            continue
        parsed = reported[ref]
        if parsed.execution["execution_state"] == "complete":
            segments = _identified(parsed.segments, None, ids)
            role = "outside_actual"
            placed.add(ref)
        else:
            span, problem = _outside_occupancy(row, conn, point_versions)
            if problem is not None:
                add(problem)
            if span is None:
                continue
            segments = ((*span, row["machine_id"], row["operator_id"]),)
            role = "outside"
        _occupy(occupied, segments, ref, None, role)
    return placed


def _actual_intervals(occupied, reported, actual, placed, ids):
    """Completed internal operations not placed as outside work occupy their actual segments.

    These are the selected rows' own actual segments (still on their seed or moved off it) and completed
    operations without an official row. A selected row still on its seed is scanned as its trial record
    and this actual one; the same operation never pairs with itself.
    """
    for ref, parsed in reported.items():
        if ref in actual and ref not in placed:
            _occupy(occupied, _identified(parsed.segments, None, ids), ref, None, "actual")


def _occupy(occupied, segments, operation, task, role):
    for start, end, machine_id, operator_id in segments:
        for kind, key in (("machine", machine_id), ("operator", operator_id)):
            if key is not None:
                occupied[kind, key].append((start, end, operation, task, role))


def _outside_occupancy(row, conn, point_versions):
    """A proven point occupies nothing; an unproven interval reports a blocker."""
    if row["start_time"] == row["end_time"]:
        from core.models.workbench_command import WorkbenchCommandRejected
        from core.services.workbench.plan.point_evidence import official_point_work

        try:
            if row["version"] not in point_versions:
                point_versions[row["version"]] = official_point_work(conn, row["version"])
            if row["op_id"] in point_versions[row["version"]]:
                return None, None
        except WorkbenchCommandRejected as exc:
            # 读取容量超限是整个请求的 413，不是这道工序“没有依据”。
            if exc.status == 413:
                raise
            return None, issue("outside_scope_point_unproven", "范围外那道零工时工序没有可核对的依据。")
    try:
        return interval({"start": row["start_time"], "end": row["end_time"]}), None
    except (TypeError, ValueError):
        return None, issue("outside_scope_interval_invalid", "范围外正式安排的时间不对，判断不了设备人员有没有空。")


def _trial_intervals(rows, occupancy, actual, ids):
    occupied = defaultdict(list)
    for row in rows:
        if row["original"]["operation"]["source"] == "internal":
            arrangement = None if row["operation_ref"] in actual else row["current"]
            segments = _identified(occupancy.get(row["row_ref"], ()), arrangement, ids)
            _occupy(occupied, segments, row["operation_ref"], row["task_ref"], None)
    return occupied


def _overlap_issues(occupied, add):
    for (kind, _), intervals in occupied.items():
        if not any(task is not None for _, _, _, task, _ in intervals):
            continue
        active, trial, expiry = {}, {}, []
        for index, (start, end, operation, task, role) in enumerate(
                sorted(intervals, key=lambda value: (value[0], value[1]))):
            while expiry and expiry[0][0] <= start:
                _, expired = heappop(expiry)
                active.pop(expired)
                trial.pop(expired, None)
            # Preserve chronological issue order, pairing outside work and real production only with
            # trial work. Overlaps among them do not belong to this check.
            for other_operation, other_task, other_role in (active if task is not None else trial).values():
                if operation != other_operation:
                    # The non-trial side's role (None when both are trial rows) decides what the overlap is:
                    # an arrangement, real production, or a completed outside operation that is both.
                    held = role if task is None else other_role
                    if held != "actual":
                        add(issue(kind + "_overlap", "设备安排重叠。" if kind == "machine" else "人员安排重叠。",
                                  task or other_task, other_task if task else None))
                    if held in ("outside_actual", "actual"):
                        add(issue("execution_resource_overlap", "安排与真实生产资源占用重叠。", task or other_task))
            active[index] = operation, task, role
            if task is not None:
                trial[index] = operation, task, role
            heappush(expiry, (end, index))


def _unproven_issues(rows, occupancy, release, unproven, add):
    """A trial row on a resource another operation holds without a provable interval is blocked whatever its time.

    Partial report end is never whole-operation resource release.
    """
    checks = ((release, "execution_resource_release_unknown", "同一资源仍有未确认整道完工的实际生产，不能推测释放时间。"),
              (unproven, "execution_resource_interval_unknown", "已有实际生产占用时间不完整，无法证明资源可用。"))
    for row in rows:
        if row["original"]["operation"]["source"] != "internal":
            continue
        for _, _, *refs in occupancy.get(row["row_ref"], ()):
            for kind, resource in zip(("machine", "operator"), refs):
                for holders_by_resource, code, message in checks:
                    holders = holders_by_resource.get((kind, resource))
                    if holders and (len(holders) > 1 or row["operation_ref"] not in holders):
                        add(issue(code, message, row["task_ref"]))


def _resource_unknown():
    return issue("execution_resource_unknown", "现场数据里没有设备人员编号，范围外的占用情况无法判断。")


def _retired_source_unknown():
    return issue("execution_operation_source_unknown", "已删除工序缺少原工艺来源，无法判断未填设备人员的报工是否占用内部资源。")
