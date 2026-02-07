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
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..dispatch_rules import DispatchRule, parse_dispatch_rule
from ..sort_strategies import BatchForSort, SortStrategy, StrategyFactory, parse_strategy
from ..types import ScheduleResult, ScheduleSummary
from .auto_assign import auto_assign_internal_resources
from .dispatch import dispatch_batch_order, dispatch_sgs
from .downtime import find_overlap_shift_end, occupy_resource
from .external_groups import schedule_external
from .seed import normalize_seed_results


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
    s = s.replace("/", "-").replace("T", " ").replace("：", ":")
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

    def _cfg_get(self, key: str, default: Any = None) -> Any:
        """
        读取配置值（算法层只依赖“纯配置快照”）。

        兼容形态：
        - dict：{key: value}
        - dataclass/namespace：通过属性访问（如 cfg.sort_strategy）
        - 旧形态：带 `.get(key, default)` 的对象（兼容历史调用方）
        """
        cfg = self.config
        if cfg is None:
            return default
        if isinstance(cfg, dict):
            return cfg.get(key, default)
        try:
            if hasattr(cfg, key):
                v = getattr(cfg, key)
                return default if v is None else v
        except Exception:
            pass
        try:
            getter = getattr(cfg, "get", None)
            if callable(getter):
                return getter(key, default)
        except Exception:
            pass
        return default

    def schedule(
        self,
        operations: List[Any],
        batches: Dict[str, Any],
        strategy: Optional[SortStrategy] = None,
        strategy_params: Optional[Dict[str, Any]] = None,
        start_dt: Optional[datetime] = None,
        end_date: Any = None,
        machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]] = None,
        batch_order_override: Optional[List[str]] = None,
        seed_results: Optional[List[ScheduleResult]] = None,
        dispatch_mode: Optional[str] = None,  # batch_order/sgs（可选；默认从配置读取）
        dispatch_rule: Optional[str] = None,  # slack/cr/atc（仅 sgs 生效；可选；默认从配置读取）
        resource_pool: Optional[Dict[str, Any]] = None,  # 自动选人/选机的候选池（由服务层预构建；可选）
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
            try:
                strategy_key = self._cfg_get("sort_strategy", "priority_first")
            except Exception:
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
                        return float(self._cfg_get(key, default))
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

        # 派工模式（V1.2）：
        # - batch_order：保持 V1 行为（按批次顺序全局排序工序）
        # - sgs：就绪集合（eligible set）动态派工（Serial SGS），提升利用率/降低拖期的空间更大
        if dispatch_mode is None and self.config is not None:
            try:
                dispatch_mode = str(self._cfg_get("dispatch_mode", "batch_order"))
            except Exception:
                dispatch_mode = "batch_order"
        dispatch_mode_key = str(dispatch_mode or "batch_order").strip().lower() or "batch_order"
        if dispatch_mode_key not in ("batch_order", "sgs"):
            dispatch_mode_key = "batch_order"

        if dispatch_rule is None and self.config is not None:
            try:
                dispatch_rule = str(self._cfg_get("dispatch_rule", "slack"))
            except Exception:
                dispatch_rule = "slack"
        dispatch_rule_enum = parse_dispatch_rule(dispatch_rule, default=DispatchRule.SLACK)

        # 自动选人/选机（仅在内部工序缺省资源时触发；默认关闭，保持 V1 行为）
        auto_assign_enabled = False
        if self.config is not None:
            try:
                v = str(self._cfg_get("auto_assign_enabled", "no") or "").strip().lower()
                auto_assign_enabled = v in ("yes", "y", "true", "1", "on")
            except Exception:
                auto_assign_enabled = False

        # 把派工参数写入 used_params（用于留痕；不影响旧逻辑）
        try:
            used_params["dispatch_mode"] = dispatch_mode_key
            used_params["dispatch_rule"] = dispatch_rule_enum.value
            used_params["auto_assign_enabled"] = "yes" if auto_assign_enabled else "no"
        except Exception:
            pass

        # 排序批次（允许外部覆盖 batch order，用于 multi-start / 局部扰动）
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
        def _op_key(op: Any):
            bid = str(getattr(op, "batch_id", "") or "")
            seq = int(getattr(op, "seq", 0) or 0)
            oid = int(getattr(op, "id", 0) or 0)
            return (batch_order.get(bid, 999999), bid, seq, oid)

        # seed_results：规范化 + 去重防御
        seed_op_ids = set()
        if seed_results:
            normalized_seed, seed_op_ids, seed_warnings = normalize_seed_results(seed_results=seed_results, operations=operations)
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
                bid = str(sr.batch_id or "")
                if bid:
                    batch_progress[bid] = max(batch_progress.get(bid, base_time), sr.end_time)
                if (sr.source or "").strip().lower() == "internal":
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
            if missing_seed_operator:
                sample = ", ".join([x for x in missing_seed_operator_samples if x and x != "?"][:5])
                warnings.append(
                    f"seed_results 内部工序缺少 operator_id：{missing_seed_operator} 条"
                    f"{('（示例 op_id=' + sample + '）') if sample else ''}；已按可用字段占用时间线，但这些 seed 无法冻结人员资源。"
                )

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
        bid = str(getattr(op, "batch_id", "") or "")

        machine_id = (getattr(op, "machine_id", None) or "").strip()
        operator_id = (getattr(op, "operator_id", None) or "").strip()
        if not machine_id or not operator_id:
            # resource_pool 可能是空 dict（调用方显式提供但无候选）；用 is not None 区分“未提供”(None)
            if auto_assign_enabled and resource_pool is not None:
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
                    machine_id, operator_id = chosen
                else:
                    op_code = getattr(op, "op_code", "-") or "-"
                    errors.append(f"内部工序未补全资源，且自动分配失败：工序 {op_code}")
                    return None, False
            else:
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
        if total_hours_base < 0:
            errors.append(f"工时不能为负：工序 {getattr(op, 'op_code', '-') or '-'} total_hours={total_hours_base}")
            return None, False

        # 简化：效率取“开工时刻”的效率；若 earliest 因避让跨日/跨班次，则需重算
        def _scaled_hours(start: datetime) -> float:
            eff = 1.0
            try:
                eff = float(self.calendar.get_efficiency(start, operator_id=operator_id) or 1.0)
            except Exception:
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
                source="internal",
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
        )

    # timeline 工具已统一到 greedy/downtime.py
