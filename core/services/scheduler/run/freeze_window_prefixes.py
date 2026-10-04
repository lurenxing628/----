from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def group_seed_operations_by_batch(seed_operations: List[Any]) -> Dict[str, List[Any]]:
    grouped: Dict[str, List[Any]] = {}
    for op in seed_operations:
        bid = str(getattr(op, "batch_id", "") or "")
        grouped.setdefault(bid, []).append(op)
    return grouped


def max_seq_by_batch(schedule_map: Dict[int, Dict[str, Any]], op_by_id: Dict[int, Any]) -> Dict[str, int]:
    max_seq: Dict[str, int] = {}
    for oid in schedule_map.keys():
        op0 = op_by_id.get(int(oid))
        if not op0:
            continue
        bid = str(op0.batch_id or "")
        seq0 = int(op0.seq or 0)
        if seq0 <= 0:
            continue
        max_seq[bid] = max(max_seq.get(bid, 0), seq0)
    return max_seq


def prefix_op_ids_for_batch(operations: List[Any], bid: str, max_seq: int) -> List[int]:
    return [int(op.id) for op in operations if op and op.id and op.batch_id == bid and int(op.seq or 0) <= max_seq]


def rows_in_window(svc, start: Optional[datetime], end: Optional[datetime],
                   schedule_map: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """指定时段时，和时段重叠的原安排（开工即完工的按时刻落在时段内）才决定一批要保留到第几道。

    没指定时段（start/end 为 None）原样返回。时刻读不出来的行也算进来，交给前缀校验按坏数据严格处理。
    """
    if start is None or end is None:
        return schedule_map
    result = {}
    for oid, row in schedule_map.items():
        begin = svc._normalize_datetime(row.get("start_time"))
        finish = svc._normalize_datetime(row.get("end_time"))
        if not begin or not finish or begin < end and (finish > start or begin == finish >= start):
            result[oid] = row
    return result
