from __future__ import annotations

from datetime import datetime, timedelta
from heapq import heappop, heappush
from typing import Any, Dict, List, Optional, Tuple

from core.services.common.degradation import DegradationCollector
from core.services.common.plan_task_identity import public_task_id as _public_task_id
from core.services.scheduler._sched_display_utils import record_bad_time_row as _record_bad_time_row
from core.services.scheduler._sched_utils import _safe_int
from core.shared.local_datetime import format_local_datetime as _fmt_dt
from core.shared.local_datetime import parse_local_datetime

from .task_labels import public_task_label as _public_task_label


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _public_node_label(nodes: Dict[str, Dict[str, Any]], node_id: str) -> str:
    node = nodes.get(str(node_id or "")) or {}
    return _clean_text(node.get("label")) or "未命名工序"


def _node_dt(node: Dict[str, Any], key: str) -> Optional[datetime]:
    return node.get(key)


def _minutes_between(a: Optional[datetime], b: Optional[datetime]) -> Optional[int]:
    if not a or not b:
        return None
    return (b - a) // timedelta(minutes=1)


def _dropped_count(value: Any) -> int:
    return max(0, _safe_int(value, default=0))


def _empty_result(*, dropped_count: int = 0) -> Dict[str, Any]:
    dropped = _dropped_count(dropped_count)
    return {
        "ids": [],
        "edges": [],
        "makespan_end": None,
        "edge_type_stats": {"process": 0, "machine": 0, "operator": 0, "unknown": 0},
        "edge_count": 0,
        "dropped_count": dropped,
        "critical_chain_partial": dropped > 0,
        "available": True,
        "reason": "",
        "reason_code": "",
    }


def _unavailable_result(reason: str) -> Dict[str, Any]:
    result = _empty_result()
    result["available"] = False
    result["reason"] = str(reason or "").strip() or "unknown"
    result["reason_code"] = result["reason"]
    return result


def _build_nodes(rows: List[Dict[str, Any]], *, collector: Optional[DegradationCollector] = None,
                 include_points: bool = False) -> Dict[str, Dict[str, Any]]:
    nodes: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        st = parse_local_datetime(r.get("start_time"))
        et = parse_local_datetime(r.get("end_time"))
        if not st or not et or st > et or (st == et and not include_points):
            if collector is not None:
                _record_bad_time_row(collector, scope="gantt.critical_chain", row=r)
            continue
        op_code = (r.get("op_code") or "").strip()
        task_id = op_code or _public_task_id(r)

        nodes[task_id] = {
            "id": task_id,
            "sort_id": str(r.get("operation_ref") or task_id),
            "start": st,
            "end": et,
            "batch_id": str(r.get("batch_id") or "").strip(),
            "piece_id": str(r.get("piece_id") or "").strip(),
            "seq": _safe_int(r.get("seq"), default=0),
            "machine_id": str(r.get("machine_id") or "").strip(),
            "operator_id": str(r.get("operator_id") or "").strip(),
            "label": _public_task_label(r),
        }
    return nodes


