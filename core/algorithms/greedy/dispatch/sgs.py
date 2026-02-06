from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.dispatch_rules import DispatchInputs, DispatchRule, build_dispatch_key
from core.algorithms.types import ScheduleResult

from ..downtime import get_resource_available


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    if not s:
        return None
    # 兼容 YYYY/MM/DD
    s = s.replace("/", "-")
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def dispatch_sgs(
    scheduler: Any,
    *,
    sorted_ops: List[Any],
    batches: Dict[str, Any],
    batch_order: Dict[str, int],
    dispatch_rule: DispatchRule,
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
    Serial SGS（eligible set）派工：每个批次只暴露“下一道”可排工序，动态选择最优候选。

    注意：保持与原 GreedyScheduler.schedule 内 sgs 分支的行为一致：
    - 无效 batch_id：计 failed + errors
    - 任一工序失败：阻断该批次，并将“剩余工序”一次性计入 failed（保证 summary 口径一致）
    """

    # 就绪集合动态派工（Serial SGS）：每个批次只暴露“下一道”可排工序
    ops_by_batch: Dict[str, List[Any]] = {}
    # 注意：total_ops 基于 sorted_ops 统计；此处若静默过滤无效 batch_id，会导致 scheduled+failed != total
    # 因此对无效 batch_id 的工序计为失败，并写入 errors（与 batch_order 口径一致）。
    for op in sorted_ops:
        bid = str(getattr(op, "batch_id", "") or "")
        if bid not in batches:
            failed_count += 1
            errors.append(f"工序 {getattr(op, 'op_code', '-') or '-'}：找不到所属批次 {bid}")
            continue
        ops_by_batch.setdefault(bid, []).append(op)
    for bid, lst in ops_by_batch.items():
        lst.sort(key=lambda x: (int(getattr(x, "seq", 0) or 0), int(getattr(x, "id", 0) or 0)))

    # 确保遍历顺序稳定（按 batch_order，再按 batch_id）
    batch_ids_in_order = sorted(list(ops_by_batch.keys()), key=lambda x: (batch_order.get(x, 999999), x))
    next_idx: Dict[str, int] = {bid: 0 for bid in batch_ids_in_order}

    # last_op_type_by_machine / last_end_by_machine 已在 seed_results 阶段预热，用于换型 tie-break

    # ATC 需要一个平均处理时间尺度（简化：对内部工序 total_hours 做均值）
    proc_samples: List[float] = []
    for bid, lst in ops_by_batch.items():
        b = batches.get(bid)
        if not b:
            continue
        qty = getattr(b, "quantity", 0) or 0
        for op in lst:
            if (getattr(op, "source", "internal") or "internal").strip().lower() != "internal":
                continue
            setup_hours = getattr(op, "setup_hours", 0) or 0
            unit_hours = getattr(op, "unit_hours", 0) or 0
            try:
                h = float(setup_hours) + float(unit_hours) * float(qty)
            except Exception:
                h = 0.0
            if h and h > 0:
                proc_samples.append(float(h))
    avg_proc_hours = (sum(proc_samples) / float(len(proc_samples))) if proc_samples else 1.0

    while True:
        candidates: List[Tuple[str, Any]] = []
        for bid in batch_ids_in_order:
            if bid in blocked_batches:
                continue
            idx = int(next_idx.get(bid, 0) or 0)
            lst = ops_by_batch.get(bid) or []
            if idx >= len(lst):
                continue
            candidates.append((bid, lst[idx]))
        if not candidates:
            break

        best_pair: Optional[Tuple[str, Any]] = None
        best_key: Optional[Tuple[float, ...]] = None
        for bid, op in candidates:
            try:
                batch = batches[bid]
                priority = getattr(batch, "priority", None)
                due_d = _parse_date(getattr(batch, "due_date", None))
                seq = int(getattr(op, "seq", 0) or 0)
                oid = int(getattr(op, "id", 0) or 0)
                score_penalty = 0.0  # 0=正常可估算；1=不可估算（应劣于所有正常候选）

                # 估算（用于打分，不占资源）
                if (getattr(op, "source", "internal") or "internal").strip().lower() == "external":
                    prev_end = batch_progress.get(bid, base_time)
                    merge_mode = (getattr(op, "ext_merge_mode", None) or "").strip().lower()
                    ext_group_id = (getattr(op, "ext_group_id", None) or "").strip()
                    if merge_mode == "merged" and ext_group_id:
                        cached = external_group_cache.get((bid, ext_group_id))
                        if cached:
                            est_start, est_end = cached
                        else:
                            total_days = getattr(op, "ext_group_total_days", None)
                            try:
                                total_days_f = float(total_days) if total_days is not None and str(total_days).strip() != "" else None
                            except Exception:
                                total_days_f = None
                            if not total_days_f or total_days_f <= 0:
                                # 不可估算：打分阶段给一个“惩罚 key”，避免 best_pair 为空后无条件选 candidates[0]
                                score_penalty = 1.0
                                est_start = prev_end
                                est_end = prev_end
                            else:
                                est_start = prev_end
                                est_end = scheduler.calendar.add_calendar_days(est_start, total_days_f)
                    else:
                        ext_days = getattr(op, "ext_days", None)
                        try:
                            ext_days_f = float(ext_days) if ext_days is not None and str(ext_days).strip() != "" else None
                        except Exception:
                            ext_days_f = None
                        if ext_days_f is None:
                            ext_days_f = 1.0
                        if ext_days_f <= 0:
                            # 不可估算：打分阶段给惩罚 key（真实排产阶段仍会报错并阻断批次）
                            score_penalty = 1.0
                            est_start = prev_end
                            est_end = prev_end
                        else:
                            est_start = prev_end
                            est_end = scheduler.calendar.add_calendar_days(est_start, ext_days_f)
                    proc_h = max((est_end - est_start).total_seconds() / 3600.0, 0.0)
                    change_pen = 0
                    if score_penalty and score_penalty > 0:
                        # 仅用于打分：避免 proc_hours=0 导致 CR/ATC 极端值；并使其在 tie-break 中更差
                        try:
                            proc_h = max(float(avg_proc_hours), 1e-6)
                        except Exception:
                            proc_h = 1.0
                        change_pen = 1
                else:
                    machine_id = (getattr(op, "machine_id", None) or "").strip()
                    operator_id = (getattr(op, "operator_id", None) or "").strip()
                    if not machine_id or not operator_id:
                        # 缺资源：实际排产一定会失败；打分阶段必须惩罚，避免在 ATC/CR 下被优先选择。
                        score_penalty = 1.0
                        est_start = batch_progress.get(bid, base_time)
                        est_end = est_start
                        # 仅用于打分：给一个稳定的处理时间尺度，避免 proc_hours=0 触发极端派工 key
                        try:
                            proc_h = max(float(avg_proc_hours), 1e-6)
                        except Exception:
                            proc_h = 1.0
                        change_pen = 1
                    else:
                        prev_end = batch_progress.get(bid, base_time)
                        est_start = max(prev_end, base_time)
                        # 粗略考虑“资源最新占用结束”（不扫描间隙；用于评分足够）
                        est_start = max(est_start, get_resource_available(machine_timeline, machine_id, base_time))
                        est_start = max(est_start, get_resource_available(operator_timeline, operator_id, base_time))
                        est_start = scheduler.calendar.adjust_to_working_time(est_start, priority=priority, operator_id=operator_id)

                        setup_hours = getattr(op, "setup_hours", 0) or 0
                        unit_hours = getattr(op, "unit_hours", 0) or 0
                        qty = getattr(batch, "quantity", 0) or 0
                        try:
                            total_hours = float(setup_hours) + float(unit_hours) * float(qty)
                        except Exception:
                            total_hours = 0.0
                            score_penalty = 1.0
                        eff = 1.0
                        try:
                            eff = float(scheduler.calendar.get_efficiency(est_start, operator_id=operator_id) or 1.0)
                        except Exception:
                            eff = 1.0
                        if score_penalty and score_penalty > 0:
                            # 工时不可解析：打分阶段按“不可估算”处理，避免成为最优候选
                            try:
                                proc_h = max(float(avg_proc_hours), 1e-6)
                            except Exception:
                                proc_h = 1.0
                            est_end = est_start
                            change_pen = 1
                        else:
                            if eff and eff > 0 and eff != 1.0:
                                total_hours = total_hours / eff
                            proc_h = max(float(total_hours), 0.0)
                            est_end = scheduler.calendar.add_working_hours(
                                est_start, proc_h, priority=priority, operator_id=operator_id
                            )

                            last_type = (last_op_type_by_machine.get(machine_id) or "").strip()
                            cur_type = (str(getattr(op, "op_type_name", None) or "") or "").strip()
                            if last_type and cur_type and last_type != cur_type:
                                change_pen = 1
                            else:
                                change_pen = 0

                k = build_dispatch_key(
                    DispatchInputs(
                        rule=dispatch_rule,
                        priority=str(priority or "normal"),
                        due_date=due_d,
                        est_start=est_start,
                        est_end=est_end,
                        proc_hours=float(proc_h),
                        avg_proc_hours=float(avg_proc_hours),
                        changeover_penalty=int(change_pen),
                        batch_order=int(batch_order.get(bid, 999999)),
                        batch_id=bid,
                        seq=int(seq),
                        op_id=int(oid),
                    )
                )
                # 评分 key：先按可估算性排序（正常优于不可估算），再按 dispatch rule/tie-break 排序
                k = (float(score_penalty),) + tuple(k)

                if best_key is None or k < best_key:
                    best_key = k
                    best_pair = (bid, op)
            except Exception:
                continue

        if best_pair is None:
            best_pair = candidates[0]

        bid, op = best_pair
        try:
            batch = batches[bid]
            if (getattr(op, "source", "internal") or "internal").strip().lower() == "external":
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
                next_idx[bid] = int(next_idx.get(bid, 0) or 0) + 1
                if (result.source or "").strip().lower() == "internal" and result.machine_id:
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
                # SGS 下无法“跳过”前序工序：任何失败都应阻断该批次，避免死循环/前后约束被破坏
                blocked_batches.add(bid)
                # 阻断后，该批次剩余工序不会再被尝试；为保持 summary 口径一致（scheduled_ops+failed_ops==total_ops）
                # 将“当前工序之后的剩余工序”计入失败数（类似 batch_order 模式对 blocked 批次逐条计失败）。
                try:
                    idx0 = int(next_idx.get(bid, 0) or 0)
                    lst0 = ops_by_batch.get(bid) or []
                    rest = max(int(len(lst0)) - (idx0 + 1), 0)
                    failed_count += int(rest)
                except Exception:
                    pass
        except Exception as e:
            failed_count += 1
            op_code = getattr(op, "op_code", "-") or "-"
            errors.append(f"工序 {op_code} 排产异常：{str(e)}")
            try:
                scheduler.logger.exception(f"工序 {op_code} 排产异常")  # type: ignore[attr-defined]
            except Exception:
                pass
            blocked_batches.add(bid)
            try:
                idx0 = int(next_idx.get(bid, 0) or 0)
                lst0 = ops_by_batch.get(bid) or []
                rest = max(int(len(lst0)) - (idx0 + 1), 0)
                failed_count += int(rest)
            except Exception:
                pass

    return scheduled_count, failed_count

