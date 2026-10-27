"""Whole-draft precedence and occupied-resource checks, including outside scope."""

from collections import defaultdict
from datetime import datetime
from heapq import heappop, heappush

from core.models.workbench_trial import issue, reject
from core.services.scheduler.execution.execution_ledger_guard import is_point_work
from core.services.workbench.facts.zero_duration_evidence import trial_point_evidence

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


def relation_issues(rows, live):
    by_ref = {row["operation_ref"]: row for row in rows}
    issues = []
    for row in rows:
        for previous_ref in row["original"]["predecessor_operation_refs"]:
            problem = _predecessor_issue(row, previous_ref, by_ref.get(previous_ref), live)
            if problem is not None:
                issues.append(problem)
    return issues


def _predecessor_issue(row, previous_ref, previous, live):
    if previous is None:
        actual = live["execution"].get(previous_ref)
        if not actual or actual["execution_state"] != "complete" or not actual["confirmed_finish"]:
            return issue("predecessor_missing", "前一道工序不在这份草稿里，现场也没有它已确认完工的记录，系统定不了这道工序的开工时间。请把前一道工序也放进草稿。", row["task_ref"])
        end = actual["confirmed_finish"]
    else:
        end = previous["current"]["end"]
        if _same_merged_cycle(row, previous):
            if (previous["current"]["start"], end) != (row["current"]["start"], row["current"]["end"]):
                return issue("external_group_split", "合并外协组的工序必须保持同一周期。", row["task_ref"], previous["task_ref"])
            return None
    if datetime.fromisoformat(end) > datetime.fromisoformat(row["current"]["start"]):
        return issue("precedence_violation", "后序开工早于前序完工。", row["task_ref"], previous["task_ref"] if previous else None)
    return None


def _same_merged_cycle(row, previous):
    group = row["original"].get("external_group")
    prior_group = previous["original"].get("external_group")
    if not group or not prior_group:
        return False
    return (group["group_id"] == prior_group["group_id"] and group["merge_mode"] == "merged"
            and row["original"]["operation"]["piece_id"] == previous["original"]["operation"]["piece_id"])


def resource_issues(rows, live, *, conn):
    occupied = _trial_intervals(rows)
    issues = _outside_intervals(occupied, rows, live, conn=conn)
    issues.extend(_overlap_issues(occupied))
    issues.extend(_actual_reservations(rows, live))
    return issues


def _outside_intervals(occupied, rows, live, *, conn):
    issues = []
    selected = {row["operation_ref"] for row in rows}
    selected_op_ids = {row["original"]["operation"]["id"] for row in rows}
    refs = {int(row["source_key"]): row["ref"] for row in live["facts"]["tables"]["WorkbenchPlanSourceRefs"]
            if row["kind"] == "operation" and row["active"] == 1}
    latest, point_versions = {}, {}
    for row in sorted(live["facts"]["tables"]["Schedule"], key=lambda row: (row["version"], row["id"])):
        latest[row["op_id"]] = row
    for op_id, row in latest.items():
        ref = refs.get(op_id)
        if op_id in selected_op_ids or ref in selected:
            continue
        span, problem = _outside_occupancy(row, conn, point_versions)
        if problem is not None:
            issues.append(problem)
        if span is None:
            continue
        start, end = span
        for kind in ("machine", "operator"):
            if row[kind + "_id"] is not None:
                occupied[kind, row[kind + "_id"]].append((start, end, ref or op_id, None))
    return issues


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
        except WorkbenchCommandRejected:
            return None, issue("outside_scope_point_unproven", "范围外那道零工时工序没有可核对的依据。")
    try:
        return interval({"start": row["start_time"], "end": row["end_time"]}), None
    except (TypeError, ValueError):
        return None, issue("outside_scope_interval_invalid", "范围外正式安排的时间不对，判断不了设备人员有没有空。")


def _trial_intervals(rows):
    occupied = defaultdict(list)
    for row in rows:
        if row["original"]["operation"]["source"] != "internal":
            continue
        try:
            start, end = interval(row["current"], original=row["original"])
        except (TypeError, ValueError):
            continue
        if start == end:
            continue
        for kind in ("machine", "operator"):
            key = row["current"][kind + "_id"]
            if key is not None:
                occupied[kind, key].append((start, end, row["operation_ref"], row["task_ref"]))
    return occupied


