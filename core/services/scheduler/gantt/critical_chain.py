from __future__ import annotations

from datetime import datetime, timedelta
from heapq import heappop, heappush
from typing import Any, Dict, List, Optional, Tuple

from core.services.common.plan_task_identity import public_task_id as _public_task_id
from core.shared.local_datetime import format_local_datetime as _fmt_dt
from core.shared.local_datetime import parse_local_datetime

from .task_labels import public_task_label as _public_task_label


def _identity_text(value: Any) -> str:
    if value is None:
        return ""
    text = value if type(value) is str else str(value)
    return text if text.strip() else ""


def _public_node_label(nodes: Dict[str, Dict[str, Any]], node_id: str) -> str:
    # Callers pass control-edge endpoints, which are node keys; labels come from public_task_label (never empty).
    return nodes[node_id]["label"]


def _minutes_between(a: datetime, b: datetime) -> int:
    return (b - a) // timedelta(minutes=1)


def _empty_result(*, dropped_count: int = 0) -> Dict[str, Any]:
    return {
        "ids": [],
        "edges": [],
        "makespan_end": None,
        "edge_type_stats": {"process": 0, "machine": 0, "operator": 0, "unknown": 0},
        "edge_count": 0,
        "dropped_count": dropped_count,
        "critical_chain_partial": dropped_count > 0,
        "available": True,
        "reason": "",
        "reason_code": "",
    }


def _unavailable_result(reason: str) -> Dict[str, Any]:
    result = _empty_result()
    result["available"] = False
    result["reason"] = reason
    result["reason_code"] = result["reason"]
    return result


def _build_nodes(
    rows: List[Dict[str, Any]], *, include_points: bool = False
) -> Tuple[Dict[str, Dict[str, Any]], int]:
    nodes: Dict[str, Dict[str, Any]] = {}
    dropped = 0
    for r in rows:
        st = parse_local_datetime(r.get("start_time"))
        et = parse_local_datetime(r.get("end_time"))
        if not st or not et or st > et or (st == et and not include_points):
            dropped += 1
            continue
        op_code = _identity_text(r.get("op_code"))
        task_id = op_code or _public_task_id(r)

        nodes[task_id] = {
            "id": task_id,
            "sort_id": str(r.get("operation_ref") or task_id),
            "start": st,
            "end": et,
            "batch_id": _identity_text(r.get("batch_id")),
            "piece_id": _identity_text(r.get("piece_id")),
            # 工序号只在按批次分组的 rows 路径使用，上游 plan.projection._sequence 已校验为正整数；
            # 依赖路径（gantt_graph）的行不带 seq。
            "seq": r.get("seq"),
            "machine_id": _identity_text(r.get("machine_id")),
            "operator_id": _identity_text(r.get("operator_id")),
            "label": _public_task_label(r),
        }
    return nodes, dropped


