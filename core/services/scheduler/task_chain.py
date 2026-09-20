"""甘特任务链的共享整理：按工艺 seq 连线、按资源分组排序；gantt 与 resource_dispatch 两族共用。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ._sched_utils import _safe_int


def attach_process_dependencies(tasks: List[Dict[str, Any]]) -> None:
    # 工艺依赖：同 (batch_id, piece_id) 的 seq 链（仅在本次 tasks 集合内连线，避免跨窗口缺失）
    chains: Dict[Tuple[str, str], List[Tuple[int, Dict[str, Any]]]] = {}
    for task in tasks:
        meta = task.get("meta") or {}
        bid = str(meta.get("batch_id") or "").strip()
        if not bid:
            continue
        piece_id = str(meta.get("piece_id") or "").strip()
        seq_int = _safe_int(meta.get("seq"), default=0)
        chains.setdefault((bid, piece_id), []).append((seq_int, task))

    for _, items in chains.items():
        items.sort(key=lambda item: (int(item[0]), str(item[1].get("start") or ""), str(item[1].get("id") or "")))
        prev_id: Optional[str] = None
        for _, task in items:
            task_id = str(task.get("id") or "").strip()
            if not task_id:
                continue
            if prev_id:
                # Frappe Gantt：dependencies 为逗号分隔的 task.id 字符串
                task["dependencies"] = prev_id
                task["edge_type"] = "process"
                task_meta = task.get("meta")
                if isinstance(task_meta, dict):
                    task_meta["edge_type"] = "process"
                    task_meta["dependency_from"] = prev_id
            prev_id = task_id


def sort_tasks(tasks: List[Dict[str, Any]]) -> None:
    # 排序：让同一资源尽量聚在一起（视觉上更像“设备/人员视图”）
    def _sort_key(task: Dict[str, Any]):
        meta = task.get("meta") or {}
        return (str(meta.get("group_key") or ""), str(task.get("start") or ""), str(task.get("id") or ""))

    tasks.sort(key=_sort_key)
