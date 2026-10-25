from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.changeover_events import type_transition
from core.algorithm_contracts.date_parsers import due_exclusive, parse_date


def batch_id(result: Any) -> str:
    return str(result.batch_id or "").strip()


def latest_result(results: List[Any]) -> Optional[Any]:
    rows = [
        row
        for row in results or ()
        if row.end_time is not None and batch_id(row)
    ]
    if not rows:
        return None
    return max(
        rows,
        key=lambda row: (
            row.end_time,
            batch_id(row),
            int(row.seq or 0),
        ),
    )


def finish_by_batch(results: List[Any]) -> Dict[str, datetime]:
    out: Dict[str, datetime] = {}
    for result in results or ():
        bid = batch_id(result)
        end_time = result.end_time
        if not bid or not isinstance(end_time, datetime):
            continue
        current = out.get(bid)
        if current is None or end_time > current:
            out[bid] = end_time
    return out


def batch_due_date(batch: Any) -> Optional[date]:
    due_raw = batch.due_date
    if isinstance(due_raw, date) and not isinstance(due_raw, datetime):
        return due_raw
    if isinstance(due_raw, datetime):
        return due_raw.date()
    text = str(due_raw or "").strip()
    return parse_date(text) if text else None


def most_tardy_batch(
    *,
    finish_by_batch_rows: Dict[str, datetime],
    batches: Dict[str, Any],
) -> Optional[str]:
    best: Optional[Tuple[str, float]] = None
    for raw_batch_id, batch in (batches or {}).items():
        bid = str(raw_batch_id or "").strip()
        due_date = batch_due_date(batch)
        finish_time = finish_by_batch_rows.get(bid)
        if not bid or due_date is None or finish_time is None:
            continue
        due_end = due_exclusive(due_date)
        if finish_time < due_end:
            continue
        tardiness = max((finish_time - due_end).total_seconds() / 3600.0, 0.0)
        if best is None or (tardiness, bid) > (best[1], best[0]):
            best = (bid, float(tardiness))
    return best[0] if best is not None else None


def earliest_due_pressure_batch(
    *,
    finish_by_batch_rows: Dict[str, datetime],
    batches: Dict[str, Any],
) -> str:
    best: Optional[Tuple[date, str]] = None
    for raw_batch_id, batch in (batches or {}).items():
        bid = str(raw_batch_id or "").strip()
        due_date = batch_due_date(batch)
        if not bid or due_date is None:
            continue
        finish_time = finish_by_batch_rows.get(bid)
        if finish_time is not None and finish_time < due_exclusive(due_date):
            continue
        key = (due_date, bid)
        if best is None or key < best:
            best = key
    return best[1] if best is not None else ""


def bottleneck_machine_rows(results: List[Any]) -> List[Any]:
    grouped: Dict[str, List[Any]] = {}
    for result in results or ():
        machine_id = str(result.machine_id or "").strip()
        if machine_id:
            grouped.setdefault(machine_id, []).append(result)
    if not grouped:
        return []
    machine_id = max(grouped, key=lambda mid: (busy_hours(grouped[mid]), len(grouped[mid]), mid))
    return grouped[machine_id]


def busy_hours(rows: List[Any]) -> float:
    total = 0.0
    for row in rows:
        start = row.start_time
        end = row.end_time
        if isinstance(start, datetime) and isinstance(end, datetime) and end > start:
            total += (end - start).total_seconds() / 3600.0
    return float(total)


def first_changeover_pair(results: List[Any]) -> Optional[Tuple[Any, Any]]:
    grouped: Dict[str, List[Any]] = {}
    for result in results or ():
        machine_id = str(result.machine_id or "").strip()
        if machine_id:
            grouped.setdefault(machine_id, []).append(result)
    for rows in grouped.values():
        previous = None
        previous_type = ""
        for row in sorted(rows, key=result_time_key):
            # Point events neither switch nor separate their timed neighbours; an unknown type does.
            if row.start_time == row.end_time:
                continue
            current_type = op_type(row)
            if previous is not None and type_transition(previous_type, current_type, previous.op_id, row.op_id) == 1:
                return previous, row
            previous, previous_type = row, current_type
    return None


def result_time_key(row: Any) -> Tuple[datetime, datetime, int]:
    return (
        row.start_time,
        row.end_time,
        int(row.op_id or 0),
    )


def op_type(result: Any) -> str:
    return result.op_type_id or ""


def pick_resource_pair(pool: Dict[str, Any]) -> Optional[Tuple[str, str, int]]:
    operators_by_machine = pool.get("operators_by_machine")
    pair_rank = pool.get("pair_rank")
    if not isinstance(operators_by_machine, dict) or not isinstance(pair_rank, dict):
        return None
    for machine_id in sorted(str(key) for key in operators_by_machine.keys()):
        operators = [
            text
            for item in operators_by_machine.get(machine_id) or ()
            for text in (str(item).strip(),)
            if text
        ]
        if len(operators) < 2:
            continue
        for operator_id in reversed(operators):
            # 排名都是 build_resource_pool 算出的整数（邻域降级覆盖为 -1）；没有排名的人机对
            # 与自动派工 auto_assign._pair_rank 同口径按 9999。
            rank = pair_rank.get((operator_id, machine_id), 9999)
            if rank > -1:
                return operator_id, machine_id, rank
    return None


__all__ = [
    "batch_id",
    "bottleneck_machine_rows",
    "earliest_due_pressure_batch",
    "finish_by_batch",
    "first_changeover_pair",
    "latest_result",
    "most_tardy_batch",
    "pick_resource_pair",
]
