"""Shared selected-plan admission and public resource identities."""

from collections import namedtuple

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity.plan_calendar_intervals import instant

SelectedPlanContext = namedtuple("SelectedPlanContext", "rows start end time_scope binding")


def require_snapshot(conn):
    if not conn.in_transaction:
        raise RuntimeError("Plan projections require a caller-owned read transaction.")


def selected_context(conn, entry, scope, rows, resources, plan_span):
    require_snapshot(conn)
    time_scope = scope.time_scope(plan_span)
    start, end = instant(time_scope["range_start"]), instant(time_scope["range_end"])
    binding = _context_binding(entry, scope, rows, resources, time_scope)
    return SelectedPlanContext(rows, start, end, time_scope, binding)


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
