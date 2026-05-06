from __future__ import annotations

from typing import Any, Dict, List


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
