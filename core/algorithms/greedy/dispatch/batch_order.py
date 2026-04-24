from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.types import ScheduleResult
from core.algorithms.value_domains import EXTERNAL, INTERNAL

from .runtime_state import accumulate_busy_hours, update_machine_last_state

_SCHEDULE_OPERATION_FAILED_MESSAGE = "排产异常，请查看系统日志。"


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
    strict_mode: bool = False,
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
            bid = str(getattr(op, "batch_id", "") or "").strip()
            if bid not in batches:
                failed_count += 1
                errors.append(f"工序 {getattr(op, 'op_code', '-') or '-'}：找不到所属批次 {bid}")
                continue
            if bid in blocked_batches:
                failed_count += 1
                continue

            batch = batches[bid]

            if (getattr(op, "source", INTERNAL) or INTERNAL).strip().lower() == EXTERNAL:
                result, _blocked = scheduler._schedule_external(  # type: ignore[attr-defined]
                    op,
                    batch,
                    batch_progress,
                    external_group_cache,
                    base_time,
                    errors,
                    end_dt_exclusive,
                    strict_mode=bool(strict_mode),
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
                if (result.source or "").strip().lower() == INTERNAL and result.machine_id:
                    accumulate_busy_hours(
                        machine_busy_hours=machine_busy_hours,
                        operator_busy_hours=operator_busy_hours,
                        machine_id=str(result.machine_id or "").strip(),
                        operator_id=str(result.operator_id or "").strip(),
                        start_time=result.start_time,
                        end_time=result.end_time,
                    )
                    update_machine_last_state(
                        last_end_by_machine=last_end_by_machine,
                        last_op_type_by_machine=last_op_type_by_machine,
                        machine_id=str(result.machine_id or "").strip(),
                        end_time=result.end_time,
                        op_type_name=result.op_type_name,
                        seed_mode=False,
                    )
                results.append(result)
                batch_progress[bid] = max(batch_progress.get(bid, base_time), result.end_time)
                scheduled_count += 1
            else:
                failed_count += 1
                # batch_order 模式也保持“批次串行”约束：任一工序失败则阻断该批次后续工序
                blocked_batches.add(bid)
        except Exception:
            failed_count += 1
            op_code = getattr(op, "op_code", "-") or "-"
            errors.append(f"工序 {op_code} {_SCHEDULE_OPERATION_FAILED_MESSAGE}")
            try:
                scheduler.logger.exception(f"工序 {op_code} 排产异常")  # type: ignore[attr-defined]
            except Exception:
                pass
            if bid:
                blocked_batches.add(bid)

    return scheduled_count, failed_count
