"""Compose public projections and keep their snapshot evidence off the wire."""

from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple

from core.services.workbench.facts.gantt_graph import project_scoped_gantt_graph

from .baseline import PlanBaselineFacts, build_plan_baseline
from .calendar import project_plan_calendar
from .delivery import read_plan_delivery
from .occupancy import project_plan_occupancy


def plan_process_order(history: Dict[str, Any]) -> Dict[str, Any]:
    """An official plan's process order is the one frozen into its gantt graph at adoption."""
    basis = "run_admission" if history["source_kind"] == "candidate_adoption" else "trial_creation"
    return {"state": "available", "basis": basis, "issues": []}


def plan_gantt_graph(context, version: int, scoped_batch_ids: Optional[Set[str]], *, include_nodes: bool) -> Dict[str, Any]:
    """The official gantt graph, scoped to ``scoped_batch_ids`` (None: the full plan).

    The full-plan summary uses the node count stored with the plan and never decodes the graph.
    """
    if scoped_batch_ids is None and not include_nodes:
        return {
            "state": "available",
            "reason": None,
            "scope": "full_plan",
            "nodes": [],
            "node_count": context.history(version)["gantt_node_count"],
            "nodes_complete": False,
            "critical_task_refs": [],
            "critical_edges": [],
        }
    graph = project_scoped_gantt_graph(context.gantt_graph(version), scoped_batch_ids, include_nodes=include_nodes)
    if include_nodes:
        return {**graph, "node_count": len(graph["nodes"]), "nodes_complete": True}
    return graph


def workspace_projections(
    conn,
    *,
    entry,
    scope,
    resources,
    plan_span,
    logger,
    context,
) -> Tuple[Dict[str, Any], PlanBaselineFacts, Dict[str, Any]]:
    baseline, baseline_facts = build_plan_baseline(
        conn, entry=entry, scope=scope, context=context, include_items=False
    )
    selected = context.calendar_selection(entry, scope, plan_span)
    calendar, calendar_facts = project_plan_calendar(
        conn, scope=scope, resources=resources, selected=selected, include_windows=False
    )
    occupancy = project_plan_occupancy(
        scope=scope, resources=resources, calendar_facts=calendar_facts, selected=selected, include_segments=False
    )
    delivery = read_plan_delivery(conn, scope=scope, logger=logger, context=context)
    state = delivery["summary"]["state"]
    delivery = dict(delivery, state="available" if state == "complete" else state)
    version = entry.locator.version
    scoped_batch_ids = {row["batch_id"] for row in selected.rows} if scope.range_start is not None else None
    gantt_graph = plan_gantt_graph(context, version, scoped_batch_ids, include_nodes=False)
    public = {
        "baseline": baseline,
        "calendar": calendar,
        "occupancy": occupancy,
        "delivery_risks": delivery,
        "process_order": plan_process_order(context.history(version)),
    }
    return public, baseline_facts, gantt_graph
