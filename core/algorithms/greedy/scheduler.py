from __future__ import annotations

"""
贪心排产算法（Phase 7 / P7-02, P7-06）。

要点（对齐开发文档.md）：
- 内部工序：设备 + 人员 双重资源约束
- 外部工序：不占内部资源，仅按自然日（天）推进
- 前后约束：同一批次按工序顺序串行推进
- 工作日历：使用 CalendarService 的 adjust_to_working_time / add_working_hours / get_efficiency / add_calendar_days
- 外部组合并周期（merged）：整组作为一个时间块，组内每道外部工序落同一 start/end
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.value_domains import INTERNAL
from core.services.common.strict_parse import parse_optional_date, parse_optional_datetime

from ..sort_strategies import BatchForSort, SortStrategy, StrategyFactory
from ..types import ScheduleResult, ScheduleSummary
from .algo_stats import ensure_algo_stats, increment_counter
from .auto_assign import auto_assign_internal_resources
from .date_parsers import parse_date, parse_datetime
from .dispatch import dispatch_batch_order, dispatch_sgs
from .dispatch.runtime_state import accumulate_busy_hours, update_machine_last_state
from .downtime import occupy_resource
from .external_groups import schedule_external
from .internal_slot import estimate_internal_slot
from .schedule_params import resolve_schedule_params
from .seed import normalize_seed_results


def normalize_text_id(value: Any) -> str:
    try:
        return str(value or "").strip()
    except Exception:
        try:
            return str(value).strip()
        except Exception:
            return ""


def resolve_batch_sort_batch_id(batch_key: Any, batch: Any) -> str:
    normalized_key = normalize_text_id(batch_key)
    if normalized_key:
        return normalized_key
    return normalize_text_id(getattr(batch, "batch_id", None))


def build_normalized_batches_map(batches: Optional[Dict[str, Any]], *, warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for raw_key, batch in (batches or {}).items():
        batch_id = resolve_batch_sort_batch_id(raw_key, batch)
        if not batch_id:
            batch_id = str(raw_key or "")
            if warnings is not None:
                warnings.append(f"检测到空 batch_id（key/字段均为空）：{raw_key!r}")
        if batch_id in normalized and normalized.get(batch_id) is not batch:
            if warnings is not None:
                warnings.append(f"批次ID规范化冲突：{raw_key!r} -> {batch_id!r} 已存在；已保留首次出现。")
            continue
        normalized[batch_id] = batch
    return normalized


def _parse_due_date_for_sort(value: Any, *, strict_mode: bool) -> Optional[Any]:
    return parse_optional_date(value, field="due_date") if strict_mode else parse_date(value)


def _parse_ready_date_for_sort(value: Any, *, strict_mode: bool) -> Optional[Any]:
    return parse_optional_date(value, field="ready_date") if strict_mode else parse_date(value)


def _parse_created_at_for_sort(value: Any, *, strict_mode: bool, strategy: SortStrategy) -> Optional[datetime]:
    if strict_mode and strategy == SortStrategy.FIFO:
        return parse_optional_datetime(value, field="created_at")
    return parse_datetime(value)


def build_batch_sort_inputs(
    batches: Dict[str, Any],
    *,
    strict_mode: bool,
    strategy: SortStrategy,
) -> List[BatchForSort]:
    batch_for_sort: List[BatchForSort] = []
    for batch_key, batch in (batches or {}).items():
        batch_id = resolve_batch_sort_batch_id(batch_key, batch)
        if not batch_id:
            continue
        batch_for_sort.append(
            BatchForSort(
                batch_id=batch_id,
                priority=str(getattr(batch, "priority", "") or "normal"),
                due_date=_parse_due_date_for_sort(getattr(batch, "due_date", None), strict_mode=bool(strict_mode)),
                ready_status=str(getattr(batch, "ready_status", "") or "yes"),
                ready_date=_parse_ready_date_for_sort(getattr(batch, "ready_date", None), strict_mode=bool(strict_mode)),
                created_at=_parse_created_at_for_sort(
                    getattr(batch, "created_at", None), strict_mode=bool(strict_mode), strategy=strategy
                ),
            )
        )
    return batch_for_sort


class GreedyScheduler:
    """贪心排产算法（可由服务层注入日历与配置）。"""

    def __init__(self, calendar_service, config_service=None, logger: Optional[logging.Logger] = None):
        self.calendar = calendar_service
        self.config = config_service
        self.logger = logger or logging.getLogger(__name__)
        self._last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

    def schedule(
        self,
        operations: List[Any],
        batches: Dict[str, Any],
        strategy: Optional[SortStrategy] = None,
        strategy_params: Optional[Dict[str, Any]] = None,
        start_dt: Any = None,
        end_date: Any = None,
        machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]] = None,
        batch_order_override: Optional[List[str]] = None,
        seed_results: Optional[List[ScheduleResult]] = None,
        dispatch_mode: Optional[str] = None,  # batch_order/sgs（可选；默认从配置读取）
        dispatch_rule: Optional[str] = None,  # slack/cr/atc（仅 sgs 生效；可选；默认从配置读取）
        resource_pool: Optional[Dict[str, Any]] = None,  # 自动选人/选机的候选池（由服务层预构建；可选）
        strict_mode: bool = False,
    ) -> Tuple[List[ScheduleResult], ScheduleSummary, SortStrategy, Dict[str, Any]]:
        """
        执行排产。

        Returns:
            (results, summary, used_strategy, used_strategy_params)
        """
        t0 = datetime.now()
        warnings: List[str] = []
        errors: List[str] = []
        self._last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}
        ensure_algo_stats(self)

        params = resolve_schedule_params(
            config=self.config,
            strategy=strategy,
            strategy_params=strategy_params,
            start_dt=start_dt,
            end_date=end_date,
            dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule,
            resource_pool=resource_pool,
            algo_stats=self,
            strict_mode=bool(strict_mode),
        )
        warnings.extend(params.warnings)
        base_time = params.base_time
        end_dt_exclusive = params.end_dt_exclusive
        strategy = params.strategy
        used_params = params.used_params
        dispatch_mode_key = params.dispatch_mode_key
        dispatch_rule_enum = params.dispatch_rule_enum
        auto_assign_enabled = params.auto_assign_enabled

        batches = build_normalized_batches_map(batches, warnings=warnings)
        sorter = StrategyFactory.create(strategy, **used_params)

        if machine_downtimes:
            machine_downtimes = {
                normalize_text_id(resource_id): sorted(list(segments or []), key=lambda segment: (segment[0], segment[1]))
                for resource_id, segments in machine_downtimes.items()
                if normalize_text_id(resource_id)
            }

        override_order: List[str] = []
        if batch_order_override:
            seen_override = set()
            for item in batch_order_override:
                batch_id = normalize_text_id(item)
                if not batch_id or batch_id not in batches or batch_id in seen_override:
                    continue
                seen_override.add(batch_id)
                override_order.append(batch_id)

        if override_order and len(override_order) == len(batches):
            batch_order = {batch_id: index for index, batch_id in enumerate(override_order)}
        else:
            batch_for_sort = build_batch_sort_inputs(batches, strict_mode=bool(strict_mode), strategy=strategy)
            sorted_batches = sorter.sort(batch_for_sort, base_date=base_time.date())
            if override_order:
                existed = set(override_order)
                for batch in sorted_batches:
                    if batch.batch_id in existed:
                        continue
                    override_order.append(batch.batch_id)
                    existed.add(batch.batch_id)
                batch_order = {batch_id: index for index, batch_id in enumerate(override_order)}
            else:
                batch_order = {batch.batch_id: index for index, batch in enumerate(sorted_batches)}

        def _safe_int(value: Any) -> int:
            try:
                return int(value or 0)
            except Exception:
                try:
                    return int(float(value))
                except Exception:
                    return 0

        def _op_key(op: Any):
            batch_id = normalize_text_id(getattr(op, "batch_id", ""))
            seq = _safe_int(getattr(op, "seq", 0))
            op_id = _safe_int(getattr(op, "id", 0))
            return (batch_order.get(batch_id, 999999), batch_id, seq, op_id)

        seed_op_ids = set()
        if seed_results:
            normalized_seed, seed_op_ids, seed_warnings = normalize_seed_results(seed_results=seed_results, operations=operations, algo_stats=self)
            seed_results = normalized_seed
            if seed_warnings:
                warnings.extend(seed_warnings)

        ops_for_sort = operations
        if seed_op_ids:
            filtered: List[Any] = []
            dropped = 0
            for op in operations:
                try:
                    op_id = int(getattr(op, "id", 0) or 0)
                except Exception:
                    op_id = 0
                if op_id and op_id in seed_op_ids:
                    dropped += 1
                    continue
                filtered.append(op)
            if dropped:
                warnings.append(f"检测到 seed_results 与 operations 重叠：已过滤 {dropped} 道工序避免重复排产。")
                increment_counter(self, "seed_overlap_filtered_count", dropped)
            ops_for_sort = filtered

        sorted_ops = sorted(ops_for_sort, key=_op_key)

        extra = ""
        if dispatch_mode_key == "sgs":
            extra = f" 派工=sgs({dispatch_rule_enum.value})"
        self.logger.info(f"排产开始：批次数={len(batches)} 工序数={len(sorted_ops)} 策略={sorter.get_name()}{extra}")

        machine_timeline: Dict[str, List[Tuple[datetime, datetime]]] = {}
        operator_timeline: Dict[str, List[Tuple[datetime, datetime]]] = {}
        batch_progress: Dict[str, datetime] = {}
        machine_busy_hours: Dict[str, float] = {}
        operator_busy_hours: Dict[str, float] = {}
        last_op_type_by_machine: Dict[str, str] = {}
        last_end_by_machine: Dict[str, datetime] = {}

        for batch_id, batch in batches.items():
            ready_date = _parse_ready_date_for_sort(getattr(batch, "ready_date", None), strict_mode=bool(strict_mode))
            if not batch_id or ready_date is None:
                continue
            ready_start = datetime(ready_date.year, ready_date.month, ready_date.day, 0, 0, 0)
            priority = getattr(batch, "priority", None)
            ready_dt = self.calendar.adjust_to_working_time(ready_start, priority=priority)
            batch_progress[batch_id] = max(batch_progress.get(batch_id, base_time), ready_dt)

        external_group_cache: Dict[Tuple[str, str], Tuple[datetime, datetime]] = {}
        results: List[ScheduleResult] = []
        scheduled_count = 0
        failed_count = 0
        blocked_batches: set = set()
        seed_count = 0

        if seed_results:
            missing_seed_machine = 0
            missing_seed_operator = 0
            missing_seed_machine_samples: List[str] = []
            missing_seed_operator_samples: List[str] = []
            for sr in seed_results:
                if not sr or not sr.start_time or not sr.end_time:
                    continue
                if not isinstance(sr.start_time, datetime) or not isinstance(sr.end_time, datetime):
                    continue
                try:
                    if int(getattr(sr, "op_id", 0) or 0) <= 0:
                        continue
                except Exception:
                    continue

                bid = normalize_text_id(sr.batch_id)
                if (sr.source or "").strip().lower() == INTERNAL:
                    machine_id = normalize_text_id(sr.machine_id)
                    operator_id = normalize_text_id(sr.operator_id)
                    if machine_id:
                        occupy_resource(machine_timeline, machine_id, sr.start_time, sr.end_time)
                    else:
                        missing_seed_machine += 1
                        if len(missing_seed_machine_samples) < 5:
                            missing_seed_machine_samples.append(normalize_text_id(getattr(sr, "op_id", "") or "?") or "?")
                    if operator_id:
                        occupy_resource(operator_timeline, operator_id, sr.start_time, sr.end_time)
                    else:
                        missing_seed_operator += 1
                        if len(missing_seed_operator_samples) < 5:
                            missing_seed_operator_samples.append(normalize_text_id(getattr(sr, "op_id", "") or "?") or "?")
                    accumulate_busy_hours(
                        machine_busy_hours=machine_busy_hours,
                        operator_busy_hours=operator_busy_hours,
                        machine_id=machine_id,
                        operator_id=operator_id,
                        start_time=sr.start_time,
                        end_time=sr.end_time,
                    )
                    update_machine_last_state(
                        last_end_by_machine=last_end_by_machine,
                        last_op_type_by_machine=last_op_type_by_machine,
                        machine_id=machine_id,
                        end_time=sr.end_time,
                        op_type_name=sr.op_type_name,
                        seed_mode=True,
                    )
                results.append(sr)
                scheduled_count += 1
                seed_count += 1
                if bid:
                    batch_progress[bid] = max(batch_progress.get(bid, base_time), sr.end_time)

            if missing_seed_machine:
                sample = ", ".join([x for x in missing_seed_machine_samples if x and x != "?"][:5])
                warnings.append(
                    f"seed_results 内部工序缺少 machine_id：{missing_seed_machine} 条"
                    f"{('（示例 op_id=' + sample + '）') if sample else ''}；已按可用字段占用时间线，但这些 seed 无法冻结设备资源。"
                )
                increment_counter(self, "seed_missing_machine_id_count", missing_seed_machine)
            if missing_seed_operator:
                sample = ", ".join([x for x in missing_seed_operator_samples if x and x != "?"][:5])
                warnings.append(
                    f"seed_results 内部工序缺少 operator_id：{missing_seed_operator} 条"
                    f"{('（示例 op_id=' + sample + '）') if sample else ''}；已按可用字段占用时间线，但这些 seed 无法冻结人员资源。"
                )
                increment_counter(self, "seed_missing_operator_id_count", missing_seed_operator)

        if dispatch_mode_key == "sgs":
            scheduled_count, failed_count = dispatch_sgs(
                self,
                sorted_ops=sorted_ops,
                batches=batches,
                batch_order=batch_order,
                dispatch_rule=dispatch_rule_enum,
                base_time=base_time,
                end_dt_exclusive=end_dt_exclusive,
                machine_downtimes=machine_downtimes,
                batch_progress=batch_progress,
                external_group_cache=external_group_cache,
                machine_timeline=machine_timeline,
                operator_timeline=operator_timeline,
                machine_busy_hours=machine_busy_hours,
                operator_busy_hours=operator_busy_hours,
                last_op_type_by_machine=last_op_type_by_machine,
                last_end_by_machine=last_end_by_machine,
                auto_assign_enabled=auto_assign_enabled,
                resource_pool=resource_pool,
                results=results,
                errors=errors,
                blocked_batches=blocked_batches,
                scheduled_count=scheduled_count,
                failed_count=failed_count,
                strict_mode=bool(strict_mode),
            )
        else:
            scheduled_count, failed_count = dispatch_batch_order(
                self,
                sorted_ops=sorted_ops,
                batches=batches,
                base_time=base_time,
                end_dt_exclusive=end_dt_exclusive,
                machine_downtimes=machine_downtimes,
                batch_progress=batch_progress,
                external_group_cache=external_group_cache,
                machine_timeline=machine_timeline,
                operator_timeline=operator_timeline,
                machine_busy_hours=machine_busy_hours,
                operator_busy_hours=operator_busy_hours,
                last_op_type_by_machine=last_op_type_by_machine,
                last_end_by_machine=last_end_by_machine,
                auto_assign_enabled=auto_assign_enabled,
                resource_pool=resource_pool,
                results=results,
                errors=errors,
                blocked_batches=blocked_batches,
                scheduled_count=scheduled_count,
                failed_count=failed_count,
                strict_mode=bool(strict_mode),
            )

        duration = (datetime.now() - t0).total_seconds()
        total_ops = int(len(sorted_ops) + seed_count)
        summary = ScheduleSummary(
            success=(failed_count == 0),
            total_ops=total_ops,
            scheduled_ops=scheduled_count,
            failed_ops=failed_count,
            warnings=warnings,
            errors=errors,
            duration_seconds=duration,
        )

        self.logger.info(f"排产结束：成功={scheduled_count}/{total_ops} 失败={failed_count} 耗时={duration:.2f}s")
        return results, summary, strategy, used_params

    def _schedule_external(
        self,
        op: Any,
        batch: Any,
        batch_progress: Dict[str, datetime],
        external_group_cache: Dict[Tuple[str, str], Tuple[datetime, datetime]],
        base_time: datetime,
        errors: List[str],
        end_dt_exclusive: Optional[datetime],
        strict_mode: bool = False,
    ) -> Tuple[Optional[ScheduleResult], bool]:
        return schedule_external(
            self,
            op=op,
            batch=batch,
            batch_progress=batch_progress,
            external_group_cache=external_group_cache,
            base_time=base_time,
            errors=errors,
            end_dt_exclusive=end_dt_exclusive,
            strict_mode=bool(strict_mode),
        )

    def _schedule_internal(
        self,
        op: Any,
        batch: Any,
        batch_progress: Dict[str, datetime],
        machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        base_time: datetime,
        errors: List[str],
        end_dt_exclusive: Optional[datetime],
        machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]] = None,
        *,
        auto_assign_enabled: bool = False,
        resource_pool: Optional[Dict[str, Any]] = None,
        last_op_type_by_machine: Optional[Dict[str, str]] = None,
        machine_busy_hours: Optional[Dict[str, float]] = None,
        operator_busy_hours: Optional[Dict[str, float]] = None,
    ) -> Tuple[Optional[ScheduleResult], bool]:
        """排产内部工序：设备+人员双重资源约束 + 工作日历。"""
        bid = normalize_text_id(getattr(op, "batch_id", ""))
        machine_id = normalize_text_id(getattr(op, "machine_id", None))
        operator_id = normalize_text_id(getattr(op, "operator_id", None))
        if not machine_id or not operator_id:
            if auto_assign_enabled and resource_pool is not None:
                increment_counter(self, "internal_auto_assign_attempt_count")
                chosen = self._auto_assign_internal_resources(
                    op=op,
                    batch=batch,
                    batch_progress=batch_progress,
                    machine_timeline=machine_timeline,
                    operator_timeline=operator_timeline,
                    base_time=base_time,
                    end_dt_exclusive=end_dt_exclusive,
                    machine_downtimes=machine_downtimes,
                    resource_pool=resource_pool,
                    last_op_type_by_machine=(last_op_type_by_machine or {}),
                    machine_busy_hours=(machine_busy_hours or {}),
                    operator_busy_hours=(operator_busy_hours or {}),
                )
                if chosen:
                    increment_counter(self, "internal_auto_assign_success_count")
                    machine_id, operator_id = chosen
                else:
                    increment_counter(self, "internal_auto_assign_failed_count")
                    op_code = getattr(op, "op_code", "-") or "-"
                    errors.append(f"内部工序未补全资源，且自动分配失败：工序 {op_code}")
                    return None, False
            else:
                increment_counter(self, "internal_missing_resource_without_auto_assign_count")
                op_code = getattr(op, "op_code", "-") or "-"
                errors.append(f"内部工序未补全资源，无法排产：工序 {op_code}（machine_id/operator_id 必填）")
                return None, False

        prev_end = batch_progress.get(bid, base_time)
        try:
            estimate = estimate_internal_slot(
                calendar=self.calendar,
                op=op,
                batch=batch,
                machine_id=machine_id,
                operator_id=operator_id,
                base_time=base_time,
                prev_end=prev_end,
                machine_timeline=machine_timeline.get(machine_id) or [],
                operator_timeline=operator_timeline.get(operator_id) or [],
                end_dt_exclusive=end_dt_exclusive,
                machine_downtimes=(machine_downtimes.get(machine_id) or []) if machine_downtimes and machine_id else [],
                last_op_type_by_machine=last_op_type_by_machine,
                abort_after=None,
            )
        except ValueError as exc:
            op_code = getattr(op, "op_code", "-") or "-"
            errors.append(f"工时不合法：工序 {op_code} {exc}")
            return None, False

        if estimate.abort_after_hit:
            raise RuntimeError("正式内部排产不应命中 abort_after 早停")
        if estimate.blocked_by_window:
            deadline = (end_dt_exclusive - timedelta(seconds=1)).strftime("%Y-%m-%d") if end_dt_exclusive else "-"
            errors.append(
                f"排产窗口截止到 {deadline}：内部工序 {getattr(op, 'op_code', '-') or '-'}（批次 {bid}）预计完工 {estimate.end_time.strftime('%Y-%m-%d %H:%M')} 超出窗口"
            )
            return None, True

        occupy_resource(machine_timeline, machine_id, estimate.start_time, estimate.end_time)
        occupy_resource(operator_timeline, operator_id, estimate.start_time, estimate.end_time)
        if estimate.efficiency_fallback_used:
            increment_counter(self, "internal_efficiency_fallback_count")

        return (
            ScheduleResult(
                op_id=int(getattr(op, "id", 0) or 0),
                op_code=str(getattr(op, "op_code", "") or ""),
                batch_id=bid,
                seq=int(getattr(op, "seq", 0) or 0),
                machine_id=machine_id,
                operator_id=operator_id,
                start_time=estimate.start_time,
                end_time=estimate.end_time,
                source=INTERNAL,
                op_type_name=str(getattr(op, "op_type_name", None) or "") or None,
            ),
            False,
        )

    def _auto_assign_internal_resources(
        self,
        *,
        op: Any,
        batch: Any,
        batch_progress: Dict[str, datetime],
        machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        base_time: datetime,
        end_dt_exclusive: Optional[datetime],
        machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
        resource_pool: Dict[str, Any],
        last_op_type_by_machine: Dict[str, str],
        machine_busy_hours: Dict[str, float],
        operator_busy_hours: Dict[str, float],
        probe_only: bool = False,
    ) -> Optional[Tuple[str, str]]:
        return auto_assign_internal_resources(
            self,
            op=op,
            batch=batch,
            batch_progress=batch_progress,
            machine_timeline=machine_timeline,
            operator_timeline=operator_timeline,
            base_time=base_time,
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=machine_downtimes,
            resource_pool=resource_pool,
            last_op_type_by_machine=last_op_type_by_machine,
            machine_busy_hours=machine_busy_hours,
            operator_busy_hours=operator_busy_hours,
            probe_only=probe_only,
        )

    # timeline 工具已统一到 greedy/downtime.py
