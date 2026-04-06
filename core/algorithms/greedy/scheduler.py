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
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms.value_domains import INTERNAL
from core.services.common.strict_parse import parse_optional_date

from ..sort_strategies import BatchForSort, SortStrategy, StrategyFactory
from ..types import ScheduleResult, ScheduleSummary
from .algo_stats import ensure_algo_stats, increment_counter
from .auto_assign import auto_assign_internal_resources
from .config_adapter import cfg_get
from .dispatch import dispatch_batch_order, dispatch_sgs
from .downtime import find_overlap_shift_end, occupy_resource
from .external_groups import schedule_external
from .schedule_params import parse_date as _parse_date
from .schedule_params import parse_datetime as _parse_datetime
from .schedule_params import resolve_schedule_params
from .seed import normalize_seed_results


class GreedyScheduler:
    """贪心排产算法（可由服务层注入日历与配置）。"""

    def __init__(self, calendar_service, config_service=None, logger: Optional[logging.Logger] = None):
        self.calendar = calendar_service
        self.config = config_service
        self.logger = logger or logging.getLogger(__name__)
        self._last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

    def _cfg_get(self, key: str, default: Any = None) -> Any:
        """
        读取配置值（算法层只依赖“纯配置快照”）。

        兼容形态：
        - dict：{key: value}
        - dataclass/namespace：通过属性访问（如 cfg.sort_strategy）
        - 旧形态：带 `.get(key, default)` 的对象（兼容历史调用方）
        """
        return cfg_get(self.config, key, default)

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

        # -------------------------
        # 关键 ID 规范化（算法层统一 str(...).strip()）
        # -------------------------
        # 说明：可选 warm-start 已做 strip；此处把 greedy/dispatch 侧也统一，避免脏输入导致分叉。
        def _norm_id(v: Any) -> str:
            try:
                return str(v or "").strip()
            except Exception:
                try:
                    return str(v).strip()
                except Exception:
                    return ""

        batches_norm: Dict[str, Any] = {}
        for k, b in (batches or {}).items():
            nk = _norm_id(k)
            if not nk:
                nk = _norm_id(getattr(b, "batch_id", None))
            if not nk:
                # 极端兜底：保留原 key（可能为空），避免直接丢批次
                nk = str(k or "")
                warnings.append(f"检测到空 batch_id（key/字段均为空）：{k!r}")
            if nk in batches_norm and batches_norm.get(nk) is not b:
                warnings.append(f"批次ID规范化冲突：{k!r} -> {nk!r} 已存在；已保留首次出现。")
                continue
            batches_norm[nk] = b
        batches = batches_norm

        # 排序批次（允许外部覆盖 batch order，用于 multi-start / 局部扰动）
        sorter = StrategyFactory.create(strategy, **used_params)
        batch_list: List[BatchForSort] = []
        for bid0, b in batches.items():
            due_raw = getattr(b, "due_date", None)
            due_date = parse_optional_date(due_raw, field="due_date") if strict_mode else _parse_date(due_raw)
            batch_list.append(
                BatchForSort(
                    batch_id=str(bid0 or "").strip(),
                    priority=str(getattr(b, "priority", "") or "normal"),
                    due_date=due_date,
                    ready_status=str(getattr(b, "ready_status", "") or "yes"),
                    ready_date=_parse_date(getattr(b, "ready_date", None)),
                    created_at=_parse_datetime(getattr(b, "created_at", None)),
                )
            )
        sorted_batches = sorter.sort(batch_list, base_date=base_time.date())
        if batch_order_override:
            order_list = [str(x).strip() for x in batch_order_override if str(x).strip()]
            # 过滤不存在的批次，并把漏掉的批次补到末尾（按 sorter 的默认顺序）
            order_list = [bid for bid in order_list if bid in batches]
            # 去重：batch_order_override 可能包含重复批次（dict 会被最后一次覆盖），这里保留首次出现顺序
            order_list = list(dict.fromkeys(order_list))
            existed = set(order_list)
            for b in sorted_batches:
                if b.batch_id not in existed:
                    order_list.append(b.batch_id)
                    existed.add(b.batch_id)
            batch_order = {bid: i for i, bid in enumerate(order_list)}
        else:
            batch_order = {b.batch_id: i for i, b in enumerate(sorted_batches)}

        # 按批次优先级和工序顺序排序工序（稳定）
        def _safe_int(v: Any) -> int:
            try:
                return int(v or 0)
            except Exception:
                try:
                    return int(float(v))
                except Exception:
                    return 0

        def _op_key(op: Any):
            bid = str(getattr(op, "batch_id", "") or "").strip()
            seq = _safe_int(getattr(op, "seq", 0))
            oid = _safe_int(getattr(op, "id", 0))
            return (batch_order.get(bid, 999999), bid, seq, oid)

        # seed_results：规范化 + 去重防御
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
                    oid = int(getattr(op, "id", 0) or 0)
                except Exception:
                    oid = 0
                if oid and oid in seed_op_ids:
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

        # 资源占用追踪（V1 简化：只追踪“最后占用结束时间”足以满足冲突错开示例）
        machine_timeline: Dict[str, List[Tuple[datetime, datetime]]] = {}
        operator_timeline: Dict[str, List[Tuple[datetime, datetime]]] = {}
        batch_progress: Dict[str, datetime] = {}  # batch_id -> 最后完成时间（初始化会考虑 ready_date）
        # 运行期统计/状态（用于自动分配与换型 tie-break）
        machine_busy_hours: Dict[str, float] = {}
        operator_busy_hours: Dict[str, float] = {}
        last_op_type_by_machine: Dict[str, str] = {}
        last_end_by_machine: Dict[str, datetime] = {}

        # 批次“齐套日期（ready_date）”：作为批次最早可开工时间下限
        # 约定：ready_date 为空 -> 视为已齐套；不为空 -> 最早从该日班次开始排产
        for bid0, b in batches.items():
            bid = str(bid0 or "").strip()
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
        seed_count = 0

        # 预置（冻结窗口等场景）：把已存在的排程作为“固定结果”写入 results，并占用资源
        if seed_results:
            # 统计 seed_results 内部工序缺失资源的情况（避免“计入排程但未冻结资源”导致重叠）
            missing_seed_machine = 0
            missing_seed_operator = 0
            missing_seed_machine_samples: List[str] = []
            missing_seed_operator_samples: List[str] = []
            for sr in seed_results:
                if not sr or not sr.start_time or not sr.end_time:
                    continue
                # 仅对可定位到真实工序的 seed 计入统计/结果（防止 op_id<=0 造成重复排产与 total_ops 口径错误）
                try:
                    if int(getattr(sr, "op_id", 0) or 0) <= 0:
                        continue
                except Exception:
                    continue
                results.append(sr)
                scheduled_count += 1
                seed_count += 1
                bid = str(sr.batch_id or "").strip()
                if bid:
                    batch_progress[bid] = max(batch_progress.get(bid, base_time), sr.end_time)
                if (sr.source or "").strip().lower() == INTERNAL:
                    mid = str(sr.machine_id or "").strip()
                    oid = str(sr.operator_id or "").strip()

                    # 资源占用：按可用字段分别占用（避免因缺一项而完全不占用导致重叠）
                    if mid:
                        occupy_resource(machine_timeline, mid, sr.start_time, sr.end_time)
                    else:
                        missing_seed_machine += 1
                        if len(missing_seed_machine_samples) < 5:
                            missing_seed_machine_samples.append(str(getattr(sr, "op_id", "") or "").strip() or "?")

                    if oid:
                        occupy_resource(operator_timeline, oid, sr.start_time, sr.end_time)
                    else:
                        missing_seed_operator += 1
                        if len(missing_seed_operator_samples) < 5:
                            missing_seed_operator_samples.append(str(getattr(sr, "op_id", "") or "").strip() or "?")

                    # 负荷统计：同样按可用字段分别累计
                    try:
                        h = (sr.end_time - sr.start_time).total_seconds() / 3600.0
                        if mid:
                            machine_busy_hours[mid] = machine_busy_hours.get(mid, 0.0) + float(h)
                        if oid:
                            operator_busy_hours[oid] = operator_busy_hours.get(oid, 0.0) + float(h)
                    except Exception:
                        pass

                    ot = (sr.op_type_name or "").strip()
                    if mid and ot and sr.end_time:
                        prev_end = last_end_by_machine.get(mid)
                        if prev_end is None or sr.end_time > prev_end:
                            last_end_by_machine[mid] = sr.end_time
                            last_op_type_by_machine[mid] = ot

            # seed_results 内部工序缺失资源：给出汇总 warning（不阻断排产）
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
        bid = str(getattr(op, "batch_id", "") or "").strip()

        # 防御：字段可能不是 str（例如 int），避免直接 .strip() 崩溃
        machine_id = str(getattr(op, "machine_id", None) or "").strip()
        operator_id = str(getattr(op, "operator_id", None) or "").strip()
        if not machine_id or not operator_id:
            # resource_pool 可能是空 dict（调用方显式提供但无候选）；用 is not None 区分“未提供”(None)
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

        # 先从“批次前序完工/起算时间”出发，再做资源避让（支持已有区间占用/冻结窗口）
        earliest = max(prev_end, base_time)
        priority = getattr(batch, "priority", None)
        earliest = self.calendar.adjust_to_working_time(earliest, priority=priority, operator_id=operator_id)

        setup_hours = getattr(op, "setup_hours", 0) or 0
        unit_hours = getattr(op, "unit_hours", 0) or 0
        qty = getattr(batch, "quantity", 0) or 0
        try:
            total_hours_base = float(setup_hours) + float(unit_hours) * float(qty)
        except Exception:
            errors.append(
                f"工时不合法：工序 {getattr(op, 'op_code', '-') or '-'} setup={setup_hours!r} unit={unit_hours!r} qty={qty!r}"
            )
            return None, False
        if (not math.isfinite(float(total_hours_base))) or total_hours_base < 0:
            errors.append(f"工时不能为负：工序 {getattr(op, 'op_code', '-') or '-'} total_hours={total_hours_base}")
            return None, False

        # 简化：效率取“开工时刻”的效率；若 earliest 因避让跨日/跨班次，则需重算
        def _scaled_hours(start: datetime) -> float:
            eff = 1.0
            try:
                eff = float(self.calendar.get_efficiency(start, operator_id=operator_id) or 1.0)
            except Exception:
                eff = 1.0
            if (not math.isfinite(float(eff))) or float(eff) <= 0:
                increment_counter(self, "internal_efficiency_fallback_count")
                eff = 1.0
            h = float(total_hours_base)
            if eff and eff > 0 and eff != 1.0:
                return h / eff
            return h

        # 资源/停机避让：若区间与“设备/人员/停机”任一已占用区间重叠，则把开始时间推到重叠区间结束后再重算
        dt_list: List[Tuple[datetime, datetime]] = []
        if machine_downtimes and machine_id:
            dt_list = machine_downtimes.get(machine_id) or []

        guard = 0
        total_hours = _scaled_hours(earliest)
        end = self.calendar.add_working_hours(earliest, total_hours, priority=priority, operator_id=operator_id)
        while guard < 200:
            guard += 1

            shift_to: Optional[datetime] = None
            m_shift = find_overlap_shift_end(machine_timeline.get(machine_id) or [], earliest, end)
            o_shift = find_overlap_shift_end(operator_timeline.get(operator_id) or [], earliest, end)
            d_shift = find_overlap_shift_end(dt_list, earliest, end)
            for x in (m_shift, o_shift, d_shift):
                if x is None:
                    continue
                if shift_to is None or x > shift_to:
                    shift_to = x

            if shift_to is None:
                break

            earliest = max(earliest, shift_to)
            earliest = self.calendar.adjust_to_working_time(earliest, priority=priority, operator_id=operator_id)
            total_hours = _scaled_hours(earliest)
            end = self.calendar.add_working_hours(earliest, total_hours, priority=priority, operator_id=operator_id)

        if guard >= 200:
            errors.append(f"资源/停机避让迭代过多：工序 {getattr(op, 'op_code', '-') or '-'}（批次 {bid}）")
            return None, False

        if end_dt_exclusive is not None and end >= end_dt_exclusive:
            deadline = (end_dt_exclusive - timedelta(seconds=1)).strftime("%Y-%m-%d")
            errors.append(
                f"排产窗口截止到 {deadline}：内部工序 {getattr(op, 'op_code', '-') or '-'}（批次 {bid}）预计完工 {end.strftime('%Y-%m-%d %H:%M')} 超出窗口"
            )
            return None, True

        occupy_resource(machine_timeline, machine_id, earliest, end)
        occupy_resource(operator_timeline, operator_id, earliest, end)

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
