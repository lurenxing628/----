from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.material_release import released_start
from core.algorithm_contracts.types import OpForScheduleAlgo, ScheduleResult
from core.algorithm_contracts.value_domains import EXTERNAL, MERGED
from core.algorithm_runtime.algo_stats import increment_counter
from core.algorithm_runtime.piece_input import external_group_key
from core.errors import ValidationError


def rebuild_external_group_cache_from_seeds(
    *,
    seed_results: List[ScheduleResult],
    operations: List[OpForScheduleAlgo],
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

    group_key_by_op_id, operation_ids = _merged_group_key_by_op_id(operations)
    for key, blocks in _seed_blocks_by_group(seed_results, group_key_by_op_id, operation_ids, seed_group_keys or {}).items():
        distinct_blocks = sorted(set(blocks))
        if len(distinct_blocks) == 1:
            external_group_cache[key] = distinct_blocks[0]
            increment_counter(algo_stats, "seed_external_group_cache_rebuilt_count", 1)
            continue
        warnings.append(_inconsistent_group_block_warning(key, blocks=blocks, distinct_blocks=distinct_blocks))
        increment_counter(algo_stats, "seed_external_group_block_inconsistent_count", 1)


def _merged_group_key_by_op_id(operations: List[OpForScheduleAlgo]) -> Tuple[Dict[int, Tuple[str, ...]], set]:
    group_key_by_op_id: Dict[int, Tuple[str, ...]] = {}
    operation_ids: set = set()
    for op in operations:
        operation_ids.add(op.id)
        # 排产输入构建保证：合并外协组必带非空组身份。
        if op.source == EXTERNAL and op.ext_merge_mode == MERGED:
            group_key_by_op_id[op.id] = external_group_key(op)
    return group_key_by_op_id, operation_ids


def _seed_blocks_by_group(
    seed_results: List[ScheduleResult],
    group_key_by_op_id: Dict[int, Tuple[str, ...]],
    operation_ids: set,
    seed_group_keys: Dict[int, Tuple[str, ...]],
) -> Dict[Tuple[str, ...], List[Tuple[datetime, datetime]]]:
    blocks_by_group: Dict[Tuple[str, ...], List[Tuple[datetime, datetime]]] = {}
    for result in seed_results:
        op_id = result.op_id
        operation_key = group_key_by_op_id.get(op_id)
        seed_key = seed_group_keys.get(op_id)
        if seed_key is not None and op_id in operation_ids and seed_key != operation_key:
            raise ValidationError("冻结外协种子的组身份与待排工序不一致，系统已停止排产。", field="seed_results")
        key = seed_key if seed_key is not None else operation_key
        if key is None:
            continue
        start, end = result.start_time, result.end_time
        if start is None or end is None:
            continue
        blocks_by_group.setdefault(key, []).append((start, end))
    return blocks_by_group


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
    *,
    calendar: Any,
    op: OpForScheduleAlgo,
    batch_progress: Dict[str, datetime],
    external_group_cache: Dict[Tuple[str, ...], Tuple[datetime, datetime]],
    base_time: datetime,
    errors: List[str],
    end_dt_exclusive: Optional[datetime],
) -> Tuple[Optional[ScheduleResult], bool]:
    """排产外部工序：不占资源，只占用自然日周期。

    排产输入构建已把周期规范成正有限数：合并组读 ext_group_total_days，单道读 ext_days；这里直接使用。
    """
    bid = op.batch_id
    prev_end = released_start(op, batch_progress.get(bid, base_time))

    # merged 外部组：整组作为一个时间块（组内工序同起止）；输入构建保证合并组必带组身份。
    if op.ext_merge_mode == MERGED:
        ext_group_id = op.ext_group_id
        cache_key = external_group_key(op)
        cached = external_group_cache.get(cache_key)
        if cached:
            start, end = cached
        else:
            start = prev_end
            end = calendar.add_calendar_days(start, op.ext_group_total_days)

        if end_dt_exclusive is not None and end >= end_dt_exclusive:
            deadline = (end_dt_exclusive - timedelta(seconds=1)).strftime("%Y-%m-%d")
            errors.append(
                f"排产窗口截止到 {deadline}：外协组 {ext_group_id}（批次 {bid}）预计完工 {end.strftime('%Y-%m-%d %H:%M')} 超出窗口"
            )
            return None, True
        # Only a group block that fits the window becomes the shared start/end of its members.
        if not cached:
            external_group_cache[cache_key] = (start, end)

        return _external_result(op, start, end), False

    # separate（或无组）：按单道工序 ext_days 推进
    start = prev_end
    end = calendar.add_calendar_days(start, op.ext_days)
    if end_dt_exclusive is not None and end >= end_dt_exclusive:
        deadline = (end_dt_exclusive - timedelta(seconds=1)).strftime("%Y-%m-%d")
        errors.append(
            f"排产窗口截止到 {deadline}：外协工序 {op.op_code}（批次 {bid}）预计完工 {end.strftime('%Y-%m-%d %H:%M')} 超出窗口"
        )
        return None, True

    return _external_result(op, start, end), False


def _external_result(op: OpForScheduleAlgo, start: datetime, end: datetime) -> ScheduleResult:
    return ScheduleResult(
        op_id=op.id,
        op_code=op.op_code,
        batch_id=op.batch_id,
        seq=op.seq,
        start_time=start,
        end_time=end,
        source=EXTERNAL,
        op_type_name=op.op_type_name,
    )
