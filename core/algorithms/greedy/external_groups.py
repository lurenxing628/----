from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_contracts.value_domains import EXTERNAL, MERGED
from core.algorithm_runtime.algo_stats import increment_counter
from core.algorithm_runtime.piece_input import external_group_key
from core.infrastructure.errors import ValidationError
from core.shared.degradation import DegradationCollector
from core.shared.field_parse import parse_field_float


def rebuild_external_group_cache_from_seeds(
    *,
    seed_results: List[ScheduleResult],
    operations: List[Any],
    external_group_cache: Dict[Tuple[str, ...], Tuple[datetime, datetime]],
    warnings: List[str],
    algo_stats: Any,
    seed_group_keys: Optional[Dict[int, Tuple[str, ...]]] = None,
) -> None:
    """seed 注入时按组键把已排 merged 外协组成员的起止块写回 external_group_cache（audit 2026-07-20 A14）。

    背景：seed 注入原本只重建资源占用和批次进度，不重建外部组缓存；merged 组被部分种入时，
    未种成员 cache miss 会以推进后的批次进度为起点再消耗一次完整 ext_group_total_days，
    打破组内"同起止"合同且零留痕。
    触发面口径（第二核查修正）：健康冻结窗对 merged 组通常全进全出；真实触发偏
    部分种子、版本间工艺模板变化（如 separate→merged 漂移）或旧计划异常。
    生产冻结种子在过滤工序前保留精确组身份；普通算法调用仍可从重叠 operations 解出组键。
    两者冲突时停止排产；没有身份资料时不猜测归属。
    同组 seed 成员起止不一致（重建不出一个组块）时降级留痕（warning + 计数）并不写缓存，
    未种成员按现状另起块——不静默。
    """
    if not seed_results:
        return

    group_key_by_op_id = _merged_group_key_by_op_id(operations)

    operation_ids = {_op_identity_int(getattr(op, "id", 0)) for op in operations}
    for key, blocks in _seed_blocks_by_group(seed_results, group_key_by_op_id, operation_ids, seed_group_keys or {}).items():
        distinct_blocks = sorted(set(blocks))
        if len(distinct_blocks) == 1:
            external_group_cache[key] = distinct_blocks[0]
            increment_counter(algo_stats, "seed_external_group_cache_rebuilt_count", 1)
            continue
        warnings.append(_inconsistent_group_block_warning(key, blocks=blocks, distinct_blocks=distinct_blocks))
        increment_counter(algo_stats, "seed_external_group_block_inconsistent_count", 1)


def _merged_group_key_by_op_id(operations: List[Any]) -> Dict[int, Tuple[str, ...]]:
    group_key_by_op_id: Dict[int, Tuple[str, ...]] = {}
    for op in operations:
        if str(getattr(op, "source", "") or "").strip().lower() != EXTERNAL:
            continue
        merge_mode = str(getattr(op, "ext_merge_mode", None) or "").strip().lower()
        ext_group_id = str(getattr(op, "ext_group_id", None) or "").strip()
        bid = str(getattr(op, "batch_id", "") or "").strip()
        if merge_mode != MERGED or not ext_group_id or not bid:
            continue
        op_id = _op_identity_int(getattr(op, "id", 0))
        if op_id > 0:
            group_key_by_op_id[op_id] = external_group_key(op)
    return group_key_by_op_id


def _seed_blocks_by_group(
    seed_results: List[ScheduleResult],
    group_key_by_op_id: Dict[int, Tuple[str, ...]],
    operation_ids: set,
    seed_group_keys: Dict[int, Tuple[str, ...]],
) -> Dict[Tuple[str, ...], List[Tuple[datetime, datetime]]]:
    blocks_by_group: Dict[Tuple[str, ...], List[Tuple[datetime, datetime]]] = {}
    for result in seed_results:
        op_id = _op_identity_int(getattr(result, "op_id", 0))
        operation_key = group_key_by_op_id.get(op_id)
        seed_key = seed_group_keys.get(op_id)
        if seed_key is not None and op_id in operation_ids and seed_key != operation_key:
            raise ValidationError("冻结外协种子的组身份与待排工序不一致，系统已停止排产。", field="seed_results")
        key = seed_key if seed_key is not None else operation_key
        if key is None:
            continue
        start = getattr(result, "start_time", None)
        end = getattr(result, "end_time", None)
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            continue
        blocks_by_group.setdefault(key, []).append((start, end))
    return blocks_by_group


def _op_identity_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _inconsistent_group_block_warning(
    key: Tuple[str, ...],
    *,
    blocks: List[Tuple[datetime, datetime]],
    distinct_blocks: List[Tuple[datetime, datetime]],
) -> str:
    bid, ext_group_id = key[:2]
    sample = "；".join(
        f"{start.strftime('%Y-%m-%d %H:%M')}~{end.strftime('%Y-%m-%d %H:%M')}" for start, end in distinct_blocks[:3]
    )
    return (
        f"沿用旧排产结果时发现外协合并组 {ext_group_id}（批次 {bid}）的已排成员起止不一致"
        f"（{len(blocks)} 条记录、{len(distinct_blocks)} 种起止，示例：{sample}），"
        f"无法恢复为一个组块；该组未沿用的成员将按当前批次进度另起新组块。"
    )


def schedule_external(
    scheduler: Any,
    *,
    op: Any,
    batch: Any,
    batch_progress: Dict[str, datetime],
    external_group_cache: Dict[Tuple[str, ...], Tuple[datetime, datetime]],
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
        cache_key = external_group_key(op)
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
                min_violation_fallback=0.0,
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
