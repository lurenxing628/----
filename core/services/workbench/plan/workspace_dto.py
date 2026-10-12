"""Compose public projections and keep their snapshot evidence off the wire."""

from core.models.workbench_command import WorkbenchCommandRejected

from .baseline import build_plan_baseline
from .calendar import project_plan_calendar
from .delivery import read_plan_delivery
from .occupancy import project_plan_occupancy
from .process_order import project_process_order


def resource_directory(rows, resources, *, tasks=None, baseline=None, archived=()):
    directory = {}
    for row in rows:
        for kind in ("machine", "operator", "supplier"):
            key = row[kind + "_id"]
            if key in (None, ""):
                continue
            identity = resources[kind][str(key)]
            label = row[kind + "_name"]
            if label is not None and (type(label) is not str or not label.strip()):
                raise WorkbenchCommandRejected("plan_unavailable", "设备或人员名称无效，请到资料总览补填。")
            value = {"kind": kind, "ref": identity.ref, "business_code": identity.entity_key, "label": label}
            previous = directory.setdefault((kind, identity.ref), value)
            if previous != value:
                raise WorkbenchCommandRejected("plan_unavailable", "同一台设备或同一个人员有两套名称或编号，对不上。请到资料总览核对。")
    if tasks is not None:
        compared = [task for item in (baseline or {}).get("items", []) for task in (item["before"], item["after"]) if task is not None]
        used = {(kind, task[kind + "_ref"]) for task in list(tasks) + compared for kind in ("machine", "operator", "supplier")
                if task[kind + "_ref"] is not None}
        for row in archived:
            directory.setdefault((row["kind"], row["ref"]), row)
        if not used <= set(directory):
            raise WorkbenchCommandRejected("plan_unavailable", "安排引用的资源缺少可核对的来源目录，请核对原采用记录。")
        directory = {key: value for key, value in directory.items() if key in used}
    return [directory[key] for key in sorted(directory)]


def workspace_projections(conn, *, entry, scope, rows, resources, plan_span, logger=None):
    baseline, baseline_facts = build_plan_baseline(conn, entry=entry, scope=scope, selected_rows=rows)
    arguments = dict(entry=entry, scope=scope, rows=rows, resources=resources, plan_span=plan_span)
    calendar, calendar_facts = project_plan_calendar(conn, **arguments)
    occupancy, occupancy_facts = project_plan_occupancy(conn, calendar_facts=calendar_facts, **arguments)
    delivery, delivery_facts = read_plan_delivery(conn, scope=scope, identity=entry.plan_identity, logger=logger)
    known = sum(item["risk"] != "unknown" for item in delivery["items"])
    delivery = dict(delivery, state="available" if known == len(delivery["items"]) else "partial" if known else "unavailable")
    process_order, process_facts, gantt_graph = project_process_order(conn, plan_ref=scope.plan_ref)
    provenance = baseline_facts.get("provenance") or {
        "state": "unavailable", "reason": baseline.get("reason") or "此计划未记录可核对的生成来源。",
        "source_kind": None, "source_ref": None, "source_label": None, "run_ref": None,
        "accepted_at": None, "finished_at": None, "adopted_at": None, "algorithm": None, "baseline": None,
    }
    public = {"baseline": baseline, "calendar": calendar, "occupancy": occupancy,
              "delivery_risks": delivery, "process_order": process_order}
    facts = {"baseline": baseline_facts, "calendar": calendar_facts,
             "occupancy": occupancy_facts, "delivery_risks": delivery_facts, "process_order": process_facts}
    return public, facts, gantt_graph, provenance
