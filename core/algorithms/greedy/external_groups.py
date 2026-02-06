from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.types import ScheduleResult


def schedule_external(
    scheduler: Any,
    *,
    op: Any,
    batch: Any,
    batch_progress: Dict[str, datetime],
    external_group_cache: Dict[Tuple[str, str], Tuple[datetime, datetime]],
    base_time: datetime,
    errors: List[str],
    end_dt_exclusive: Optional[datetime],
) -> Tuple[Optional[ScheduleResult], bool]:
    """排产外部工序：不占资源，只占用自然日周期。"""
    bid = str(getattr(op, "batch_id", "") or "")
    prev_end = batch_progress.get(bid, base_time)

    # merged 外部组：整组作为一个时间块（组内工序同起止）
    merge_mode = (getattr(op, "ext_merge_mode", None) or "").strip().lower()
    ext_group_id = (getattr(op, "ext_group_id", None) or "").strip()
    if merge_mode == "merged" and ext_group_id:
        cache_key = (bid, ext_group_id)
        cached = external_group_cache.get(cache_key)
        if cached:
            start, end = cached
        else:
            total_days = getattr(op, "ext_group_total_days", None)
            try:
                total_days_f = float(total_days) if total_days is not None and str(total_days).strip() != "" else None
            except Exception:
                total_days_f = None
            if not total_days_f or total_days_f <= 0:
                errors.append(f"外部组合并周期未设置或不合法：批次 {bid} 组 {ext_group_id} total_days={total_days!r}")
                return None, False
            start = prev_end
            end = scheduler.calendar.add_calendar_days(start, total_days_f)
            external_group_cache[cache_key] = (start, end)

        if end_dt_exclusive is not None and end >= end_dt_exclusive:
            deadline = (end_dt_exclusive - timedelta(seconds=1)).strftime("%Y-%m-%d")
            errors.append(
                f"排产窗口截止到 {deadline}：外协组 {ext_group_id}（批次 {bid}）预计完工 {end.strftime('%Y-%m-%d %H:%M')} 超出窗口"
            )
            return None, True

        return (
            ScheduleResult(
                op_id=int(getattr(op, "id", 0) or 0),
                op_code=str(getattr(op, "op_code", "") or ""),
                batch_id=bid,
                seq=int(getattr(op, "seq", 0) or 0),
                start_time=start,
                end_time=end,
                source="external",
                op_type_name=str(getattr(op, "op_type_name", None) or "") or None,
            ),
            False,
        )

    # separate（或无组）：按单道工序 ext_days 推进
    ext_days = getattr(op, "ext_days", None)
    try:
        ext_days_f = float(ext_days) if ext_days is not None and str(ext_days).strip() != "" else None
    except Exception:
        ext_days_f = None
    if ext_days_f is None:
        ext_days_f = 1.0
    if ext_days_f <= 0:
        errors.append(f"外协周期不合法：工序 {getattr(op, 'op_code', '-') or '-'} ext_days={ext_days!r}")
        return None, False

    start = prev_end
    end = scheduler.calendar.add_calendar_days(start, ext_days_f)
    if end_dt_exclusive is not None and end >= end_dt_exclusive:
        deadline = (end_dt_exclusive - timedelta(seconds=1)).strftime("%Y-%m-%d")
        errors.append(
            f"排产窗口截止到 {deadline}：外协工序 {getattr(op, 'op_code', '-') or '-'}（批次 {bid}）预计完工 {end.strftime('%Y-%m-%d %H:%M')} 超出窗口"
        )
        return None, True

    return (
        ScheduleResult(
            op_id=int(getattr(op, "id", 0) or 0),
            op_code=str(getattr(op, "op_code", "") or ""),
            batch_id=bid,
            seq=int(getattr(op, "seq", 0) or 0),
            start_time=start,
            end_time=end,
            source="external",
            op_type_name=str(getattr(op, "op_type_name", None) or "") or None,
        ),
        False,
    )

