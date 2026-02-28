from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Set, Tuple

from core.models.enums import YesNo

from .number_utils import to_yes_no


def build_freeze_window_seed(
    svc,
    *,
    cfg: Any,
    prev_version: int,
    start_dt: datetime,
    operations: List[Any],
) -> Tuple[Set[int], List[Dict[str, Any]], List[str]]:
    """
    冻结窗口（硬约束；默认关闭）：
    - 复用上一版本在窗口内的排程结果，不再重排
    - 为保证批次前后约束：按批次 seq 前缀冻结（冻结到窗口内出现的最大 seq）

    Returns:
        (frozen_op_ids, seed_results, warnings)
    """
    frozen_op_ids: Set[int] = set()
    seed_results: List[Dict[str, Any]] = []
    warnings: List[str] = []

    if not (
        to_yes_no(getattr(cfg, "freeze_window_enabled", YesNo.NO.value), default=YesNo.NO.value) == YesNo.YES.value
        and int(getattr(cfg, "freeze_window_days", 0) or 0) > 0
        and int(prev_version or 0) > 0
    ):
        return frozen_op_ids, seed_results, warnings

    freeze_days = int(getattr(cfg, "freeze_window_days", 0) or 0)
    freeze_end = start_dt + timedelta(days=freeze_days)
    freeze_end_str = svc._format_dt(freeze_end)
    start_str = svc._format_dt(start_dt)

    op_by_id: Dict[int, Any] = {int(op.id): op for op in operations if op and op.id}
    op_ids_all = sorted(list(op_by_id.keys()))

    # 查询上一版本在窗口内的排程（仅查本次选中批次的工序）
    schedule_map: Dict[int, Dict[str, Any]] = {}
    try:
        rows = svc.schedule_repo.list_version_rows_by_op_ids_start_range(
            version=int(prev_version),
            op_ids=op_ids_all,
            start_time=start_str,
            end_time=freeze_end_str,
        )
        for r in rows:
            try:
                oid = int(r.get("op_id") or 0)
                if oid <= 0:
                    continue
                schedule_map[int(oid)] = dict(r)
            except Exception:
                continue
    except Exception as e:
        schedule_map = {}
        warnings.append(f"【冻结窗口】启用但读取上一版本排程失败，已降级为不冻结：{e}")

    # 冻结到窗口内出现的最大 seq（按批次前缀冻结）
    if schedule_map:
        max_seq_by_batch: Dict[str, int] = {}
        seed_tmp: Dict[int, Dict[str, Any]] = {}
        for oid in schedule_map.keys():
            op0 = op_by_id.get(int(oid))
            if not op0:
                continue
            bid = str(op0.batch_id or "")
            seq0 = int(op0.seq or 0)
            if seq0 <= 0:
                continue
            max_seq_by_batch[bid] = max(max_seq_by_batch.get(bid, 0), seq0)

        for bid, max_seq in max_seq_by_batch.items():
            if max_seq <= 0:
                continue
            prefix = [int(op.id) for op in operations if op and op.id and op.batch_id == bid and int(op.seq or 0) <= max_seq]
            missing = [oid for oid in prefix if oid not in schedule_map]
            if missing:
                sample = ", ".join([str(x) for x in missing[:5]])
                warnings.append(f"【冻结窗口】跳过批次 {bid}：上一版本缺少前缀工序排程（示例 op_id={sample}）")
                continue
            # 校验时间有效（否则不冻结该批次，避免“冻结但无有效区间”导致工序丢失）
            invalid_oid = None
            for oid in prefix:
                row = schedule_map.get(int(oid)) or {}
                st = svc._normalize_datetime(row.get("start_time"))
                et = svc._normalize_datetime(row.get("end_time"))
                if not st or not et or et <= st:
                    invalid_oid = int(oid)
                    break
                seed_tmp[int(oid)] = {"row": row, "start_time": st, "end_time": et}
            if invalid_oid is not None:
                warnings.append(f"【冻结窗口】跳过批次 {bid}：上一版本工序时间无效（op_id={invalid_oid}）")
                # 清理该批次临时缓存
                for oid in prefix:
                    seed_tmp.pop(int(oid), None)
                continue
            for oid in prefix:
                frozen_op_ids.add(int(oid))

        # 生成 seed_results（用于算法占用资源 + 新版本回写）
        for oid in sorted(frozen_op_ids):
            op0 = op_by_id.get(oid)
            seed = seed_tmp.get(oid)
            if not op0 or not seed:
                continue
            row = seed.get("row")
            st = seed.get("start_time")
            et = seed.get("end_time")
            if not row or not st or not et:
                continue
            seed_results.append(
                {
                    "op_id": oid,
                    "op_code": op0.op_code,
                    "batch_id": op0.batch_id,
                    "seq": int(op0.seq or 0),
                    "machine_id": row.get("machine_id"),
                    "operator_id": row.get("operator_id"),
                    "start_time": st,
                    "end_time": et,
                    "source": (op0.source or "internal").strip(),
                    "op_type_name": getattr(op0, "op_type_name", None),
                }
            )

        # 排序（便于人类阅读/留痕）
        seed_results.sort(key=lambda x: (x.get("start_time") or datetime.min, x.get("op_id") or 0))

    return frozen_op_ids, seed_results, warnings