def _build_process_prev(nodes: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    proc_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for n in nodes.values():
        bid = str(n.get("batch_id") or "").strip()
        if not bid:
            continue
        key = (bid, str(n.get("piece_id") or "").strip())
        proc_groups.setdefault(key, []).append(n)

    proc_prev: Dict[str, str] = {}
    for _, items in proc_groups.items():
        items.sort(key=lambda x: (int(x.get("seq") or 0), x.get("start"), str(x.get("id") or "")))
        prev: Optional[Dict[str, Any]] = None
        for n in items:
            if prev:
                proc_prev[str(n.get("id") or "")] = str(prev.get("id") or "")
            prev = n

    return proc_prev


def _build_prev_by_resource(nodes: Dict[str, Dict[str, Any]], *, resource_key: str) -> Dict[str, str]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes.values():
        if n.get("start") == n.get("end"):
            continue
        rid = str(n.get(resource_key) or "").strip()
        if not rid:
            continue
        groups.setdefault(rid, []).append(n)

    prev_map: Dict[str, str] = {}
    for _, items in groups.items():
        items.sort(key=lambda x: (x.get("start"), x.get("end"), int(x.get("order") or 0), str(x.get("id") or "")))
        prev: Optional[Dict[str, Any]] = None
        for n in items:
            if prev:
                prev_map[str(n.get("id") or "")] = str(prev.get("id") or "")
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
    sink = max(nodes.values(), key=lambda x: (x.get("end"), int(x.get("order") or 0), str(x.get("id") or "")))
    return str(sink.get("id") or "")


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
    guard = 0
    while cur and cur not in seen and guard < (len(nodes) + 5):
        guard += 1
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
        k = str(e.get("edge_type") or "unknown")
        if k not in stats:
            k = "unknown"
        stats[k] = stats[k] + 1
    return stats


def _explicit_sink(rows: List[Dict[str, Any]], nodes: Dict[str, Dict[str, Any]], target_id: str) -> Tuple[str, str]:
    if type(target_id) is not str or not target_id or target_id != target_id.strip():
        return "", "target_invalid"
    identities = [(row.get("op_code") or "").strip() or _public_task_id(row) for row in rows]
    if len(set(identities)) != len(identities):
        return "", "target_identity_conflict"
    if target_id not in identities:
        return "", "target_not_found"
    if target_id not in nodes:
        return "", "target_time_unavailable"
    return target_id, ""


def _compute_critical_chain_from_loaded_rows(rows: List[Dict[str, Any]], *, target_id: Optional[str] = None) -> Dict[str, Any]:
    collector = DegradationCollector()
    nodes = _build_nodes(rows, collector=collector)
    dropped = _dropped_count((collector.to_counters() or {}).get("bad_time_row_skipped"))
    sink_id = ""
    if target_id is not None:
        sink_id, reason = _explicit_sink(rows, nodes, target_id)
        if reason:
            return _unavailable_result(reason)
    elif not nodes:
        return _empty_result(dropped_count=dropped)

    proc_prev = {key: [value] for key, value in _build_process_prev(nodes).items()}
    return _chain_result(nodes, proc_prev, dropped_count=dropped, sink_id=sink_id)


def _chain_result(nodes, proc_prev, *, dropped_count=0, sink_id=""):
    mach_prev = _build_prev_by_resource(nodes, resource_key="machine_id")
    op_prev = _build_prev_by_resource(nodes, resource_key="operator_id")

    ctrl_prev = _choose_control_prev(nodes, proc_prev=proc_prev, mach_prev=mach_prev, op_prev=op_prev)
    if not sink_id:
        sink_id = _sink_id(nodes)
    chain, edges = _backtrace_chain(sink_id, ctrl_prev=ctrl_prev, nodes=nodes)
    sink_end = _node_dt(nodes[sink_id], "end") if sink_id in nodes else None
    makespan_end = _fmt_dt(sink_end) if sink_end is not None else None

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
    nodes = _build_nodes(rows, include_points=True)
    if not nodes:
        return _empty_result()
    previous = {key: [parent for parent in predecessor_ids.get(key, []) if parent in nodes] for key in nodes}
    counts = {key: len(parents) for key, parents in previous.items()}
    following: Dict[str, List[str]] = {key: [] for key in nodes}
    for key, parents in previous.items():
        for parent in parents:
            following[parent].append(key)
    ready = []
    for key, count in counts.items():
        if count == 0:
            heappush(ready, (nodes[key]["start"], nodes[key]["end"], nodes[key]["sort_id"], key))
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
    return _chain_result(nodes, previous)


def compute_critical_chain_from_rows(rows: List[Dict[str, Any]], *, target_id: Optional[str] = None) -> Dict[str, Any]:
    """An explicit sink changes only backtracing, never the full input control graph."""
    try:
        return _compute_critical_chain_from_loaded_rows(list(rows or []), target_id=target_id)
    except Exception:
        return _unavailable_result("rows_exception")
