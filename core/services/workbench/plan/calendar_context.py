"""Shared selected-plan admission and public resource identities."""

from collections import namedtuple

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity.plan_calendar_intervals import instant
from core.services.workbench.facts.plan_serialization import plain_plan_facts
from core.services.workbench.facts.zero_duration_evidence import overlaps

from .point_evidence import annotate_plan_points

SelectedPlanContext = namedtuple("SelectedPlanContext", "rows start end time_scope binding")


def require_snapshot(conn):
    if not conn.in_transaction:
        raise RuntimeError("Plan projections require a caller-owned read transaction.")


def selected_context(conn, entry, scope, rows, resources, plan_span, *, read_context=None):
    require_snapshot(conn)
    if not entry.can_view or entry.plan_identity is None:
        raise WorkbenchCommandRejected("plan_unavailable", "所选计划暂不可用，请刷新列表后重新选择。")
    time_scope = scope.time_scope(plan_span)
    start, end = instant(time_scope["range_start"]), instant(time_scope["range_end"])
    if start > end or (start == end and scope.range_start is not None):
        raise WorkbenchCommandRejected("plan_unavailable", "查询的时间范围无效。请重新选择起止日期。")
    selected = _selected_rows(conn, entry, scope, rows, start, end, read_context=read_context)
    binding = _context_binding(entry, scope, selected, resources, time_scope)
    return SelectedPlanContext(selected, start, end, time_scope, plain_plan_facts(binding))


def _selected_rows(conn, entry, scope, rows, start, end, *, read_context):
    selected, unique = [], {}
    prepared = rows if read_context is not None else annotate_plan_points(conn, rows)
    times = read_context.datetime_intervals(entry) if read_context is not None else None
    for original in prepared:
        if times is None:
            row, low, high = _validated_row(original, entry.locator.version)
        else:
            row = original
            low, high = times[row["schedule_id"]]
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
        raise WorkbenchCommandRejected("plan_unavailable", "工序安排的起止时间无效，请核对计划资料。")
    return row, low, high


def _context_binding(entry, scope, selected, resources, time_scope):
    refs = {kind: [(str(key), value.ref, value.revision) for key, value in sorted(mapping.items())]
            for kind, mapping in resources.items() if kind in ("machine", "operator")}
    identity = entry.plan_identity
    return {"version": entry.locator.version, "role": entry.locator.plan_role,
               "source_table": identity.source_table, "scope": scope.scope(), "time_scope": time_scope,
               "rows": sorted(({key: value for key, value in row.items() if key != "_point_work"}
                               for row in selected), key=lambda row: row["schedule_id"]), "refs": refs}


def resource_ids(rows, kind):
    return sorted({str(row[kind + "_id"]) for row in rows if (row.get("_point_work") or
                   str(row["source"]).strip().lower() == "internal") and row[kind + "_id"] not in (None, "")})


def public_resource(kind, key, identities, raw):
    identity = identities.get(kind, {}).get(key)
    if identity is None:
        raise WorkbenchCommandRejected("identity_missing", "安排关联的设备或人员编号缺失，请到资料总览核对。")
    return {"kind": kind, "resource_ref": identity.ref, "label": raw["name"] if raw is not None else None}
