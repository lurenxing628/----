"""Compose public projections and keep their snapshot evidence off the wire."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.gantt_graph import project_scoped_gantt_graph, public_gantt_graph

from .baseline import build_plan_baseline
from .calendar import project_plan_calendar
from .delivery import read_plan_delivery
from .occupancy import project_plan_occupancy
from .process_order import project_process_order


def resource_directory(rows, resources, *, tasks, baseline=None, compared_tasks=(), archived=(), used_refs=()):
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
    used = set(used_refs) | {
        (kind, task[kind + "_ref"])
        for task in list(tasks) + compared
        for kind in ("machine", "operator", "supplier")
        if task.get(kind + "_ref") is not None
    }
    for row in archived:
        directory.setdefault((row["kind"], row["ref"]), row)
    if not used <= set(directory):
        raise WorkbenchCommandRejected("plan_unavailable", "安排引用的资源缺少可核对的来源目录，请核对原采用记录。")
    directory = {key: value for key, value in directory.items() if key in used}
    return [directory[key] for key in sorted(directory)]


def summarize_gantt_graph(gantt_graph: dict, *, include_nodes: bool = False, scoped_batch_ids=None) -> dict:
    if gantt_graph["state"] != "available":
        return {
            **public_gantt_graph(gantt_graph),
            "node_count": 0,
            "nodes_complete": False,
        }
    if scoped_batch_ids is not None:
        scoped = project_scoped_gantt_graph(gantt_graph, scoped_batch_ids, include_nodes=include_nodes)
        if include_nodes:
            return {
                **scoped,
                "node_count": len(scoped["nodes"]),
                "nodes_complete": True,
            }
        return scoped
    count = (
        gantt_graph["node_count"]
        if "node_count" in gantt_graph and not include_nodes
        else len(gantt_graph["nodes"])
    )
    if include_nodes:
        return {
            **public_gantt_graph(gantt_graph),
            "node_count": count,
            "nodes_complete": True,
        }
    return {
        "state": "available",
        "reason": None,
        "scope": gantt_graph["scope"],
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
):
    baseline, baseline_facts = build_plan_baseline(
        conn, entry=entry, scope=scope, context=context, include_items=False,
    )
    selected = context.calendar_selection(entry, scope, plan_span)
    calendar, calendar_facts = project_plan_calendar(
        conn, scope=scope, resources=resources, selected=selected, include_windows=False,
    )
    occupancy = project_plan_occupancy(
        scope=scope, resources=resources, calendar_facts=calendar_facts, selected=selected,
        include_segments=False, intervals=context.datetime_intervals(entry),
    )
    delivery, _ = read_plan_delivery(conn, scope=scope, logger=logger, context=context)
    state = delivery["summary"]["state"]
    delivery = dict(delivery, state="available" if state == "complete" else state)
    process_order, gantt_graph = project_process_order(
        conn, plan_ref=scope.plan_ref, context=context, include_nodes=(scope.range_start is not None),
    )
    scoped_batches = {row["batch_id"] for row in selected[0]} if scope.range_start is not None else None
    gantt_graph = summarize_gantt_graph(gantt_graph, include_nodes=False, scoped_batch_ids=scoped_batches)
    provenance = baseline_facts.get("provenance") or {
        "state": "unavailable", "reason": baseline.get("reason") or "此计划未记录可核对的生成来源。",
        "source_kind": None, "source_ref": None, "source_label": None, "run_ref": None,
        "accepted_at": None, "finished_at": None, "adopted_at": None, "algorithm": None, "baseline": None,
    }
    public = {"baseline": baseline, "calendar": calendar, "occupancy": occupancy,
              "delivery_risks": delivery, "process_order": process_order}
    facts = {
        "resource_directory": (
            baseline_facts.get("resource_directory", [])
            + baseline_facts.get("adoption", {}).get("resource_directory", [])
        ),
        "compared_tasks": baseline_facts.get("compared_tasks", []),
    }
    return public, facts, gantt_graph, provenance
