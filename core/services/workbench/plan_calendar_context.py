"""Shared selected-plan admission and public issue vocabulary."""

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_plan_scope import MAX_PLAN_TASKS

from .plan_calendar_intervals import instant
from .plan_fact_serialization import plain_plan_facts
from .plan_point_evidence import annotate_plan_points
from .zero_duration_evidence import overlaps

_MESSAGES = {
    "calendar_invalid": "日历或人员轮班资料无效，相关容量无法核实。",
    "calendar_range_limit": "日历范围超过有界读取上限，请缩小时间范围。",
    "calendar_cell_limit": "资源与日期组合超过有界计算上限，请缩小时间范围。",
    "calendar_fact_limit": "相关日历或资源事实超过读取上限，未返回截断容量。",
    "calendar_window_limit": "班次超过本投影支持的24小时窗口，相关容量无法核实。",
    "resource_missing": "安排关联的资源记录缺失，容量无法核实。",
    "resource_status_unknown": "资源启停状态未知，未按启用或零容量处理。",
    "downtime_invalid": "设备停机时间或状态无效，容量无法核实。",
    "calendar_unavailable": "日历容量无法核实，安排工时与时间冲突仍单独显示。",
    "assignment_source_unknown": "安排的自制或外协来源不明，未推算内部资源占用。",
    "assignment_resource_missing": "自制安排缺少设备或人员，无法确认资源约束。",
    "assignment_priority_unknown": "安排的优先级未知，无法确认普通或急件日历许可。",
    "assignment_resource_inactive": "安排使用了未启用的设备或人员。",
    "assignment_work_type_unknown": "安排或设备的真实工种资料缺失，无法确认工种匹配。",
    "assignment_work_type_mismatch": "安排与设备的自制工种不匹配。",
    "assignment_qualification_invalid": "人员技能或授权资料无效，无法确认安排资格。",
    "assignment_not_authorized": "人员没有该设备的操作授权。",
    "assignment_not_qualified": "人员未登记该自制工种的资格。",
    "assignment_calendar_unavailable": "安排所需日历容量无法核实，未将缺失时数记为零。",
    "assignment_outside_calendar": "安排有时段不满足相应优先级的资源日历或设备停机约束。",
    "assignment_machine_downtime": "安排与设备的有效停机时段重叠。",
}


def issue(code, **fields):
    return dict(code=code, message=_MESSAGES[code], **fields)


def require_snapshot(conn):
    if not conn.in_transaction:
        raise RuntimeError("Plan projections require a caller-owned read transaction.")


def selected_context(conn, entry, scope, rows, resources, plan_span):
    require_snapshot(conn)
    if len(rows) > MAX_PLAN_TASKS:
        raise WorkbenchCommandRejected("query_too_large", "计划投影超过10000条安排上限，未返回截断数据。", 413)
    if not entry.can_view or entry.plan_identity is None:
        raise WorkbenchCommandRejected("plan_unavailable", "计划身份不可查看，未替换目标。")
    time_scope = scope.time_scope(plan_span)
    start, end = instant(time_scope["range_start"]), instant(time_scope["range_end"])
    if start > end or (start == end and scope.range_start is not None):
        raise WorkbenchCommandRejected("plan_unavailable", "计划投影时间范围无效。")
    selected = _selected_rows(conn, entry, scope, rows, start, end)
    binding = _context_binding(entry, scope, selected, resources, time_scope)
    return selected, start, end, time_scope, input_fingerprint(plain_plan_facts(binding))


def _selected_rows(conn, entry, scope, rows, start, end):
    selected, unique = [], {}
    for original in annotate_plan_points(conn, rows, source_table=entry.plan_identity.source_table):
        row, low, high = _validated_row(original, entry.locator.version)
        key = row["schedule_id"]
        if key in unique and unique[key] != row:
            raise WorkbenchCommandRejected("plan_unavailable", "同一安排出现不同事实，无法去重。")
        if key not in unique and (scope.range_start is None or overlaps(low, high, start, end)):
            selected.append(row)
        unique[key] = row
    return selected


def _validated_row(original, version):
    row = dict(original)
    if row["version"] != version:
        raise WorkbenchCommandRejected("plan_unavailable", "安排版本与已选计划不一致。")
    low, high = instant(row["start_time"]), instant(row["end_time"])
    if low > high or (low == high and not row.get("_point_work")):
        raise WorkbenchCommandRejected("plan_unavailable", "安排时间无效，未返回替代占用。")
    return row, low, high


def _context_binding(entry, scope, selected, resources, time_scope):
    refs = {kind: [(str(key), value.ref, value.revision) for key, value in sorted(mapping.items())]
            for kind, mapping in resources.items() if kind in ("machine", "operator")}
    identity = entry.plan_identity
    return {"version": entry.locator.version, "role": entry.locator.plan_role,
               "scenario_id": entry.locator.scenario_id, "source_table": identity.source_table,
               "candidate_id": identity.candidate_id, "scope": scope.scope(), "time_scope": time_scope,
               "rows": sorted(({key: value for key, value in row.items() if key != "_point_work"}
                               for row in selected), key=lambda row: row["schedule_id"]), "refs": refs}


def resource_ids(rows, kind):
    return sorted({str(row[kind + "_id"]) for row in rows if (row.get("_point_work") or
                   str(row["source"]).strip().lower() == "internal") and row[kind + "_id"] not in (None, "")})


def public_resource(kind, key, identities, raw):
    identity = identities.get(kind, {}).get(key)
    if identity is None:
        raise WorkbenchCommandRejected("identity_missing", "安排资源永久引用缺失，读取不会补建。")
    return {"kind": kind, "resource_ref": identity.ref, "label": raw["name"] if raw is not None else None}
