"""Shared selected-plan admission and public issue vocabulary."""

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_plan_scope import MAX_PLAN_TASKS

from .plan_calendar_intervals import instant
from .plan_fact_serialization import plain_plan_facts
from .plan_point_evidence import annotate_plan_points
from .zero_duration_evidence import overlaps

_MESSAGES = {
    "calendar_invalid": "工作日历或人员班表有误，这部分产能算不出来。请到工作日历核对。",
    "calendar_range_limit": "查询的日期范围太大，班表读不完。请缩小时间范围后重试。",
    "calendar_cell_limit": "设备人员和日期的组合太多，算不完。请缩小时间范围后重试。",
    "calendar_fact_limit": "要读的班表或设备人员记录超过上限，没有读取，也不会只给一部分产能。请缩小时间范围后重试。",
    "calendar_window_limit": "班次时长超过 24 小时，这部分产能算不出来。请到工作日历核对班次。",
    "resource_missing": "这条安排关联的设备或人员记录找不到，产能算不出来。请到资料总览核对。",
    "resource_status_unknown": "设备或人员是启用还是停用读不出来，系统不会替你猜。请到资料总览核对。",
    "downtime_invalid": "设备停机时间或状态有误，产能算不出来。请到资料总览核对设备停机。",
    "calendar_unavailable": "工作日历产能算不出来；工时和时间冲突还是照常显示。",
    "assignment_source_unknown": "这条安排是自制还是外协分不清，系统不猜设备人员占用。请到基础资料核对工序归属。",
    "assignment_resource_missing": "自制安排没有填设备或人员，确认不了会不会冲突。请到基础资料补齐。",
    "assignment_priority_unknown": "这条安排的优先级读不出来，分不清按普通还是急件的班表算。请到批次管理核对优先级。",
    "assignment_resource_inactive": "这条安排用到了未启用的设备或人员。请改派，或到资料总览把它启用。",
    "assignment_work_type_unknown": "这条安排或设备的工种资料缺失，确认不了工种对不对得上。请到资料总览补齐工种。",
    "assignment_work_type_mismatch": "这条安排的自制工种和设备的工种对不上。请改派设备，或到资料总览核对工种。",
    "assignment_qualification_invalid": "人员的技能或设备授权资料有误，确认不了能不能干这道工序。请到资料总览核对。",
    "assignment_not_authorized": "这个人员没有该设备的操作授权。请改派人员，或到资料总览补授权。",
    "assignment_not_qualified": "这个人员没有登记该自制工种的资格。请改派人员，或到资料总览补资格。",
    "assignment_calendar_unavailable": "这条安排要用的班表产能算不出来，系统不会把缺的工时当 0。请到工作日历核对。",
    "assignment_outside_calendar": "这条安排有时段落在设备人员的班表外，或者撞上设备停机。请到工作日历和资料总览核对。",
    "assignment_machine_downtime": "这条安排和设备的停机时段重叠。请改期，或到资料总览核对设备停机。",
}


def issue(code, **fields):
    return dict(code=code, message=_MESSAGES[code], **fields)


def require_snapshot(conn):
    if not conn.in_transaction:
        raise RuntimeError("Plan projections require a caller-owned read transaction.")


def selected_context(conn, entry, scope, rows, resources, plan_span):
    require_snapshot(conn)
    if len(rows) > MAX_PLAN_TASKS:
        raise WorkbenchCommandRejected("query_too_large", "这个计划超过 10000 条安排上限，没有读取，也不会只给一部分。请缩小时间范围后重试。", 413)
    if not entry.can_view or entry.plan_identity is None:
        raise WorkbenchCommandRejected("plan_unavailable", "所选计划现在不能查看，系统不会自动换成别的计划。请刷新计划列表后重新选择。")
    time_scope = scope.time_scope(plan_span)
    start, end = instant(time_scope["range_start"]), instant(time_scope["range_end"])
    if start > end or (start == end and scope.range_start is not None):
        raise WorkbenchCommandRejected("plan_unavailable", "查询的时间范围无效。请重新选择起止日期。")
    selected = _selected_rows(conn, entry, scope, rows, start, end)
    binding = _context_binding(entry, scope, selected, resources, time_scope)
    return selected, start, end, time_scope, input_fingerprint(plain_plan_facts(binding))


def _selected_rows(conn, entry, scope, rows, start, end):
    selected, unique = [], {}
    for original in annotate_plan_points(conn, rows, source_table=entry.plan_identity.source_table):
        row, low, high = _validated_row(original, entry.locator.version)
        key = row["schedule_id"]
        if key in unique and unique[key] != row:
            raise WorkbenchCommandRejected("plan_unavailable", "同一条安排读到了两份不一样的数据，算不出实际占用。请刷新后重试。")
        if key not in unique and (scope.range_start is None or overlaps(low, high, start, end)):
            selected.append(row)
        unique[key] = row
    return selected


def _validated_row(original, version):
    row = dict(original)
    if row["version"] != version:
        raise WorkbenchCommandRejected("plan_unavailable", "这条安排不属于所选计划的这一版。请刷新后重试。")
    low, high = instant(row["start_time"]), instant(row["end_time"])
    if low > high or (low == high and not row.get("_point_work")):
        raise WorkbenchCommandRejected("plan_unavailable", "这条安排的时间无效，系统不会用别的时间顶替。请到计划甘特核对。")
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
        raise WorkbenchCommandRejected("identity_missing", "这条安排的设备或人员找不到编号，系统不会自动补建。请到资料总览核对。")
    return {"kind": kind, "resource_ref": identity.ref, "label": raw["name"] if raw is not None else None}
