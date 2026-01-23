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
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .sort_strategies import BatchForSort, SortStrategy, StrategyFactory, parse_strategy


@dataclass
class ScheduleResult:
    """单道工序排程结果（供落库与追溯使用）。"""

    op_id: int  # BatchOperations.id
    op_code: str
    batch_id: str
    seq: int
    machine_id: Optional[str] = None
    operator_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    source: str = "internal"  # internal/external


@dataclass
class ScheduleSummary:
    """排程摘要（供留痕与页面提示使用）。"""

    success: bool
    total_ops: int
    scheduled_ops: int
    failed_ops: int
    warnings: List[str]
    errors: List[str]
    duration_seconds: float


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


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    # 仅日期：当作当天 00:00
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return None


class GreedyScheduler:
    """贪心排产算法（可由服务层注入日历与配置）。"""

    def __init__(self, calendar_service, config_service=None, logger: Optional[logging.Logger] = None):
        self.calendar = calendar_service
        self.config = config_service
        self.logger = logger or logging.getLogger(__name__)

    def schedule(
        self,
        operations: List[Any],
        batches: Dict[str, Any],
        strategy: Optional[SortStrategy] = None,
        strategy_params: Optional[Dict[str, Any]] = None,
        start_dt: Optional[datetime] = None,
        end_date: Any = None,
        machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]] = None,
    ) -> Tuple[List[ScheduleResult], ScheduleSummary, SortStrategy, Dict[str, Any]]:
        """
        执行排产。

        Returns:
            (results, summary, used_strategy, used_strategy_params)
        """
        t0 = datetime.now()
        warnings: List[str] = []
        errors: List[str] = []

        base_time = start_dt or datetime.now()
        end_d = _parse_date(end_date)
        end_dt_exclusive: Optional[datetime] = None
        if end_d:
            end_dt_exclusive = datetime(end_d.year, end_d.month, end_d.day, 0, 0, 0) + timedelta(days=1)

        # 获取排序策略：优先使用调用方传入，其次从配置读取
        if strategy is None:
            if self.config is not None:
                try:
                    strategy_key = self.config.get("sort_strategy", "priority_first")
                except Exception:
                    strategy_key = "priority_first"
            else:
                strategy_key = "priority_first"
            strategy = parse_strategy(strategy_key, default=SortStrategy.PRIORITY_FIRST)

        # 权重策略参数：优先用调用方传入，否则从配置读取
        used_params: Dict[str, Any] = {}
        if strategy == SortStrategy.WEIGHTED:
            if strategy_params is not None:
                used_params = {
                    "priority_weight": float(strategy_params.get("priority_weight", 0.4)),
                    "due_weight": float(strategy_params.get("due_weight", 0.5)),
                }
            elif self.config is not None:
                def _cfg_float(key: str, default: float) -> float:
                    try:
                        return float(self.config.get(key, default))
                    except Exception:
                        return float(default)

                used_params = {
                    "priority_weight": _cfg_float("priority_weight", 0.4),
                    "due_weight": _cfg_float("due_weight", 0.5),
                }
            else:
                used_params = {"priority_weight": 0.4, "due_weight": 0.5}
        else:
            used_params = dict(strategy_params or {})

        # 排序批次
        sorter = StrategyFactory.create(strategy, **used_params)
        batch_list: List[BatchForSort] = []
        for b in batches.values():
            batch_list.append(
                BatchForSort(
                    batch_id=str(getattr(b, "batch_id", "") or ""),
                    priority=str(getattr(b, "priority", "") or "normal"),
                    due_date=_parse_date(getattr(b, "due_date", None)),
                    ready_status=str(getattr(b, "ready_status", "") or "yes"),
                    ready_date=_parse_date(getattr(b, "ready_date", None)),
                    created_at=_parse_datetime(getattr(b, "created_at", None)),
                )
            )
        sorted_batches = sorter.sort(batch_list)
        batch_order = {b.batch_id: i for i, b in enumerate(sorted_batches)}

        # 按批次优先级和工序顺序排序工序（稳定）
        def _op_key(op: Any):
            bid = str(getattr(op, "batch_id", "") or "")
            seq = int(getattr(op, "seq", 0) or 0)
            oid = int(getattr(op, "id", 0) or 0)
            return (batch_order.get(bid, 999999), bid, seq, oid)

        sorted_ops = sorted(operations, key=_op_key)

        self.logger.info(f"排产开始：批次数={len(batches)} 工序数={len(sorted_ops)} 策略={sorter.get_name()}")

        # 资源占用追踪（V1 简化：只追踪“最后占用结束时间”足以满足冲突错开示例）
        machine_timeline: Dict[str, List[Tuple[datetime, datetime]]] = {}
        operator_timeline: Dict[str, List[Tuple[datetime, datetime]]] = {}
        batch_progress: Dict[str, datetime] = {}  # batch_id -> 最后完成时间（初始化会考虑 ready_date）

        # 批次“齐套日期（ready_date）”：作为批次最早可开工时间下限
        # 约定：ready_date 为空 -> 视为已齐套；不为空 -> 最早从该日班次开始排产
        for b in batches.values():
            bid = str(getattr(b, "batch_id", "") or "")
            rd = getattr(b, "ready_date", None)
            rd_d = _parse_date(rd)
            if bid and rd_d:
                dt0 = datetime(rd_d.year, rd_d.month, rd_d.day, 0, 0, 0)
                try:
                    p = getattr(b, "priority", None)
                    dt_ready = self.calendar.adjust_to_working_time(dt0, priority=p)
                except Exception:
                    dt_ready = dt0
                batch_progress[bid] = max(batch_progress.get(bid, base_time), dt_ready)

        # 外部组合并周期缓存：同一 batch 的同一 ext_group_id 只推进一次
        external_group_cache: Dict[Tuple[str, str], Tuple[datetime, datetime]] = {}

        results: List[ScheduleResult] = []
        scheduled_count = 0
        failed_count = 0
        blocked_batches: set = set()

        for op in sorted_ops:
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
                    result, blocked = self._schedule_external(
                        op, batch, batch_progress, external_group_cache, base_time, errors, end_dt_exclusive
                    )
                else:
                    result, blocked = self._schedule_internal(
                        op,
                        batch,
                        batch_progress,
                        machine_timeline,
                        operator_timeline,
                        base_time,
                        errors,
                        end_dt_exclusive,
                        machine_downtimes,
                    )

                if result and result.start_time and result.end_time:
                    results.append(result)
                    batch_progress[bid] = result.end_time
                    scheduled_count += 1
                else:
                    failed_count += 1
                    if blocked:
                        blocked_batches.add(bid)
            except Exception as e:
                failed_count += 1
                op_code = getattr(op, "op_code", "-") or "-"
                errors.append(f"工序 {op_code} 排产异常：{str(e)}")
                self.logger.exception(f"工序 {op_code} 排产异常")

        duration = (datetime.now() - t0).total_seconds()
        summary = ScheduleSummary(
            success=(failed_count == 0),
            total_ops=len(sorted_ops),
            scheduled_ops=scheduled_count,
            failed_ops=failed_count,
            warnings=warnings,
            errors=errors,
            duration_seconds=duration,
        )

        self.logger.info(f"排产结束：成功={scheduled_count}/{len(sorted_ops)} 失败={failed_count} 耗时={duration:.2f}s")
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
    ) -> Tuple[Optional[ScheduleResult], bool]:
        """排产外部工序：不占资源，只占用自然日周期。"""
        bid = str(getattr(op, "batch_id", "") or "")
        prev_end = batch_progress.get(bid, base_time)

        # merged 外部组：整组作为一个时间块（组内工序同起止）
        merge_mode = (getattr(op, "ext_merge_mode", None) or "").strip()
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
                end = self.calendar.add_calendar_days(start, total_days_f)
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
        end = self.calendar.add_calendar_days(start, ext_days_f)
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
            ),
            False,
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
    ) -> Tuple[Optional[ScheduleResult], bool]:
        """排产内部工序：设备+人员双重资源约束 + 工作日历。"""
        bid = str(getattr(op, "batch_id", "") or "")

        machine_id = (getattr(op, "machine_id", None) or "").strip()
        operator_id = (getattr(op, "operator_id", None) or "").strip()
        if not machine_id or not operator_id:
            op_code = getattr(op, "op_code", "-") or "-"
            errors.append(f"内部工序未补全资源，无法排产：工序 {op_code}（machine_id/operator_id 必填）")
            return None, False

        prev_end = batch_progress.get(bid, base_time)

        machine_available = self._get_resource_available(machine_timeline, machine_id, base_time)
        operator_available = self._get_resource_available(operator_timeline, operator_id, base_time)
        earliest = max(prev_end, machine_available, operator_available)

        priority = getattr(batch, "priority", None)
        earliest = self.calendar.adjust_to_working_time(earliest, priority=priority)

        setup_hours = getattr(op, "setup_hours", 0) or 0
        unit_hours = getattr(op, "unit_hours", 0) or 0
        qty = getattr(batch, "quantity", 0) or 0
        try:
            total_hours = float(setup_hours) + float(unit_hours) * float(qty)
        except Exception:
            errors.append(f"工时不合法：工序 {getattr(op, 'op_code', '-') or '-'} setup={setup_hours!r} unit={unit_hours!r} qty={qty!r}")
            return None, False
        if total_hours < 0:
            errors.append(f"工时不能为负：工序 {getattr(op, 'op_code', '-') or '-'} total_hours={total_hours}")
            return None, False

        efficiency = 1.0
        try:
            efficiency = float(self.calendar.get_efficiency(earliest) or 1.0)
        except Exception:
            efficiency = 1.0
        if efficiency and efficiency > 0 and efficiency < 1.0:
            total_hours = total_hours / efficiency

        # 先算一次完工时间
        end = self.calendar.add_working_hours(earliest, total_hours, priority=priority)

        # 停机避让：若工序区间与停机区间重叠，则把开始时间推到停机结束后再重算
        dt_list = []
        if machine_downtimes and machine_id:
            dt_list = machine_downtimes.get(machine_id) or []
        if dt_list:
            guard = 0
            while guard < 50:
                guard += 1
                overlapped = None
                for ds, de in dt_list:
                    if end <= ds or earliest >= de:
                        continue
                    overlapped = (ds, de)
                    break
                if not overlapped:
                    break
                # 推到停机结束，并再次对齐工作日历
                earliest = max(earliest, overlapped[1])
                earliest = self.calendar.adjust_to_working_time(earliest, priority=priority)
                end = self.calendar.add_working_hours(earliest, total_hours, priority=priority)
            if guard >= 50:
                errors.append(f"停机避让迭代过多：工序 {getattr(op, 'op_code', '-') or '-'}（批次 {bid}）")
                return None, False

        if end_dt_exclusive is not None and end >= end_dt_exclusive:
            deadline = (end_dt_exclusive - timedelta(seconds=1)).strftime("%Y-%m-%d")
            errors.append(
                f"排产窗口截止到 {deadline}：内部工序 {getattr(op, 'op_code', '-') or '-'}（批次 {bid}）预计完工 {end.strftime('%Y-%m-%d %H:%M')} 超出窗口"
            )
            return None, True

        self._occupy_resource(machine_timeline, machine_id, earliest, end)
        self._occupy_resource(operator_timeline, operator_id, earliest, end)

        return (
            ScheduleResult(
                op_id=int(getattr(op, "id", 0) or 0),
                op_code=str(getattr(op, "op_code", "") or ""),
                batch_id=bid,
                seq=int(getattr(op, "seq", 0) or 0),
                machine_id=machine_id,
                operator_id=operator_id,
                start_time=earliest,
                end_time=end,
                source="internal",
            ),
            False,
        )

    @staticmethod
    def _get_resource_available(
        timeline: Dict[str, List[Tuple[datetime, datetime]]],
        resource_id: str,
        base_time: datetime,
    ) -> datetime:
        if not resource_id:
            return base_time
        segments = timeline.get(resource_id) or []
        if not segments:
            return base_time
        return max(end for _, end in segments)

    @staticmethod
    def _occupy_resource(
        timeline: Dict[str, List[Tuple[datetime, datetime]]],
        resource_id: str,
        start: datetime,
        end: datetime,
    ) -> None:
        if not resource_id:
            return
        timeline.setdefault(resource_id, []).append((start, end))

