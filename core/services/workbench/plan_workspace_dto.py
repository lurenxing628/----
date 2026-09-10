"""Compose public projections and keep their snapshot evidence off the wire."""

from core.models.workbench_command import WorkbenchCommandRejected

from .plan_baseline import build_plan_baseline
from .plan_calendar import project_plan_calendar
from .plan_delivery import read_plan_delivery
from .plan_occupancy import project_plan_occupancy
from .plan_process_order import project_process_order


def resource_directory(rows, resources):
    directory = {}
    for row in rows:
        for kind in ("machine", "operator", "supplier"):
            key = row[kind + "_id"]
            if key in (None, ""):
                continue
            identity = resources[kind][str(key)]
            label = row[kind + "_name"]
            if label is not None and (type(label) is not str or not label.strip()):
                raise WorkbenchCommandRejected("plan_unavailable", "资源名称无效，未用内部编号替代名称。")
            value = {"kind": kind, "ref": identity.ref, "business_code": identity.entity_key, "label": label}
            previous = directory.setdefault((kind, identity.ref), value)
            if previous != value:
                raise WorkbenchCommandRejected("plan_unavailable", "同一资源存在不一致的名称或业务编号。")
    return [directory[key] for key in sorted(directory)]


def workspace_projections(conn, *, entry, scope, rows, resources, plan_span, logger=None):
    baseline, baseline_facts = build_plan_baseline(conn, entry=entry, scope=scope, selected_rows=rows)
    arguments = dict(entry=entry, scope=scope, rows=rows, resources=resources, plan_span=plan_span)
    calendar, calendar_facts = project_plan_calendar(conn, **arguments)
    occupancy, occupancy_facts = project_plan_occupancy(conn, calendar_facts=calendar_facts, **arguments)
    delivery, delivery_facts = read_plan_delivery(conn, scope=scope, identity=entry.plan_identity, logger=logger)
    known = sum(item["risk"] != "unknown" for item in delivery["items"])
    delivery = dict(delivery, state="available" if known == len(delivery["items"]) else "partial" if known else "unavailable")
    process_order, process_facts = project_process_order(conn, plan_ref=scope.plan_ref)
    public = {"baseline": baseline, "calendar": calendar, "occupancy": occupancy,
              "delivery_risks": delivery, "process_order": process_order}
    facts = {"baseline": baseline_facts, "calendar": calendar_facts,
             "occupancy": occupancy_facts, "delivery_risks": delivery_facts, "process_order": process_facts}
    return public, facts
