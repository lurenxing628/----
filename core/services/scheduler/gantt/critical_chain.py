from __future__ import annotations

from datetime import datetime
from heapq import heappop, heappush
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.ordering import clean_resource_id


def _build_nodes(
    tasks: List[Dict[str, Any]], task_intervals: Dict[str, Tuple[datetime, datetime]]
) -> Dict[str, Dict[str, Any]]:
    nodes: Dict[str, Dict[str, Any]] = {}
    for task in tasks:
        ref = task["task_ref"]
        start, end = task_intervals[ref]
        nodes[ref] = {
            "id": ref,
            "sort_id": task["operation_ref"],
            "start": start,
            "end": end,
            "machine_id": clean_resource_id(task["machine_ref"]),
            "operator_id": clean_resource_id(task["operator_ref"]),
        }
    return nodes


def _build_prev_by_resource(nodes: Dict[str, Dict[str, Any]], *, resource_key: str) -> Dict[str, str]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes.values():
        if n["start"] == n["end"]:
            continue
        rid = n[resource_key]
        if not rid:
            continue
        groups.setdefault(rid, []).append(n)

    prev_map: Dict[str, str] = {}
    for _, items in groups.items():
        items.sort(key=lambda x: (x["start"], x["end"], x["order"], x["id"]))
        prev: Optional[Dict[str, Any]] = None
        for n in items:
            if prev:
                prev_map[n["id"]] = prev["id"]
            prev = n

    return prev_map


def _eligible_process_edge(pn: Dict[str, Any], n: Dict[str, Any]) -> bool:
    # 工艺前驱：允许“merged 外协组”导致的同起止时间（pn.start==n.start 且 pn.end==n.end）
    return (pn["end"] <= n["start"]) or (pn["start"] == n["start"] and pn["end"] == n["end"])


def _eligible_resource_edge(pn: Dict[str, Any], n: Dict[str, Any]) -> bool:
    # 资源前驱：必须满足 pn.end <= n.start（不允许重叠）
    return pn["end"] <= n["start"]


def _choose_control_prev(
    nodes: Dict[str, Dict[str, Any]],
    *,
    proc_prev: Dict[str, List[str]],
    mach_prev: Dict[str, str],
    op_prev: Dict[str, str],
) -> Dict[str, Tuple[str, str]]:
    ctrl_prev: Dict[str, Tuple[str, str]] = {}
    for tid, n in nodes.items():
        cands: List[Tuple[datetime, int, str, str]] = []
        for pid in proc_prev[tid]:
            pn = nodes[pid]
            if _eligible_process_edge(pn, n):
                cands.append((pn["end"], pn["order"], pid, "process"))
        for edge_type, prev_map in (("machine", mach_prev), ("operator", op_prev)):
            pid = prev_map.get(tid)
            if pid:
                pn = nodes[pid]
                if _eligible_resource_edge(pn, n):
                    cands.append((pn["end"], pn["order"], pid, edge_type))
        if cands:
            cands.sort(key=lambda candidate: candidate[:3])
            _, _, from_id, edge_type = cands[-1]
            ctrl_prev[tid] = from_id, edge_type
    return ctrl_prev


def _sink_id(nodes: Dict[str, Dict[str, Any]]) -> str:
    sink = max(nodes.values(), key=lambda x: (x["end"], x["order"], x["id"]))
    return sink["id"]


def _backtrace_chain(
    sink_id: str, *, ctrl_prev: Dict[str, Tuple[str, str]]
) -> Tuple[List[str], List[Dict[str, Any]]]:
    chain_rev: List[str] = []
    edges_rev: List[Dict[str, Any]] = []

    cur = sink_id
    while True:
        chain_rev.append(cur)
        control = ctrl_prev.get(cur)
        if control is None:
            break
        pred, edge_type = control
        edges_rev.append({"from": pred, "to": cur, "edge_type": edge_type})
        cur = pred

    return list(reversed(chain_rev)), list(reversed(edges_rev))


def _chain_result(nodes, proc_prev):
    mach_prev = _build_prev_by_resource(nodes, resource_key="machine_id")
    op_prev = _build_prev_by_resource(nodes, resource_key="operator_id")

    ctrl_prev = _choose_control_prev(nodes, proc_prev=proc_prev, mach_prev=mach_prev, op_prev=op_prev)
    chain, edges = _backtrace_chain(_sink_id(nodes), ctrl_prev=ctrl_prev)
    return {"ids": chain, "edges": edges}


def compute_critical_chain_from_dependencies(tasks, previous, *, task_intervals):
    """Use captured process edges, including joins and point operations.

    ``previous`` maps every task_ref to its acyclic in-graph process
    predecessors and ``task_intervals`` to its admitted datetime interval.
    Process order breaks equal-time ties and keeps downstream point stages in
    the chain; permanent operation identities keep adoption from changing it.
    """
    nodes = _build_nodes(tasks, task_intervals)
    if not nodes:
        return {"ids": [], "edges": []}
    counts: Dict[str, int] = {}
    following: Dict[str, List[str]] = {key: [] for key in nodes}
    ready = []
    for key, node in nodes.items():
        parents = previous[key]
        count = len(parents)
        counts[key] = count
        if count == 0:
            heappush(ready, (node["start"], node["end"], node["sort_id"], key))
        else:
            for parent in parents:
                following[parent].append(key)
    order = 0
    while ready:
        _, _, _, key = heappop(ready)
        nodes[key]["order"] = order
        order += 1
        for child in following[key]:
            counts[child] -= 1
            if counts[child] == 0:
                heappush(ready, (nodes[child]["start"], nodes[child]["end"], nodes[child]["sort_id"], child))
    return _chain_result(nodes, previous)
