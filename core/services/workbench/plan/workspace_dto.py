"""Compose public projections and keep their snapshot evidence off the wire."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.gantt_graph import project_scoped_gantt_graph

from .baseline import build_plan_baseline
from .calendar import project_plan_calendar
from .delivery import read_plan_delivery
from .occupancy import project_plan_occupancy
from .process_order import project_process_order


def resource_directory(rows, resources, *, tasks, baseline=None, compared_tasks=(), archived=()):
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
    compared = list(compared_tasks) or [
        task for item in (baseline or {}).get("items", [])
        for task in (item["before"], item["after"]) if task is not None
    ]
    used = {(kind, task[kind + "_ref"]) for task in list(tasks) + compared for kind in ("machine", "operator", "supplier")
            if task.get(kind + "_ref") is not None}
    for row in archived:
        directory.setdefault((row["kind"], row["ref"]), row)
    if not used <= set(directory):
        raise WorkbenchCommandRejected("plan_unavailable", "安排引用的资源缺少可核对的来源目录，请核对原采用记录。")
    directory = {key: value for key, value in directory.items() if key in used}
    return [directory[key] for key in sorted(directory)]


def summarize_gantt_graph(gantt_graph: dict, *, include_nodes: bool = False) -> dict:
    if gantt_graph.get("state") != "available":
        return {
            "state": "unavailable",
            "reason": gantt_graph.get("reason"),
            "scope": gantt_graph.get("scope", "full_plan"),
            "nodes": [],
            "node_count": 0,
            "nodes_complete": False,
            "critical_task_refs": [],
            "critical_edges": [],
        }
    count = len(gantt_graph["nodes"])
    if include_nodes:
        return {
            "state": "available",
            "reason": None,
            "scope": gantt_graph.get("scope", "full_plan"),
            "nodes": gantt_graph["nodes"],
            "node_count": count,
            "nodes_complete": True,
            "critical_task_refs": gantt_graph["critical_task_refs"],
            "critical_edges": gantt_graph["critical_edges"],
        }
    return {
        "state": "available",
        "reason": None,
        "scope": gantt_graph.get("scope", "full_plan"),
        "nodes": [],
        "node_count": count,
        "nodes_complete": count == 0,
        "critical_task_refs": [],
        "critical_edges": [],
    }


def workspace_projections(
    conn,
    *,
    entry,
    scope,
    resources,
    plan_span,
    logger,
    context,
    include_baseline_items=False,
    include_gantt_graph=False,
    include_capacity_details=False,
):
    baseline, baseline_facts = build_plan_baseline(
        conn, entry=entry, scope=scope, context=context, include_items=include_baseline_items,
    )
    selected = context.calendar_selection(entry, scope, resources, plan_span)
    calendar, calendar_facts = project_plan_calendar(
        conn, scope=scope, resources=resources, selected=selected, include_windows=include_capacity_details,
    )
    occupancy, _ = project_plan_occupancy(
        scope=scope, resources=resources, calendar_facts=calendar_facts, selected=selected,
        include_segments=include_capacity_details,
    )
    delivery, delivery_facts = read_plan_delivery(conn, scope=scope, identity=entry.plan_identity, logger=logger, context=context)
    state = delivery["summary"]["state"]
    delivery = dict(delivery, state="available" if state == "complete" else state)
    process_order, _, gantt_graph = project_process_order(conn, plan_ref=scope.plan_ref, context=context)
    if scope.range_start is not None and gantt_graph.get("state") == "available":
        gantt_graph = project_scoped_gantt_graph(gantt_graph, {row["batch_id"] for row in selected[0]})
    gantt_graph = summarize_gantt_graph(gantt_graph, include_nodes=include_gantt_graph)
    provenance = baseline_facts.get("provenance") or {
        "state": "unavailable", "reason": baseline.get("reason") or "此计划未记录可核对的生成来源。",
        "source_kind": None, "source_ref": None, "source_label": None, "run_ref": None,
        "accepted_at": None, "finished_at": None, "adopted_at": None, "algorithm": None, "baseline": None,
    }
    public = {"baseline": baseline, "calendar": calendar, "occupancy": occupancy,
              "delivery_risks": delivery, "process_order": process_order}
    cal_sources = calendar_facts.get("sources") or {}
    facts = {
        "baseline": (baseline.get("state"), baseline.get("reason_code"), baseline.get("reason")),
        "calendar": (
            calendar_facts.get("state"),
            calendar_facts.get("reason"),
            {k: v for k, v in cal_sources.items() if k != "operations"},
        ),
        "delivery": delivery_facts.get("batch_identities"),
        "process_order": (process_order.get("state"), process_order.get("issues")),
        "resource_directory": (
            baseline_facts.get("resource_directory", [])
            + baseline_facts.get("adoption", {}).get("resource_directory", [])
        ),
        "compared_tasks": baseline_facts.get("compared_tasks", []),
    }
    return public, facts, gantt_graph, provenance
