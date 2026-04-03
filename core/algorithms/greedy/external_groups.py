from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.types import ScheduleResult
from core.algorithms.value_domains import EXTERNAL, MERGED
from core.services.common.degradation import DegradationCollector
from core.services.common.field_parse import parse_field_float

from .algo_stats import increment_counter


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
    strict_mode: bool = False,
) -> Tuple[Optional[ScheduleResult], bool]:
    """排产外部工序：不占资源，只占用自然日周期。"""

    def _record_compat_counters(collector: DegradationCollector) -> None:
        counters = collector.to_counters()
        legacy_defaulted = int(counters.get("legacy_external_days_defaulted") or 0) + int(counters.get("blank_required") or 0)
        if legacy_defaulted > 0:
            increment_counter(scheduler, "legacy_external_days_defaulted_count", legacy_defaulted)


    bid = str(getattr(op, "batch_id", "") or "").strip()
    prev_end = batch_progress.get(bid, base_time)

    # merged 外部组：整组作为一个时间块（组内工序同起止）
    merge_mode = str(getattr(op, "ext_merge_mode", None) or "").strip().lower()
    ext_group_id = str(getattr(op, "ext_group_id", None) or "").strip()
    if merge_mode == MERGED and ext_group_id:
        cache_key = (bid, ext_group_id)
        cached = external_group_cache.get(cache_key)
        if cached:
            start, end = cached
        else:
            total_days = getattr(op, "ext_group_total_days", None)
            collector = DegradationCollector()
            try:
                total_days_f = float(
                    parse_field_float(
                        total_days,
                        field="ext_group_total_days",
                        strict_mode=bool(strict_mode),
                        scope="greedy.external.schedule",
                        fallback=0.0,
                        collector=collector,
                        min_value=0.0,
                        min_inclusive=False,
                    )
                )
            except Exception:
                if strict_mode:
                    raise
                total_days_f = 0.0
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
                source=EXTERNAL,
                op_type_name=str(getattr(op, "op_type_name", None) or "") or None,
            ),
            False,
        )

    # separate（或无组）：按单道工序 ext_days 推进
    ext_days = getattr(op, "ext_days", None)
    collector = DegradationCollector()
    try:
        ext_days_f = float(
            parse_field_float(
                ext_days,
                field="ext_days",
                strict_mode=bool(strict_mode),
                scope="greedy.external.schedule",
                fallback=1.0,
                collector=collector,
                min_value=0.0,
                min_inclusive=False,
            )
        )
    except Exception:
        if strict_mode:
            raise
        ext_days_f = 0.0
    _record_compat_counters(collector)
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
            source=EXTERNAL,
            op_type_name=str(getattr(op, "op_type_name", None) or "") or None,
        ),
        False,
    )

