from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


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


def compute_critical_chain(schedule_repo, version: int) -> Dict[str, Any]:
    """
    关键链识别（可解释，近似 CC/CP 语义）：
    - 输入：某一 version 的全量排程（不按周截断）
    - 前驱集合：工艺前驱 + 设备资源前驱 + 人员资源前驱
    - 控制前驱：从候选前驱里选“end_time 最晚且 <= 当前 start_time”的那个
    - 从 makespan 结束的任务回溯控制前驱，得到关键链
    """
    try:
        rows = schedule_repo.list_by_version_with_details(int(version))
    except Exception:
        rows = []

    # 构建节点
    nodes: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        st = _parse_dt(r.get("start_time"))
        et = _parse_dt(r.get("end_time"))
        if not st or not et or not (st < et):
            continue
        op_code = (r.get("op_code") or "").strip()
        task_id = op_code or f"op_{r.get('op_id')}"

        seq_raw = r.get("seq")
        try:
            seq_int = int(seq_raw) if seq_raw is not None and str(seq_raw).strip() != "" else 0
        except Exception:
            seq_int = 0

        nodes[task_id] = {
            "id": task_id,
            "start": st,
            "end": et,
            "batch_id": str(r.get("batch_id") or "").strip(),
            "piece_id": str(r.get("piece_id") or "").strip(),
            "seq": int(seq_int),
            "machine_id": str(r.get("machine_id") or "").strip(),
            "operator_id": str(r.get("operator_id") or "").strip(),
        }

    if not nodes:
        return {
            "ids": [],
            "edges": [],
            "makespan_end": None,
            "edge_type_stats": {"process": 0, "machine": 0, "operator": 0, "unknown": 0},
            "edge_count": 0,
        }

    # 1) 工艺前驱：同 (batch_id, piece_id) 的 seq 链
    proc_prev: Dict[str, str] = {}
    proc_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for n in nodes.values():
        bid = str(n.get("batch_id") or "").strip()
        if not bid:
            continue
        key = (bid, str(n.get("piece_id") or "").strip())
        proc_groups.setdefault(key, []).append(n)
    for _, items in proc_groups.items():
        items.sort(key=lambda x: (int(x.get("seq") or 0), x.get("start"), str(x.get("id") or "")))
        prev: Optional[Dict[str, Any]] = None
        for n in items:
            if prev:
                proc_prev[str(n.get("id") or "")] = str(prev.get("id") or "")
            prev = n

    # 2) 设备资源前驱：同 machine_id 按 start 排序的上一条
    mach_prev: Dict[str, str] = {}
    mach_groups: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes.values():
        mid = str(n.get("machine_id") or "").strip()
        if not mid:
            continue
        mach_groups.setdefault(mid, []).append(n)
    for _, items in mach_groups.items():
        items.sort(key=lambda x: (x.get("start"), x.get("end"), str(x.get("id") or "")))
        prev = None
        for n in items:
            if prev:
                mach_prev[str(n.get("id") or "")] = str(prev.get("id") or "")
            prev = n

    # 3) 人员资源前驱：同 operator_id 按 start 排序的上一条
    op_prev: Dict[str, str] = {}
    op_groups: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes.values():
        oid = str(n.get("operator_id") or "").strip()
        if not oid:
            continue
        op_groups.setdefault(oid, []).append(n)
    for _, items in op_groups.items():
        items.sort(key=lambda x: (x.get("start"), x.get("end"), str(x.get("id") or "")))
        prev = None
        for n in items:
            if prev:
                op_prev[str(n.get("id") or "")] = str(prev.get("id") or "")
            prev = n

    # 控制前驱：三者取“最晚结束”的那一个，并记录边类型/原因，便于前端解释
    ctrl_prev: Dict[str, str] = {}
    ctrl_prev_edge: Dict[str, Dict[str, Any]] = {}
    for tid, n in nodes.items():
        cands: List[Dict[str, Any]] = []
        # 工艺前驱：允许“merged 外协组”导致的同起止时间（pn.start==n.start 且 pn.end==n.end）
        pid_proc = proc_prev.get(tid)
        if pid_proc:
            pn = nodes.get(pid_proc)
            if pn:
                try:
                    if (pn.get("end") <= n.get("start")) or (
                        pn.get("start") == n.get("start") and pn.get("end") == n.get("end")
                    ):
                        cands.append(
                            {
                                "from": pid_proc,
                                "edge_type": "process",
                                "reason": "工艺前驱",
                                "from_end": pn.get("end"),
                                "to_start": n.get("start"),
                            }
                        )
                except Exception:
                    pass

        # 资源前驱：必须满足 pn.end <= n.start（不允许重叠）
        for edge_type, pid in (("machine", mach_prev.get(tid)), ("operator", op_prev.get(tid))):
            if not pid:
                continue
            pn = nodes.get(pid)
            if not pn:
                continue
            try:
                if pn.get("end") <= n.get("start"):
                    cands.append(
                        {
                            "from": pid,
                            "edge_type": edge_type,
                            "reason": "资源前驱（设备）" if edge_type == "machine" else "资源前驱（人员）",
                            "from_end": pn.get("end"),
                            "to_start": n.get("start"),
                        }
                    )
            except Exception:
                continue
        if cands:
            cands.sort(key=lambda x: (x.get("from_end"), str(x.get("from") or "")))
            chosen = cands[-1]
            from_id = str(chosen.get("from") or "")
            if from_id:
                ctrl_prev[tid] = from_id
                ctrl_prev_edge[tid] = {
                    "from": from_id,
                    "to": tid,
                    "edge_type": str(chosen.get("edge_type") or "unknown"),
                    "reason": str(chosen.get("reason") or "控制前驱"),
                    "gap_minutes": _minutes_between(chosen.get("from_end"), chosen.get("to_start")),
                }

    # makespan 链尾：全局最大完工时间
    sink = max(nodes.values(), key=lambda x: (x.get("end"), str(x.get("id") or "")))
    sink_id = str(sink.get("id") or "")

    # 回溯
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

    chain = list(reversed(chain_rev))
    edges = list(reversed(edges_rev))
    makespan_end = _fmt_dt(nodes[sink_id].get("end")) if sink_id in nodes and nodes[sink_id].get("end") else None
    edge_type_stats: Dict[str, int] = {"process": 0, "machine": 0, "operator": 0, "unknown": 0}
    for e in edges:
        k = str(e.get("edge_type") or "unknown")
        if k not in edge_type_stats:
            k = "unknown"
        edge_type_stats[k] = int(edge_type_stats.get(k, 0)) + 1
    return {
        "ids": chain,
        "edges": edges,
        "makespan_end": makespan_end,
        "edge_type_stats": edge_type_stats,
        "edge_count": len(edges),
    }

