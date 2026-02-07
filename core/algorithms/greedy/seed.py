from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.algorithms.types import ScheduleResult


def normalize_seed_results(
    *,
    seed_results: Optional[List[ScheduleResult]],
    operations: List[Any],
) -> Tuple[List[ScheduleResult], Set[int], List[str]]:
    """
    防御性处理：
    - 当 seed_results 与 operations 重叠时，避免同一工序被排两次
    - 当 seed_results 存在 op_id<=0 时，尝试按 op_code 或 (batch_id, seq) 回填 op_id

    Returns:
        (normalized_seed_results, seed_op_ids, warnings)
    """
    warnings: List[str] = []
    seed_op_ids: Set[int] = set()

    if not seed_results:
        return [], seed_op_ids, warnings

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
    dropped_bad_time = 0
    dropped_dup = 0
    dup_samples: List[str] = []

    for sr in seed_results:
        try:
            if not sr or not getattr(sr, "start_time", None) or not getattr(sr, "end_time", None):
                continue
            try:
                if getattr(sr, "end_time", None) <= getattr(sr, "start_time", None):
                    dropped_bad_time += 1
                    continue
            except Exception:
                dropped_bad_time += 1
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
                # 去重：同一 op_id 的 seed 重复记录会导致重复占用资源/重复计数
                if int(oid0) in seed_op_ids:
                    dropped_dup += 1
                    if len(dup_samples) < 5:
                        dup_samples.append(str(int(oid0)))
                    continue
                seed_op_ids.add(int(oid0))
                normalized.append(sr)
        except Exception:
            continue

    if backfilled:
        warnings.append(f"seed_results 存在 {backfilled} 条 op_id<=0 的记录，已按 op_code/batch_id+seq 回填 op_id 以避免重复排产。")
    if dropped_invalid:
        warnings.append(f"seed_results 存在 {dropped_invalid} 条 op_id<=0 且无法匹配的记录，已忽略（避免重复统计/排产）。")
    if dropped_bad_time:
        warnings.append(f"seed_results 存在 {dropped_bad_time} 条 start_time>=end_time 的记录，已忽略（避免冻结窗口/资源占用异常）。")
    if dropped_dup:
        sample = ", ".join([x for x in dup_samples if x][:5])
        warnings.append(
            f"seed_results 存在 {dropped_dup} 条重复 op_id 的记录，已按 op_id 去重（保留首条）"
            f"{('（示例 op_id=' + sample + '）') if sample else ''}。"
        )

    return normalized, seed_op_ids, warnings

