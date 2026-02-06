from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from core.models.enums import BatchStatus, SourceType


def persist_schedule(
    svc,
    *,
    version: int,
    results: List[Any],
    summary: Any,
    used_strategy: Any,
    used_params: Dict[str, Any],
    batches: Dict[str, Any],
    operations: List[Any],
    normalized_batch_ids: List[str],
    created_by: str,
    simulate: bool,
    frozen_op_ids: Set[int],
    result_status: str,
    result_summary_json: str,
    result_summary_obj: Dict[str, Any],
    missing_internal_resource_op_ids: Set[int],
    overdue_items: List[Dict[str, Any]],
    time_cost_ms: int,
) -> None:
    """
    原子落库：Schedule + 状态更新 + ScheduleHistory
    事务后：OperationLogs（避免 logger 内部 commit 干扰原子性）
    """
    # 组装 Schedule 落库行
    schedule_rows: List[Dict[str, Any]] = []
    for r in results:
        if not getattr(r, "start_time", None) or not getattr(r, "end_time", None):
            continue
        schedule_rows.append(
            {
                "op_id": int(r.op_id),
                "machine_id": r.machine_id,
                "operator_id": r.operator_id,
                "start_time": svc._format_dt(r.start_time),
                "end_time": svc._format_dt(r.end_time),
                "lock_status": "locked" if int(r.op_id) in frozen_op_ids else "unlocked",
                "version": int(version),
            }
        )

    with svc.tx_manager.transaction():
        if schedule_rows:
            svc.schedule_repo.bulk_create(schedule_rows)

        if not simulate:
            # 批次工序：成功排到的置 scheduled；失败的保持原状态（便于继续补全）
            scheduled_op_ids = {int(r.op_id) for r in results if r and getattr(r, "op_id", None)}
            assigned_by_op_id: Dict[int, Dict[str, Any]] = {
                int(r.op_id): {"machine_id": r.machine_id, "operator_id": r.operator_id}
                for r in results
                if r
                and int(getattr(r, "op_id", 0) or 0) > 0
                and (r.source or "").strip().lower() == SourceType.INTERNAL.value
            }
            for op in operations:
                if not op.id:
                    continue
                if int(op.id) in scheduled_op_ids:
                    svc.op_repo.update(int(op.id), {"status": "scheduled"})
                    # 自动分配补全：仅在原本缺省资源时回写 machine/operator（避免覆盖人工已选）
                    if int(op.id) in missing_internal_resource_op_ids:
                        assign = assigned_by_op_id.get(int(op.id)) or {}
                        mc = (assign.get("machine_id") or "").strip()
                        oid = (assign.get("operator_id") or "").strip()
                        updates: Dict[str, Any] = {}
                        # 允许“部分补全”：算法可能只补齐其中一个资源；且避免覆盖人工已选
                        if mc and not (str(getattr(op, "machine_id", "") or "").strip()):
                            updates["machine_id"] = mc
                        if oid and not (str(getattr(op, "operator_id", "") or "").strip()):
                            updates["operator_id"] = oid
                        if updates:
                            svc.op_repo.update(int(op.id), updates)

            # 批次：若本批次所有工序都排到 -> scheduled，否则保持 pending
            by_batch_total: Dict[str, int] = {}
            by_batch_scheduled: Dict[str, int] = {}
            for op in operations:
                by_batch_total[op.batch_id] = by_batch_total.get(op.batch_id, 0) + 1
                if op.id and int(op.id) in scheduled_op_ids:
                    by_batch_scheduled[op.batch_id] = by_batch_scheduled.get(op.batch_id, 0) + 1

            for bid, _b in batches.items():
                total = by_batch_total.get(bid, 0)
                ok = by_batch_scheduled.get(bid, 0)
                new_status = BatchStatus.SCHEDULED.value if total > 0 and ok == total else BatchStatus.PENDING.value
                svc.batch_repo.update(bid, {"status": new_status})

        # 排产历史留痕（DB）
        svc.history_repo.create(
            {
                "version": int(version),
                "strategy": used_strategy.value,
                "batch_count": len(batches),
                "op_count": int(getattr(summary, "total_ops", 0)),
                "result_status": result_status,
                "result_summary": result_summary_json,
                "created_by": str(created_by or "system"),
            }
        )

    # 操作日志留痕（OperationLogs）：放到事务后（避免内部 commit 干扰原子性）
    if svc.op_logger is not None:
        detail = {
            "is_simulation": bool(simulate),
            "version": int(version),
            "strategy": used_strategy.value,
            "strategy_params": used_params or {},
            "algo": result_summary_obj.get("algo"),
            "batch_ids": list(normalized_batch_ids),
            "batch_count": len(batches),
            "op_count": int(getattr(summary, "total_ops", 0)),
            "scheduled_ops": int(getattr(summary, "scheduled_ops", 0)),
            "failed_ops": int(getattr(summary, "failed_ops", 0)),
            "result_status": result_status,
            "overdue_count": len(overdue_items),
            "overdue_batches_sample": overdue_items[:10],
            "time_cost_ms": int(time_cost_ms),
        }
        svc.op_logger.info(
            module="scheduler",
            action="simulate" if simulate else "schedule",
            target_type="schedule",
            target_id=str(version),
            detail=detail,
        )

