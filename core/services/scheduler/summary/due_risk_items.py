"""交期风险 items 构造（从 schedule_summary_assembly 拆出的内聚计算单元）。

全批次循环按 finish 与 due_exclusive 的关系两侧切分（严格互斥、零重叠）：
finish >= due_exclusive 为超期；落在 [due_exclusive - 临期窗口, due_exclusive) 为临期（卡交期、未超期）；
更早完工（缓冲 > 临期窗口）则健康、跳过。产出 (overdue_items, meta)，meta 含 near_due_items + 坏交期记账——
二元返回形状不变（临期走 meta，保 build_overdue_items 公开解包契约）。
由 summary_runtime_state.build_overdue_items 注入 due_exclusive / append_summary_warning 后调用。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Tuple

# 临期窗口：排程完工时间卡在「交期前 NEAR_DUE_WINDOW_DAYS 天内、且未超期」即临期。
# Python 侧单点定义（契约 4.11 时间窗单点），模板只消费冻结进 summary 的结论。
NEAR_DUE_WINDOW_DAYS = 3
_NEAR_DUE_DELTA = timedelta(days=NEAR_DUE_WINDOW_DAYS)


def _record_invalid_due(
    *,
    batch_id: str,
    due_text: str,
    invalid_due_ids_sample: List[str],
    invalid_due_raw_sample: List[str],
) -> None:
    if len(invalid_due_ids_sample) < 10:
        invalid_due_ids_sample.append(str(batch_id))
    if len(invalid_due_raw_sample) < 5:
        invalid_due_raw_sample.append(f"{batch_id}={due_text!r}")


def _build_overdue_items(
    svc,
    *,
    batches: Dict[str, Any],
    finish_by_batch: Dict[str, datetime],
    summary: Any,
    due_exclusive_fn: Callable[[Any], datetime],
    append_summary_warning_fn: Callable[[Any, str], bool],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    overdue_items: List[Dict[str, Any]] = []
    near_due_items: List[Dict[str, Any]] = []
    invalid_due_count = 0
    invalid_due_ids_sample: List[str] = []
    invalid_due_raw_sample: List[str] = []

    for batch_id, batch in batches.items():
        due_text = svc._normalize_text(getattr(batch, "due_date", None))
        if not due_text:
            continue
        try:
            due_date = datetime.strptime(due_text.replace("/", "-"), "%Y-%m-%d").date()
        except Exception:
            invalid_due_count += 1
            _record_invalid_due(
                batch_id=str(batch_id),
                due_text=due_text,
                invalid_due_ids_sample=invalid_due_ids_sample,
                invalid_due_raw_sample=invalid_due_raw_sample,
            )
            continue

        finish_time = finish_by_batch.get(str(batch_id))
        if finish_time is None:
            continue
        # 同一交期口径的两侧（严格互斥、零重叠）：finish >= due_exclusive 为超期；
        # 落在 [due_exclusive - 临期窗口, due_exclusive) 为临期；更早完工则健康、跳过。
        due_exclusive = due_exclusive_fn(due_date)
        if finish_time >= due_exclusive:
            target = overdue_items
        elif finish_time >= due_exclusive - _NEAR_DUE_DELTA:
            target = near_due_items
        else:
            continue
        target.append(
            {
                "batch_id": batch_id,
                "due_date": due_text,
                "finish_time": svc._format_dt(finish_time),
            }
        )

    if invalid_due_count > 0:
        sample_ids = "，".join(invalid_due_ids_sample[:10])
        message = f"存在 {invalid_due_count} 个批次交期写法不对，已忽略超期与临期判断（示例批次：{sample_ids}）"
        warning_appended = append_summary_warning_fn(summary, message)
        logger = getattr(svc, "logger", None)
        if logger is not None:
            raw_sample = "；".join(invalid_due_raw_sample[:5])
            detail = f"{message}；示例原始交期：{raw_sample}"
            if not warning_appended:
                detail += "；且 summary.warnings 追加失败"
            logger.warning(detail)

    return overdue_items, {
        "invalid_due_count": int(invalid_due_count),
        "invalid_due_batch_ids_sample": list(invalid_due_ids_sample),
        "invalid_due_raw_sample": list(invalid_due_raw_sample),
        "near_due_items": near_due_items,
    }


__all__ = ["_build_overdue_items", "_record_invalid_due", "NEAR_DUE_WINDOW_DAYS"]
