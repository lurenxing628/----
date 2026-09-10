"""交期风险 items 构造（从 schedule_summary_assembly 拆出的内聚计算单元）。

全批次循环按 finish 与 due_exclusive 的关系两侧切分（严格互斥、零重叠）：
finish >= due_exclusive 为超期；落在 [due_exclusive - 临期窗口, due_exclusive) 为临期（卡交期、未超期）；
更早完工（缓冲 > 临期窗口）则健康、跳过。产出 (overdue_items, meta)，meta 含 near_due_items + 坏交期记账——
二元返回形状不变（临期走 meta，保 build_overdue_items 公开解包契约）。
由 summary_runtime_state.build_overdue_items 注入 due_exclusive / append_summary_warning 后调用。

排产未完成口径（audit 2026-07-20 A18）：有失败/跳过工序明细且已有部分完工结果的批次，
finish_by_batch 里的值是被失败截断的部分完工时间，按它做超期/临期分类会把半途失败批次
静默判"健康"。这类批次由 incomplete_batch_ids_from_failure_details 圈出，在两侧切分里
整体排除，改走 build_incomplete_batch_items 的"排产未完成"风险清单。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# 临期窗口：排程完工时间卡在「交期前 NEAR_DUE_WINDOW_DAYS 天内、且未超期」即临期。
# Python 侧单点定义（契约 4.11 时间窗单点），模板只消费冻结进 summary 的结论。
NEAR_DUE_WINDOW_DAYS = 3
_NEAR_DUE_DELTA = timedelta(days=NEAR_DUE_WINDOW_DAYS)


def incomplete_batch_ids_from_failure_details(
    failure_details: Any,
    finish_by_batch: Dict[str, datetime],
) -> Set[str]:
    """排产未完成批次集合：有失败/跳过工序明细、且已有部分完工结果的批次。

    零结果批次（整批没排上）不在此集合——它们没有 finish 条目，仍走既有
    unscheduled"未形成完工结果"口径；此集合专圈"部分成功后失败截断"的批次。
    """
    incomplete: Set[str] = set()
    for detail in list(failure_details or []):
        if not isinstance(detail, dict):
            continue
        batch_id = str(detail.get("batch_id") or "").strip()
        if batch_id and batch_id in finish_by_batch:
            incomplete.add(batch_id)
    return incomplete


def _scheduled_op_count_by_batch(results: List[Any], incomplete_batch_ids: Set[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for result in list(results or []):
        batch_id = str(getattr(result, "batch_id", "") or "").strip()
        if batch_id in incomplete_batch_ids:
            counts[batch_id] = counts.get(batch_id, 0) + 1
    return counts


def _failure_stats_by_batch(
    failure_details: List[Dict[str, Any]],
    incomplete_batch_ids: Set[str],
) -> Tuple[Dict[str, int], Dict[str, str]]:
    """按批次聚合失败明细：失败/跳过工序数 + 首条失败原因 code（按明细顺序即派工顺序）。"""
    failed_count_by_batch: Dict[str, int] = {}
    first_reason_by_batch: Dict[str, str] = {}
    for detail in list(failure_details or []):
        if not isinstance(detail, dict):
            continue
        batch_id = str(detail.get("batch_id") or "").strip()
        if batch_id not in incomplete_batch_ids:
            continue
        failed_count_by_batch[batch_id] = failed_count_by_batch.get(batch_id, 0) + 1
        code = str(detail.get("code") or "").strip()
        if code and batch_id not in first_reason_by_batch:
            first_reason_by_batch[batch_id] = code
    return failed_count_by_batch, first_reason_by_batch


def build_incomplete_batch_items(
    svc,
    *,
    incomplete_batch_ids: Set[str],
    batches: Dict[str, Any],
    finish_by_batch: Dict[str, datetime],
    results: List[Any],
    failure_details: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """构造"排产未完成"风险清单 items（按 batch_id 排序，带原因与已排/未排工序数）。

    partial_finish_time 是被失败截断的部分完工时间——只作留痕，不得当完工时间
    参与交期判断（audit 2026-07-20 A18）。
    """
    if not incomplete_batch_ids:
        return []
    scheduled_count_by_batch = _scheduled_op_count_by_batch(results, incomplete_batch_ids)
    failed_count_by_batch, first_reason_by_batch = _failure_stats_by_batch(failure_details, incomplete_batch_ids)

    items: List[Dict[str, Any]] = []
    for batch_id in sorted(incomplete_batch_ids):
        batch = batches.get(batch_id)
        due_text = svc._normalize_text(getattr(batch, "due_date", None)) if batch is not None else None
        finish_time = finish_by_batch.get(batch_id)
        items.append(
            {
                "batch_id": batch_id,
                "reason_code": first_reason_by_batch.get(batch_id),
                "scheduled_op_count": int(scheduled_count_by_batch.get(batch_id, 0)),
                "failed_op_count": int(failed_count_by_batch.get(batch_id, 0)),
                "due_date": due_text or None,
                "partial_finish_time": svc._format_dt(finish_time) if finish_time is not None else None,
            }
        )
    return items


def incomplete_batches_payload(
    svc,
    *,
    failure_details: Any,
    finish_by_batch: Dict[str, datetime],
    batches: Dict[str, Any],
    results: List[Any],
) -> Dict[str, Any]:
    """result_summary["incomplete_batches"] 桶：排产未完成批次风险清单。

    与 summary_runtime_state 的超期/临期排除口径同源（同一 incomplete 集合推导）。
    items 上限 50 条防摘要膨胀，count 为全量。
    """
    details = [item for item in list(failure_details or []) if isinstance(item, dict)]
    items = build_incomplete_batch_items(
        svc,
        incomplete_batch_ids=incomplete_batch_ids_from_failure_details(details, finish_by_batch),
        batches=batches,
        finish_by_batch=finish_by_batch,
        results=results,
        failure_details=details,
    )
    return {"count": len(items), "items": items[:50]}


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
    incomplete_batch_ids: Optional[Set[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    overdue_items: List[Dict[str, Any]] = []
    near_due_items: List[Dict[str, Any]] = []
    invalid_due_count = 0
    invalid_due_ids_sample: List[str] = []
    invalid_due_raw_sample: List[str] = []
    excluded_incomplete = incomplete_batch_ids or set()

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
        if str(batch_id) in excluded_incomplete:
            # 排产未完成批次：finish 是被失败截断的部分完工时间，不参与超期/临期
            # "健康"分类，整体改走"排产未完成"风险清单（audit 2026-07-20 A18）。
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


__all__ = [
    "_build_overdue_items",
    "_record_invalid_due",
    "build_incomplete_batch_items",
    "incomplete_batch_ids_from_failure_details",
    "incomplete_batches_payload",
    "NEAR_DUE_WINDOW_DAYS",
]