def _build_process_prev(nodes: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    proc_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for n in nodes.values():
        bid = n["batch_id"]
        if not bid:
            continue
        key = (bid, n["piece_id"])
        proc_groups.setdefault(key, []).append(n)

    proc_prev: Dict[str, List[str]] = {}
    for _, items in proc_groups.items():
        items.sort(key=lambda x: (x["seq"], x["start"], x["id"]))
        prev: Optional[Dict[str, Any]] = None
        for n in items:
            if prev:
                proc_prev[n["id"]] = [prev["id"]]
            prev = n

    return proc_prev


def _build_prev_by_resource(nodes: Dict[str, Dict[str, Any]], *, resource_key: str) -> Dict[str, str]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes.values():
        if n.get("start") == n.get("end"):
            continue
        rid = n[resource_key]
        if not rid:
            continue
        groups.setdefault(rid, []).append(n)

    prev_map: Dict[str, str] = {}
    for _, items in groups.items():
        items.sort(key=lambda x: (x["start"], x["end"], int(x.get("order") or 0), x["id"]))
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
        for pid in proc_prev.get(tid, []):
            pn = nodes[pid]
            if _eligible_process_edge(pn, n):
                cands.append((pn["end"], int(pn.get("order") or 0), pid, "process"))
        for edge_type, prev_map in (("machine", mach_prev), ("operator", op_prev)):
            pid = prev_map.get(tid)
            if pid:
                pn = nodes[pid]
                if _eligible_resource_edge(pn, n):
                    cands.append((pn["end"], int(pn.get("order") or 0), pid, edge_type))
        if cands:
            cands.sort(key=lambda candidate: candidate[:3])
            _, _, from_id, edge_type = cands[-1]
            ctrl_prev[tid] = from_id, edge_type
    return ctrl_prev


def _sink_id(nodes: Dict[str, Dict[str, Any]]) -> str:
    sink = max(nodes.values(), key=lambda x: (x["end"], int(x.get("order") or 0), x["id"]))
    return sink["id"]


def _backtrace_chain(
    sink_id: str,
    *,
    ctrl_prev: Dict[str, Tuple[str, str]],
    nodes: Dict[str, Dict[str, Any]],
) -> Tuple[List[str], List[Dict[str, Any]]]:
    chain_rev: List[str] = []
    edges_rev: List[Dict[str, Any]] = []

    cur = sink_id
    seen: set = set()
    while cur and cur not in seen:
        seen.add(cur)
        chain_rev.append(cur)
        control = ctrl_prev.get(cur)
        if control:
            pred, edge_type = control
            edges_rev.append(
                {
                    "from": pred,
                    "to": cur,
                    "from_label": _public_node_label(nodes, pred),
                    "to_label": _public_node_label(nodes, cur),
                    "edge_type": edge_type,
                    "reason": "工艺前驱" if edge_type == "process" else ("资源前驱（设备）" if edge_type == "machine" else "资源前驱（人员）"),
                    "gap_minutes": _minutes_between(nodes[pred]["end"], nodes[cur]["start"]),
                }
            )
            cur = pred
        else:
            cur = ""

    return list(reversed(chain_rev)), list(reversed(edges_rev))


def _edge_type_stats(edges: List[Dict[str, Any]]) -> Dict[str, int]:
    stats: Dict[str, int] = {"process": 0, "machine": 0, "operator": 0, "unknown": 0}
    for e in edges:
        stats[e["edge_type"]] += 1
    return stats


def _explicit_sink(rows: List[Dict[str, Any]], nodes: Dict[str, Dict[str, Any]], target_id: str) -> Tuple[str, str]:
    if type(target_id) is not str or not target_id.strip():
        return "", "target_invalid"
    identities = [_identity_text(row.get("op_code")) or _public_task_id(row) for row in rows]
    if len(set(identities)) != len(identities):
        return "", "target_identity_conflict"
    if target_id not in identities:
        return "", "target_not_found"
    if target_id not in nodes:
        return "", "target_time_unavailable"
    return target_id, ""


def compute_critical_chain_from_rows(rows: List[Dict[str, Any]], *, target_id: Optional[str] = None) -> Dict[str, Any]:
    """An explicit sink changes only backtracing, never the full input control graph."""
    nodes, dropped = _build_nodes(rows)
    if target_id is not None:
        sink_id, reason = _explicit_sink(rows, nodes, target_id)
        if reason:
            return _unavailable_result(reason)
    elif not nodes:
        return _empty_result(dropped_count=dropped)
    else:
        sink_id = _sink_id(nodes)

    proc_prev = _build_process_prev(nodes)
    return _chain_result(nodes, proc_prev, dropped_count=dropped, sink_id=sink_id)


def _chain_result(nodes, proc_prev, *, dropped_count, sink_id):
    mach_prev = _build_prev_by_resource(nodes, resource_key="machine_id")
    op_prev = _build_prev_by_resource(nodes, resource_key="operator_id")

    ctrl_prev = _choose_control_prev(nodes, proc_prev=proc_prev, mach_prev=mach_prev, op_prev=op_prev)
    chain, edges = _backtrace_chain(sink_id, ctrl_prev=ctrl_prev, nodes=nodes)
    makespan_end = _fmt_dt(nodes[sink_id]["end"])

    return {
        "ids": chain,
        "edges": edges,
        "makespan_end": makespan_end,
        "edge_type_stats": _edge_type_stats(edges),
        "edge_count": len(edges),
        "dropped_count": dropped_count,
        "critical_chain_partial": dropped_count > 0,
    }


def compute_critical_chain_from_dependencies(rows, predecessor_ids):
    """Use captured process edges, including joins and point operations.

    Process order breaks equal-time ties and keeps downstream point stages in
    the chain; permanent operation identities keep adoption from changing it.
    """
    nodes, dropped = _build_nodes(rows, include_points=True)
    if not nodes:
        return _empty_result(dropped_count=dropped)
    previous: Dict[str, List[str]] = {}
    counts: Dict[str, int] = {}
    following: Dict[str, List[str]] = {key: [] for key in nodes}
    ready = []
    for key, node in nodes.items():
        parents = [parent for parent in predecessor_ids.get(key, []) if parent in nodes]
        previous[key] = parents
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
    if order != len(nodes):
        raise ValueError("工艺前后关系形成循环，无法计算关键链。")
    return _chain_result(nodes, previous, dropped_count=dropped, sink_id=_sink_id(nodes))
