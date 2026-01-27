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

from .dispatch_rules import DispatchInputs, DispatchRule, build_dispatch_key, parse_dispatch_rule
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
    op_type_name: Optional[str] = None


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

        # 派工模式（V1.2）：
        # - batch_order：保持 V1 行为（按批次顺序全局排序工序）
        # - sgs：就绪集合（eligible set）动态派工（Serial SGS），提升利用率/降低拖期的空间更大
        if dispatch_mode is None and self.config is not None:
            try:
                dispatch_mode = str(self.config.get("dispatch_mode", "batch_order"))
            except Exception:
                dispatch_mode = "batch_order"
        dispatch_mode_key = str(dispatch_mode or "batch_order").strip().lower() or "batch_order"
        if dispatch_mode_key not in ("batch_order", "sgs"):
            dispatch_mode_key = "batch_order"

        if dispatch_rule is None and self.config is not None:
            try:
                dispatch_rule = str(self.config.get("dispatch_rule", "slack"))
            except Exception:
                dispatch_rule = "slack"
        dispatch_rule_enum = parse_dispatch_rule(dispatch_rule, default=DispatchRule.SLACK)

        # 自动选人/选机（仅在内部工序缺省资源时触发；默认关闭，保持 V1 行为）
        auto_assign_enabled = False
        if self.config is not None:
            try:
                v = str(self.config.get("auto_assign_enabled", "no") or "").strip().lower()
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

        # 防御性处理：当 seed_results 与 operations 重叠时，避免同一工序被排两次
        # 关键点：seed_results 可能存在 op_id<=0（上游缺失/脏数据）。若不处理，会导致：
        # - seed_count 计入（写入 results）
        # - 但无法从 operations 过滤对应工序（重复排产/重复统计）
        seed_op_ids = set()
        if seed_results:
            # 建立 operations 映射：优先 op_code（全局唯一），兜底 (batch_id, seq)（仅在本次 operations 内唯一时生效）
            op_id_by_code: Dict[str, int] = {}
            bs_seen: Dict[Tuple[str, int], int] = {}
            bs_dups: set = set()
            for op in operations:
                try:
                    oid = int(getattr(op, "id", 0) or 0)
                except Exception:
                    oid = 0
                if oid <= 0:
                    continue

                code = str(getattr(op, "op_code", "") or "").strip()
                if code and code not in op_id_by_code:
                    op_id_by_code[code] = int(oid)

                bid = str(getattr(op, "batch_id", "") or "").strip()
                try:
                    seq = int(getattr(op, "seq", 0) or 0)
                except Exception:
                    seq = 0
                if bid and seq > 0:
                    key = (bid, int(seq))
                    prev = bs_seen.get(key)
                    if prev is not None and prev != int(oid):
                        bs_dups.add(key)
                    else:
                        bs_seen[key] = int(oid)

            # (batch_id, seq) 若不唯一则禁用该 key，避免误匹配
            for key in bs_dups:
                bs_seen.pop(key, None)
            op_id_by_batch_seq = bs_seen

            normalized: List[ScheduleResult] = []
            backfilled = 0
            dropped_invalid = 0
            for sr in seed_results:
                try:
                    if not sr or not getattr(sr, "start_time", None) or not getattr(sr, "end_time", None):
                        continue

                    oid0 = int(getattr(sr, "op_id", 0) or 0)
                    if oid0 <= 0:
                        # 尝试回填：op_code -> op_id
                        new_oid = 0
                        code0 = str(getattr(sr, "op_code", "") or "").strip()
                        if code0:
                            new_oid = int(op_id_by_code.get(code0, 0) or 0)

                        # 兜底： (batch_id, seq) -> op_id（仅唯一时可用）
                        if new_oid <= 0:
                            bid0 = str(getattr(sr, "batch_id", "") or "").strip()
                            try:
                                seq0 = int(getattr(sr, "seq", 0) or 0)
                            except Exception:
                                seq0 = 0
                            if bid0 and seq0 > 0:
                                new_oid = int(op_id_by_batch_seq.get((bid0, int(seq0)), 0) or 0)

                        if new_oid > 0:
                            try:
                                setattr(sr, "op_id", int(new_oid))
                                oid0 = int(new_oid)
                                backfilled += 1
                            except Exception:
                                # 退化：构造新的 ScheduleResult，保证输出/后续处理口径一致
                                try:
                                    sr = ScheduleResult(
                                        op_id=int(new_oid),
                                        op_code=str(getattr(sr, "op_code", "") or ""),
                                        batch_id=str(getattr(sr, "batch_id", "") or ""),
                                        seq=int(getattr(sr, "seq", 0) or 0),
                                        machine_id=(str(getattr(sr, "machine_id", "") or "") or None),
                                        operator_id=(str(getattr(sr, "operator_id", "") or "") or None),
                                        start_time=getattr(sr, "start_time", None),
                                        end_time=getattr(sr, "end_time", None),
                                        source=str(getattr(sr, "source", "internal") or "internal"),
                                        op_type_name=(str(getattr(sr, "op_type_name", "") or "") or None),
                                    )
                                    oid0 = int(new_oid)
                                    backfilled += 1
                                except Exception:
                                    dropped_invalid += 1
                                    continue
                        else:
                            dropped_invalid += 1
                            continue

                    if oid0 > 0:
                        seed_op_ids.add(int(oid0))
                        normalized.append(sr)
                except Exception:
                    continue

            if backfilled:
                warnings.append(
                    f"seed_results 存在 {backfilled} 条 op_id<=0 的记录，已按 op_code/batch_id+seq 回填 op_id 以避免重复排产。"
                )
            if dropped_invalid:
                warnings.append(
                    f"seed_results 存在 {dropped_invalid} 条 op_id<=0 且无法匹配的记录，已忽略（避免重复统计/排产）。"
                )
            seed_results = normalized

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
                if (sr.source or "").strip() == "internal":
                    mid = str(sr.machine_id or "").strip()
                    oid = str(sr.operator_id or "").strip()

                    # 资源占用：按可用字段分别占用（避免因缺一项而完全不占用导致重叠）
                    if mid:
                        self._occupy_resource(machine_timeline, mid, sr.start_time, sr.end_time)
                    else:
                        missing_seed_machine += 1
                        if len(missing_seed_machine_samples) < 5:
                            missing_seed_machine_samples.append(str(getattr(sr, "op_id", "") or "").strip() or "?")

                    if oid:
                        self._occupy_resource(operator_timeline, oid, sr.start_time, sr.end_time)
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
                    if (getattr(op, "source", "internal") or "internal").strip() != "internal":
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
                        if (getattr(op, "source", "internal") or "internal").strip() == "external":
                            prev_end = batch_progress.get(bid, base_time)
                            merge_mode = (getattr(op, "ext_merge_mode", None) or "").strip()
                            ext_group_id = (getattr(op, "ext_group_id", None) or "").strip()
                            if merge_mode == "merged" and ext_group_id:
                                cached = external_group_cache.get((bid, ext_group_id))
                                if cached:
                                    est_start, est_end = cached
                                else:
                                    total_days = getattr(op, "ext_group_total_days", None)
                                    try:
                                        total_days_f = (
                                            float(total_days)
                                            if total_days is not None and str(total_days).strip() != ""
                                            else None
                                        )
                                    except Exception:
                                        total_days_f = None
                                    if not total_days_f or total_days_f <= 0:
                                        # 不可估算：打分阶段给一个“惩罚 key”，避免 best_pair 为空后无条件选 candidates[0]
                                        score_penalty = 1.0
                                        est_start = prev_end
                                        est_end = prev_end
                                    else:
                                        est_start = prev_end
                                        est_end = self.calendar.add_calendar_days(est_start, total_days_f)
                            else:
                                ext_days = getattr(op, "ext_days", None)
                                try:
                                    ext_days_f = (
                                        float(ext_days)
                                        if ext_days is not None and str(ext_days).strip() != ""
                                        else None
                                    )
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
                                    est_end = self.calendar.add_calendar_days(est_start, ext_days_f)
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
                                # 留给实际排产时报错；这里给一个兜底 key（避免 best_pair 为空）
                                est_start = batch_progress.get(bid, base_time)
                                est_end = est_start
                                proc_h = 0.0
                                change_pen = 1
                            else:
                                prev_end = batch_progress.get(bid, base_time)
                                est_start = max(prev_end, base_time)
                                # 粗略考虑“资源最新占用结束”（不扫描间隙；用于评分足够）
                                est_start = max(est_start, self._get_resource_available(machine_timeline, machine_id, base_time))
                                est_start = max(est_start, self._get_resource_available(operator_timeline, operator_id, base_time))
                                est_start = self.calendar.adjust_to_working_time(est_start, priority=priority)

                                setup_hours = getattr(op, "setup_hours", 0) or 0
                                unit_hours = getattr(op, "unit_hours", 0) or 0
                                qty = getattr(batch, "quantity", 0) or 0
                                try:
                                    total_hours = float(setup_hours) + float(unit_hours) * float(qty)
                                except Exception:
                                    total_hours = 0.0
                                eff = 1.0
                                try:
                                    eff = float(self.calendar.get_efficiency(est_start) or 1.0)
                                except Exception:
                                    eff = 1.0
                                if eff and 0 < eff < 1.0:
                                    total_hours = total_hours / eff
                                proc_h = max(float(total_hours), 0.0)
                                est_end = self.calendar.add_working_hours(est_start, proc_h, priority=priority)

                                last_type = (last_op_type_by_machine.get(machine_id) or "").strip()
                                cur_type = (str(getattr(op, "op_type_name", None) or "") or "").strip()
                                if last_type and cur_type and last_type != cur_type:
                                    change_pen = 1
                                else:
                                    change_pen = 0

                        k = build_dispatch_key(
                            DispatchInputs(
                                rule=dispatch_rule_enum,
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
                    self.logger.exception(f"工序 {op_code} 排产异常")
                    blocked_batches.add(bid)
                    try:
                        idx0 = int(next_idx.get(bid, 0) or 0)
                        lst0 = ops_by_batch.get(bid) or []
                        rest = max(int(len(lst0)) - (idx0 + 1), 0)
                        failed_count += int(rest)
                    except Exception:
                        pass
        else:
            # V1 默认：按 batch_order 全局排序后逐条排入
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
                    self.logger.exception(f"工序 {op_code} 排产异常")
                    if bid:
                        blocked_batches.add(bid)

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
                op_type_name=str(getattr(op, "op_type_name", None) or "") or None,
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

        # 资源/停机避让：若区间与“设备/人员/停机”任一已占用区间重叠，则把开始时间推到重叠区间结束后再重算
        dt_list: List[Tuple[datetime, datetime]] = []
        if machine_downtimes and machine_id:
            dt_list = machine_downtimes.get(machine_id) or []

        guard = 0
        end = self.calendar.add_working_hours(earliest, total_hours, priority=priority)
        while guard < 200:
            guard += 1

            shift_to: Optional[datetime] = None
            m_shift = self._find_overlap_shift_end(machine_timeline.get(machine_id) or [], earliest, end)
            o_shift = self._find_overlap_shift_end(operator_timeline.get(operator_id) or [], earliest, end)
            d_shift = self._find_overlap_shift_end(dt_list, earliest, end)
            for x in (m_shift, o_shift, d_shift):
                if x is None:
                    continue
                if shift_to is None or x > shift_to:
                    shift_to = x

            if shift_to is None:
                break

            earliest = max(earliest, shift_to)
            earliest = self.calendar.adjust_to_working_time(earliest, priority=priority)
            end = self.calendar.add_working_hours(earliest, total_hours, priority=priority)

        if guard >= 200:
            errors.append(f"资源/停机避让迭代过多：工序 {getattr(op, 'op_code', '-') or '-'}（批次 {bid}）")
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
        """
        内部工序缺省资源时，自动选择 (machine_id, operator_id)。

        选择目标（简化的多目标）：
        1) 预计完工时间最早（end 最小）
        2) 尽量不换型（同一设备连续 op_type_name 相同优先）
        3) 负荷均衡（优先选择当前更空闲的人/机）
        4) 若存在主操/高技能标记（pair_rank 更小），作为微弱 tie-break
        """
        bid = str(getattr(op, "batch_id", "") or "")
        prev_end = batch_progress.get(bid, base_time)
        priority = getattr(batch, "priority", None)

        fixed_machine = (getattr(op, "machine_id", None) or "").strip()
        fixed_operator = (getattr(op, "operator_id", None) or "").strip()
        op_type_id = (getattr(op, "op_type_id", None) or "").strip()

        machines_by_op_type = resource_pool.get("machines_by_op_type") if isinstance(resource_pool, dict) else {}
        operators_by_machine = resource_pool.get("operators_by_machine") if isinstance(resource_pool, dict) else {}
        machines_by_operator = resource_pool.get("machines_by_operator") if isinstance(resource_pool, dict) else {}
        pair_rank = resource_pool.get("pair_rank") if isinstance(resource_pool, dict) else {}

        # 构造候选设备集合
        machine_candidates: List[str] = []
        if fixed_machine:
            machine_candidates = [fixed_machine]
        elif fixed_operator:
            machine_candidates = [str(x) for x in (machines_by_operator.get(fixed_operator) or []) if str(x).strip()]
        else:
            if op_type_id and isinstance(machines_by_op_type, dict) and op_type_id in machines_by_op_type:
                machine_candidates = [str(x) for x in (machines_by_op_type.get(op_type_id) or []) if str(x).strip()]
            else:
                # 无 op_type_id 或映射缺失：退化为“所有可用设备”
                if isinstance(operators_by_machine, dict):
                    machine_candidates = [str(x) for x in operators_by_machine.keys() if str(x).strip()]

        # 去重 + 稳定
        machine_candidates = sorted(list({m for m in machine_candidates if m}), key=lambda x: x)
        if not machine_candidates:
            return None

        # 工时
        setup_hours = getattr(op, "setup_hours", 0) or 0
        unit_hours = getattr(op, "unit_hours", 0) or 0
        qty = getattr(batch, "quantity", 0) or 0
        try:
            total_hours_base = float(setup_hours) + float(unit_hours) * float(qty)
        except Exception:
            return None
        if total_hours_base < 0:
            return None

        cur_type = (str(getattr(op, "op_type_name", None) or "") or "").strip()

        best: Optional[Tuple[Any, ...]] = None
        best_pair: Optional[Tuple[str, str]] = None

        for mid in machine_candidates:
            # 候选人员集合
            op_candidates: List[str] = []
            if isinstance(operators_by_machine, dict):
                qualified = [str(x) for x in (operators_by_machine.get(mid) or []) if str(x).strip()]
            else:
                qualified = []
            if fixed_operator:
                # 固定 operator：必须在该设备的资质列表内
                if fixed_operator not in qualified:
                    continue
                op_candidates = [fixed_operator]
            else:
                op_candidates = qualified

            if not op_candidates:
                continue

            # 逐 (machine, operator) 评估可行最早区间
            for oid in op_candidates:
                earliest = max(prev_end, base_time)
                earliest = self.calendar.adjust_to_working_time(earliest, priority=priority)

                # 简化：效率取开工时刻对应日的效率
                total_hours = float(total_hours_base)
                try:
                    eff = float(self.calendar.get_efficiency(earliest) or 1.0)
                except Exception:
                    eff = 1.0
                if eff and 0 < eff < 1.0:
                    total_hours = total_hours / eff

                dt_list: List[Tuple[datetime, datetime]] = []
                if machine_downtimes and mid:
                    dt_list = machine_downtimes.get(mid) or []

                guard = 0
                end = self.calendar.add_working_hours(earliest, total_hours, priority=priority)
                while guard < 200:
                    guard += 1
                    shift_to: Optional[datetime] = None
                    m_shift = self._find_overlap_shift_end(machine_timeline.get(mid) or [], earliest, end)
                    o_shift = self._find_overlap_shift_end(operator_timeline.get(oid) or [], earliest, end)
                    d_shift = self._find_overlap_shift_end(dt_list, earliest, end)
                    for x in (m_shift, o_shift, d_shift):
                        if x is None:
                            continue
                        if shift_to is None or x > shift_to:
                            shift_to = x
                    if shift_to is None:
                        break
                    earliest = max(earliest, shift_to)
                    earliest = self.calendar.adjust_to_working_time(earliest, priority=priority)
                    end = self.calendar.add_working_hours(earliest, total_hours, priority=priority)

                if guard >= 200:
                    continue
                if end_dt_exclusive is not None and end >= end_dt_exclusive:
                    continue

                last_type = (last_op_type_by_machine.get(mid) or "").strip()
                change_pen = 1 if (last_type and cur_type and last_type != cur_type) else 0
                load_pen = float(machine_busy_hours.get(mid, 0.0) or 0.0) + float(operator_busy_hours.get(oid, 0.0) or 0.0)
                rank = 9999
                try:
                    rank = int((pair_rank or {}).get((oid, mid), 9999))
                except Exception:
                    rank = 9999

                score = (end, int(change_pen), float(load_pen), int(rank), mid, oid)
                if best is None or score < best:
                    best = score
                    best_pair = (mid, oid)

        return best_pair

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

    @staticmethod
    def _find_overlap_shift_end(
        segments: List[Tuple[datetime, datetime]],
        start: datetime,
        end: datetime,
    ) -> Optional[datetime]:
        """
        若 [start, end) 与 segments 中任意区间重叠，返回“需要推迟到的最晚结束时刻”（max end）。
        """
        shift: Optional[datetime] = None
        for s, e in segments or []:
            if end <= s or start >= e:
                continue
            if shift is None or e > shift:
                shift = e
        return shift

