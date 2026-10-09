from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def group_seed_operations_by_batch(seed_operations: List[Any]) -> Dict[str, List[Any]]:
    grouped: Dict[str, List[Any]] = {}
    for op in seed_operations:
        bid = str(getattr(op, "batch_id", "") or "")
        grouped.setdefault(bid, []).append(op)
    return grouped


def window_anchors_by_batch(schedule_map: Dict[int, Dict[str, Any]],
                            op_by_id: Dict[int, Any]) -> Dict[str, Dict[Optional[str], int]]:
    """{批次: {分件号（None 为不分件或共同工序）: 窗口里这一件最大的工序号}}；工序号 <=0 的不算。"""
    anchors: Dict[str, Dict[Optional[str], int]] = {}
    for oid in schedule_map.keys():
        op0 = op_by_id.get(int(oid))
        if not op0:
            continue
        seq0 = int(op0.seq or 0)
        if seq0 <= 0:
            continue
        pieces = anchors.setdefault(str(op0.batch_id or ""), {})
        piece = getattr(op0, "piece_id", None)
        pieces[piece] = max(pieces.get(piece, 0), seq0)
    return anchors


def prefix_op_ids_for_anchors(operations: List[Any], bid: str, anchors: Dict[Optional[str], int]) -> List[int]:
    """窗口里的工序加上它们的前道。不分件的批次就是工序号不超过窗口里最大号的全部工序；
    分件批次里，分件工序只跟同一件和共同工序走，另一件排在后面的工序不算前道（与排产计算的分件前后关系一致）。"""
    top = max(anchors.values())
    result = []
    for op in operations:
        if not op or not op.id or op.batch_id != bid:
            continue
        piece = getattr(op, "piece_id", None)
        bound = top if piece is None else max(anchors.get(None, 0), anchors.get(piece, 0))
        if int(op.seq or 0) <= bound:
            result.append(int(op.id))
    return result


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
