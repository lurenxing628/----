from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.types import ScheduleResult


def dispatch_batch_order(
    scheduler: Any,
    *,
    sorted_ops: List[Any],
    batches: Dict[str, Any],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    batch_progress: Dict[str, datetime],
    external_group_cache: Dict[Tuple[str, str], Tuple[datetime, datetime]],
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    machine_busy_hours: Dict[str, float],
    operator_busy_hours: Dict[str, float],
    last_op_type_by_machine: Dict[str, str],
    last_end_by_machine: Dict[str, datetime],
    auto_assign_enabled: bool,
    resource_pool: Optional[Dict[str, Any]],
    results: List[ScheduleResult],
    errors: List[str],
    blocked_batches: set,
    scheduled_count: int,
    failed_count: int,
) -> Tuple[int, int]:
    """
    batch_order 派工：按 batch_order 全局排序后的工序列表逐条排入。

    注意：
    - 该函数保持与原 GreedyScheduler.schedule 内 batch_order 分支的行为一致：
      - 无效 batch_id：计 failed + errors
      - 任一工序失败：阻断该批次后续工序（failed++ 逐条计入）
    """
    for op in sorted_ops:
        bid = ""
        try:
            bid = str(getattr(op, "batch_id", "") or "")
            if bid not in batches:
                failed_count += 1
                errors.append(f"工序 {getattr(op, 'op_code', '-') or '-'}：找不到所属批次 {bid}")
                continue
            if bid in blocked_batches:
                failed_count += 1
                continue

            batch = batches[bid]

            if (getattr(op, "source", "internal") or "internal").strip() == "external":
                result, _blocked = scheduler._schedule_external(  # type: ignore[attr-defined]
                    op, batch, batch_progress, external_group_cache, base_time, errors, end_dt_exclusive
                )
            else:
                result, _blocked = scheduler._schedule_internal(  # type: ignore[attr-defined]
                    op,
                    batch,
                    batch_progress,
                    machine_timeline,
                    operator_timeline,
                    base_time,
                    errors,
                    end_dt_exclusive,
                    machine_downtimes,
                    auto_assign_enabled=auto_assign_enabled,
                    resource_pool=resource_pool,
                    last_op_type_by_machine=last_op_type_by_machine,
                    machine_busy_hours=machine_busy_hours,
                    operator_busy_hours=operator_busy_hours,
                )

            if result and result.start_time and result.end_time:
                results.append(result)
                batch_progress[bid] = result.end_time
                scheduled_count += 1
                if (result.source or "").strip() == "internal" and result.machine_id:
                    try:
                        mid0 = str(result.machine_id or "").strip()
                        oid0 = str(result.operator_id or "").strip()
                        h = (result.end_time - result.start_time).total_seconds() / 3600.0
                        if mid0:
                            machine_busy_hours[mid0] = machine_busy_hours.get(mid0, 0.0) + float(h)
                            prev_end = last_end_by_machine.get(mid0)
                            if prev_end is None or result.end_time > prev_end:
                                last_end_by_machine[mid0] = result.end_time
                        if oid0:
                            operator_busy_hours[oid0] = operator_busy_hours.get(oid0, 0.0) + float(h)
                    except Exception:
                        pass
                    ot = (result.op_type_name or "").strip()
                    if ot:
                        last_op_type_by_machine[str(result.machine_id).strip()] = ot
            else:
                failed_count += 1
                # batch_order 模式也保持“批次串行”约束：任一工序失败则阻断该批次后续工序
                blocked_batches.add(bid)
        except Exception as e:
            failed_count += 1
            op_code = getattr(op, "op_code", "-") or "-"
            errors.append(f"工序 {op_code} 排产异常：{str(e)}")
            try:
                scheduler.logger.exception(f"工序 {op_code} 排产异常")  # type: ignore[attr-defined]
            except Exception:
                pass
            if bid:
                blocked_batches.add(bid)

    return scheduled_count, failed_count