def _overlap_issues(occupied):
    issues = []
    for (kind, _), intervals in occupied.items():
        if not any(task is not None for _, _, _, task in intervals):
            continue
        active, trial, expiry = {}, {}, []
        for index, (start, end, operation, task) in enumerate(sorted(intervals, key=lambda value: (value[0], value[1]))):
            while expiry and expiry[0][0] <= start:
                _, expired = heappop(expiry)
                active.pop(expired)
                trial.pop(expired, None)
            # Preserve chronological issue order, pairing outside work only with
            # trial work. Outside/outside overlaps do not belong to this check.
            for other_operation, other_task in (active if task is not None else trial).values():
                if operation != other_operation:
                    issues.append(issue(kind + "_overlap", "设备安排重叠。" if kind == "machine" else "人员安排重叠。",
                                        task or other_task, other_task if task else None))
                    _issue_limit(issues)
            active[index] = operation, task
            if task is not None:
                trial[index] = operation, task
            heappush(expiry, (end, index))
    return issues


def _actual_reservations(rows, live):
    index, issues = _actual_index(live)
    for row in rows:
        if row["original"]["operation"]["source"] != "internal":
            continue
        if row["current"]["start"] == row["current"]["end"]:
            # The row validator must prove the point before any save/adoption.
            continue
        row_start = datetime.fromisoformat(row["current"]["start"])
        row_end = datetime.fromisoformat(row["current"]["end"])
        for kind in ("machine", "operator"):
            for ref, execution, start_dt, end_dt in index[kind, row["current"][kind + "_ref"]]:
                if row["operation_ref"] == ref:
                    continue
                conflict = _actual_conflict(row, row_start, row_end, execution, start_dt, end_dt)
                if conflict:
                    issues.append(conflict)
                    _issue_limit(issues)
    return issues


def _actual_index(live):
    index, issues = defaultdict(list), []
    tables = live["facts"]["tables"]
    ops = {str(row["id"]): row for row in tables["BatchOperations"]}
    ops_by_ref = {row["ref"]: ops.get(row["source_key"], {}) for row in tables["WorkbenchPlanSourceRefs"]
                  if row["kind"] == "operation"}
    for ref, execution in live["execution"].items():
        reports = execution["reports"]
        if execution["execution_state"] == "unreported" and not reports:
            continue
        op = ops_by_ref.get(ref, {})
        if op.get("source") == "external":
            continue
        complete = execution["execution_state"] == "complete"
        # 与排产执行保护同一口径：零定额点工序的零时长报工合法，不占设备人员时段。
        is_point = is_point_work(op.get("source"), op.get("setup_hours"), op.get("unit_hours"),
                                 execution["target_quantity"])
        for report in reports:
            start_dt, end_dt = _actual_span(complete, report["actual_start"] or execution["first_actual_start"],
                                            report["actual_end"] or execution["confirmed_finish"])
            if is_point and report["effective_processing_hours"] == 0 and start_dt is not None and start_dt == end_dt:
                continue
            for kind in ("machine", "operator"):
                resource = report["actual_" + kind + "_ref"]
                if resource is None:
                    issues.append(_resource_unknown())
                else:
                    index[kind, resource].append((ref, execution, start_dt, end_dt))
    return index, issues


def _resource_unknown():
    return issue("execution_resource_unknown", "现场数据里没有设备人员编号，范围外的占用情况无法判断。")


def _actual_span(complete, start, end):
    # Only a confirmed whole-operation finish releases the resource at a known time.
    if not complete or not start or not end:
        return None, None
    return datetime.fromisoformat(start), datetime.fromisoformat(end)


def _actual_conflict(row, row_start, row_end, execution, start_dt, end_dt):
    # Partial report end is never whole-operation resource release.
    if execution["execution_state"] != "complete":
        return issue("execution_resource_release_unknown", "同一资源仍有未确认整道完工的实际生产，不能推测释放时间。", row["task_ref"])
    if start_dt is None or end_dt is None or end_dt <= start_dt:
        return issue("execution_resource_interval_unknown", "已有实际生产占用时间不完整，无法证明资源可用。", row["task_ref"])
    if start_dt < row_end and end_dt > row_start:
        return issue("execution_resource_overlap", "安排与真实生产资源占用重叠。", row["task_ref"])
    return None


def _issue_limit(issues):
    if len(issues) > _MAX_ISSUES:
        reject("validation_too_large", "真实冲突数量超过50000条，本次没有截断冲突或提交调整。", 413)
