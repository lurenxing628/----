from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ._sched_utils import _safe_int


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip().replace("/", "-")
    if not s:
        return None
    s = s.replace("T", " ").replace("：", ":")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _minutes_between(a: Optional[datetime], b: Optional[datetime]) -> Optional[int]:
    if not a or not b:
        return None
    try:
        return int((b - a).total_seconds() // 60)
    except Exception:
        return None


def _empty_result() -> Dict[str, Any]:
    return {
        "ids": [],
        "edges": [],
        "makespan_end": None,
        "edge_type_stats": {"process": 0, "machine": 0, "operator": 0, "unknown": 0},
        "edge_count": 0,
    }


def _load_rows(schedule_repo, version: int) -> List[Dict[str, Any]]:
    try:
        return schedule_repo.list_by_version_with_details(int(version))
    except Exception:
        return []


def _build_nodes(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    nodes: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        st = _parse_dt(r.get("start_time"))
        et = _parse_dt(r.get("end_time"))
        if not st or not et or not (st < et):
            continue
        op_code = (r.get("op_code") or "").strip()
        task_id = op_code or f"op_{r.get('op_id')}"

        nodes[task_id] = {
            "id": task_id,
            "start": st,
            "end": et,
            "batch_id": str(r.get("batch_id") or "").strip(),
            "piece_id": str(r.get("piece_id") or "").strip(),
            "seq": _safe_int(r.get("seq"), default=0),
            "machine_id": str(r.get("machine_id") or "").strip(),
            "operator_id": str(r.get("operator_id") or "").strip(),
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
        rid = str(n.get(resource_key) or "").strip()
        if not rid:
            continue
        groups.setdefault(rid, []).append(n)

    prev_map: Dict[str, str] = {}
    for _, items in groups.items():
        items.sort(key=lambda x: (x.get("start"), x.get("end"), str(x.get("id") or "")))
        prev: Optional[Dict[str, Any]] = None
        for n in items:
            if prev:
                prev_map[str(n.get("id") or "")] = str(prev.get("id") or "")
            prev = n

    return prev_map


def _eligible_process_edge(pn: Dict[str, Any], n: Dict[str, Any]) -> bool:
    # 工艺前驱：允许“merged 外协组”导致的同起止时间（pn.start==n.start 且 pn.end==n.end）
    try:
        return (pn.get("end") <= n.get("start")) or (pn.get("start") == n.get("start") and pn.get("end") == n.get("end"))
    except Exception:
        return False


def _eligible_resource_edge(pn: Dict[str, Any], n: Dict[str, Any]) -> bool:
    # 资源前驱：必须满足 pn.end <= n.start（不允许重叠）
    try:
        return pn.get("end") <= n.get("start")
    except Exception:
        return False


def _process_prev_candidate(
    nodes: Dict[str, Dict[str, Any]], tid: str, n: Dict[str, Any], *, proc_prev: Dict[str, str]
) -> Optional[Dict[str, Any]]:
    pid_proc = proc_prev.get(tid)
    if not pid_proc:
        return None
    pn = nodes.get(pid_proc)
    if not pn or not _eligible_process_edge(pn, n):
        return None
    return {
        "from": pid_proc,
        "edge_type": "process",
        "reason": "工艺前驱",
        "from_end": pn.get("end"),
        "to_start": n.get("start"),
    }


def _resource_prev_candidate(
    nodes: Dict[str, Dict[str, Any]],
    tid: str,
    n: Dict[str, Any],
    *,
    edge_type: str,
    prev_map: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    pid = prev_map.get(tid)
    if not pid:
        return None
    pn = nodes.get(pid)
    if not pn or not _eligible_resource_edge(pn, n):
        return None
    return {
        "from": pid,
        "edge_type": edge_type,
        "reason": "资源前驱（设备）" if edge_type == "machine" else "资源前驱（人员）",
        "from_end": pn.get("end"),
        "to_start": n.get("start"),
    }


def _pick_latest_candidate(cands: List[Dict[str, Any]]) -> Optional[Tuple[str, Dict[str, Any]]]:
    if not cands:
        return None
    cands.sort(key=lambda x: (x.get("from_end"), str(x.get("from") or "")))
    chosen = cands[-1]
    from_id = str(chosen.get("from") or "")
    if not from_id:
        return None
    return from_id, chosen


def _choose_control_prev(
    nodes: Dict[str, Dict[str, Any]],
    *,
    proc_prev: Dict[str, str],
    mach_prev: Dict[str, str],
    op_prev: Dict[str, str],
) -> Tuple[Dict[str, str], Dict[str, Dict[str, Any]]]:
    ctrl_prev: Dict[str, str] = {}
    ctrl_prev_edge: Dict[str, Dict[str, Any]] = {}

    for tid, n in nodes.items():
        cands: List[Dict[str, Any]] = []

        proc_cand = _process_prev_candidate(nodes, tid, n, proc_prev=proc_prev)
        if proc_cand:
            cands.append(proc_cand)

        for edge_type, prev_map in (("machine", mach_prev), ("operator", op_prev)):
            rc = _resource_prev_candidate(nodes, tid, n, edge_type=edge_type, prev_map=prev_map)
            if rc:
                cands.append(rc)

        picked = _pick_latest_candidate(cands)
        if not picked:
            continue
        from_id, chosen = picked

        ctrl_prev[tid] = from_id
        ctrl_prev_edge[tid] = {
            "from": from_id,
            "to": tid,
            "edge_type": str(chosen.get("edge_type") or "unknown"),
            "reason": str(chosen.get("reason") or "控制前驱"),
            "gap_minutes": _minutes_between(chosen.get("from_end"), chosen.get("to_start")),
        }

    return ctrl_prev, ctrl_prev_edge


def _sink_id(nodes: Dict[str, Dict[str, Any]]) -> str:
    sink = max(nodes.values(), key=lambda x: (x.get("end"), str(x.get("id") or "")))
    return str(sink.get("id") or "")


def _backtrace_chain(
    sink_id: str,
    *,
    ctrl_prev: Dict[str, str],
    ctrl_prev_edge: Dict[str, Dict[str, Any]],
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
        pred = ctrl_prev.get(cur)
        if pred:
            edge_meta = ctrl_prev_edge.get(cur) or {}
            edges_rev.append(
                {
                    "from": pred,
                    "to": cur,
                    "edge_type": str(edge_meta.get("edge_type") or "unknown"),
                    "reason": str(edge_meta.get("reason") or "控制前驱"),
                    "gap_minutes": edge_meta.get("gap_minutes"),
                }
            )
        cur = pred or ""

    return list(reversed(chain_rev)), list(reversed(edges_rev))


def _edge_type_stats(edges: List[Dict[str, Any]]) -> Dict[str, int]:
    stats: Dict[str, int] = {"process": 0, "machine": 0, "operator": 0, "unknown": 0}
    for e in edges:
        k = str(e.get("edge_type") or "unknown")
        if k not in stats:
            k = "unknown"
        stats[k] = int(stats.get(k, 0)) + 1
    return stats


def compute_critical_chain(schedule_repo, version: int) -> Dict[str, Any]:
    """
    关键链识别（可解释，近似 CC/CP 语义）：
    - 输入：某一 version 的全量排程（不按周截断）
    - 前驱集合：工艺前驱 + 设备资源前驱 + 人员资源前驱
    - 控制前驱：从候选前驱里选“end_time 最晚且 <= 当前 start_time”的那个
    - 从 makespan 结束的任务回溯控制前驱，得到关键链
    """
    rows = _load_rows(schedule_repo, version=int(version))
    nodes = _build_nodes(rows)
    if not nodes:
        return _empty_result()

    proc_prev = _build_process_prev(nodes)
    mach_prev = _build_prev_by_resource(nodes, resource_key="machine_id")
    op_prev = _build_prev_by_resource(nodes, resource_key="operator_id")

    ctrl_prev, ctrl_prev_edge = _choose_control_prev(nodes, proc_prev=proc_prev, mach_prev=mach_prev, op_prev=op_prev)
    sink_id = _sink_id(nodes)

    chain, edges = _backtrace_chain(sink_id, ctrl_prev=ctrl_prev, ctrl_prev_edge=ctrl_prev_edge, nodes=nodes)
    makespan_end = _fmt_dt(nodes[sink_id].get("end")) if sink_id in nodes and nodes[sink_id].get("end") else None

    return {
        "ids": chain,
        "edges": edges,
        "makespan_end": makespan_end,
        "edge_type_stats": _edge_type_stats(edges),
        "edge_count": len(edges),
    }

