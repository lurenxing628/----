from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.greedy.date_parsers import due_exclusive, parse_date


def batch_id(result: Any) -> str:
    return str(getattr(result, "batch_id", "") or "").strip()


def latest_result(results: List[Any]) -> Optional[Any]:
    rows = [
        row
        for row in list(results or [])
        if getattr(row, "end_time", None) is not None and batch_id(row)
    ]
    if not rows:
        return None
    return max(
        rows,
        key=lambda row: (
            getattr(row, "end_time", datetime.min),
            batch_id(row),
            int(getattr(row, "seq", 0) or 0),
        ),
    )


def positive_count(value: Any) -> int:
    try:
        return max(int(len(value or [])), 0)
    except Exception:
        return 0


def finish_by_batch(results: List[Any]) -> Dict[str, datetime]:
    out: Dict[str, datetime] = {}
    for result in list(results or []):
        bid = batch_id(result)
        end_time = getattr(result, "end_time", None)
        if not bid or not isinstance(end_time, datetime):
            continue
        current = out.get(bid)
        if current is None or end_time > current:
            out[bid] = end_time
    return out


def batch_due_date(batch: Any) -> Optional[date]:
    due_raw = getattr(batch, "due_date", None)
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
) -> Optional[Tuple[str, float]]:
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
    return best


def tardy_batch_count(finish_by_batch_rows: Dict[str, datetime], batches: Dict[str, Any]) -> int:
    return 0 if most_tardy_batch(finish_by_batch_rows=finish_by_batch_rows, batches=batches) is None else 1


def due_batch_count(batches: Dict[str, Any]) -> int:
    return sum(1 for batch in (batches or {}).values() if batch_due_date(batch) is not None)


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


def bottleneck_machine_rows(results: List[Any]) -> Tuple[str, List[Any]]:
    grouped: Dict[str, List[Any]] = {}
    for result in list(results or []):
        machine_id = str(getattr(result, "machine_id", "") or "").strip()
        if machine_id:
            grouped.setdefault(machine_id, []).append(result)
    if not grouped:
        return "", []
    machine_id = max(grouped, key=lambda mid: (busy_hours(grouped[mid]), len(grouped[mid]), mid))
    return machine_id, grouped[machine_id]


def busy_hours(rows: List[Any]) -> float:
    total = 0.0
    for row in rows:
        start = getattr(row, "start_time", None)
        end = getattr(row, "end_time", None)
        if isinstance(start, datetime) and isinstance(end, datetime) and end > start:
            total += (end - start).total_seconds() / 3600.0
    return float(total)


def first_changeover_pair(results: List[Any]) -> Optional[Tuple[Any, Any]]:
    grouped: Dict[str, List[Any]] = {}
    for result in list(results or []):
        machine_id = str(getattr(result, "machine_id", "") or "").strip()
        if machine_id:
            grouped.setdefault(machine_id, []).append(result)
    for rows in grouped.values():
        rows.sort(key=result_time_key)
        previous = None
        for row in rows:
            if previous is not None and op_type(previous) and op_type(row) and op_type(previous) != op_type(row):
                return previous, row
            previous = row
    return None


def result_time_key(row: Any) -> Tuple[datetime, datetime, int]:
    return (
        getattr(row, "start_time", datetime.min),
        getattr(row, "end_time", datetime.min),
        int(getattr(row, "op_id", 0) or 0),
    )


def op_type(result: Any) -> str:
    return str(getattr(result, "op_type_name", "") or "").strip()


def changeover_count(results: List[Any]) -> int:
    count = 0
    grouped: Dict[str, List[Any]] = {}
    for result in list(results or []):
        machine_id = str(getattr(result, "machine_id", "") or "").strip()
        if machine_id:
            grouped.setdefault(machine_id, []).append(result)
    for rows in grouped.values():
        rows.sort(key=result_time_key)
        previous = ""
        for row in rows:
            current = op_type(row)
            if previous and current and previous != current:
                count += 1
            if current:
                previous = current
    return int(count)


def copy_resource_pool(resource_pool: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(resource_pool, dict):
        return {}
    out: Dict[str, Any] = {}
    for key in ("machines_by_op_type", "operators_by_machine", "machines_by_operator", "pair_rank"):
        value = resource_pool.get(key)
        if isinstance(value, dict):
            out[key] = {
                item_key: list(item_value) if isinstance(item_value, list) else item_value
                for item_key, item_value in value.items()
            }
        else:
            out[key] = {}
    return out


def pick_resource_pair(pool: Dict[str, Any]) -> Optional[Tuple[str, str, int]]:
    operators_by_machine = pool.get("operators_by_machine")
    pair_rank = pool.get("pair_rank")
    if not isinstance(operators_by_machine, dict) or not isinstance(pair_rank, dict):
        return None
    for machine_id in sorted(str(key) for key in operators_by_machine.keys()):
        operators = [
            str(item).strip()
            for item in list(operators_by_machine.get(machine_id) or [])
            if str(item).strip()
        ]
        if len(operators) < 2:
            continue
        operator_id = operators[-1]
        rank_value = pair_rank.get((operator_id, machine_id), 9999)
        try:
            rank = int(rank_value)
        except (TypeError, ValueError, OverflowError):
            rank = 9999
        return operator_id, machine_id, rank
    return None


def resource_pair_count(pool: Dict[str, Any]) -> int:
    pair_rank = pool.get("pair_rank")
    return len(pair_rank) if isinstance(pair_rank, dict) else 0


__all__ = [
    "batch_id",
    "bottleneck_machine_rows",
    "changeover_count",
    "copy_resource_pool",
    "due_batch_count",
    "earliest_due_pressure_batch",
    "finish_by_batch",
    "first_changeover_pair",
    "latest_result",
    "most_tardy_batch",
    "pick_resource_pair",
    "positive_count",
    "resource_pair_count",
    "tardy_batch_count",
]
