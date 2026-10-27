from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from core.shared.local_datetime import parse_local_datetime as parse_dt


def group_seed_operations_by_batch(seed_operations: List[Any]) -> Dict[str, List[Any]]:
    grouped: Dict[str, List[Any]] = {}
    for op in seed_operations:
        grouped.setdefault(op.batch_id, []).append(op)
    return grouped


def window_anchors_by_batch(schedule_map: Dict[int, Dict[str, Any]],
                            op_by_id: Dict[int, Any]) -> Dict[str, Dict[Optional[str], int]]:
    """{批次: {分件号（None 为不分件或共同工序）: 窗口里这一件最大的工序号}}。"""
    anchors: Dict[str, Dict[Optional[str], int]] = {}
    for oid in schedule_map.keys():
        op0 = op_by_id.get(int(oid))
        if not op0:
            continue
        pieces = anchors.setdefault(op0.batch_id, {})
        piece = op0.piece_id
        pieces[piece] = max(pieces.get(piece, 0), op0.seq)
    return anchors


def prefix_op_ids_for_anchors(operations: List[Any], anchors: Dict[Optional[str], int]) -> List[int]:
    """窗口里的工序加上它们的前道。不分件的批次就是工序号不超过窗口里最大号的全部工序；
    分件批次里，分件工序只跟同一件和共同工序走，另一件排在后面的工序不算前道（与排产计算的分件前后关系一致）。"""
    # BatchOperation.batch_id/seq are required (core/models/batch_operation.py; NOT NULL in schema).
    top = max(anchors.values())
    common_bound = max(
        (op.seq for op in operations if op.piece_id is None and op.seq <= top),
        default=anchors.get(None, 0),
    )
    return [
        int(op.id)
        for op in operations
        if op.seq <= (top if op.piece_id is None else max(common_bound, anchors.get(op.piece_id, 0)))
    ]


def rows_in_window(start: datetime, end: datetime,
                   schedule_map: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """和时段重叠的原安排（开工即完工的按时刻落在时段内）才决定一批要保留到第几道。

    时刻读不出来的行也算进来，交给前缀校验按坏数据严格处理。
    """
    result = {}
    for oid, row in schedule_map.items():
        parsed_times = row.get("_parsed_times")
        if parsed_times is None:
            parsed_times = (parse_dt(row.get("start_time")), parse_dt(row.get("end_time")))
            row["_parsed_times"] = parsed_times
        begin, finish = parsed_times
        if not begin or not finish or begin < end and (finish > start or begin == finish >= start):
            result[oid] = row
    return result
