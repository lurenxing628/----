from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple


def _serialize_end_date(end_date: Optional[Any]) -> Optional[str]:
    if end_date is None:
        return None
    if isinstance(end_date, str):
        s = end_date.strip()
        return s if s else None
    try:
        iso_fn = getattr(end_date, "isoformat", None)
        if callable(iso_fn):
            return str(iso_fn())
    except Exception:
        pass
    s = str(end_date).strip()
    return s if s else None


def build_result_summary(
    svc,
    *,
    cfg: Any,
    version: int,
    normalized_batch_ids: List[str],
    start_dt: datetime,
    end_date: Optional[Any],
    batches: Dict[str, Any],
    operations: List[Any],
    results: List[Any],
    summary: Any,
    used_strategy: Any,
    used_params: Dict[str, Any],
    algo_mode: str,
    objective_name: str,
    time_budget_seconds: int,
    best_score: Optional[Tuple[float, ...]],
    best_metrics: Optional[Any],
    best_order: List[str],
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    frozen_op_ids: Set[int],
    downtime_meta: Optional[Dict[str, Any]] = None,
    simulate: bool,
    t0: float,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any], str, int]:
    """
    生成：超期清单 + result_status + result_summary（dict/json）。

    Returns:
        (overdue_items, result_status, result_summary_obj, result_summary_json, time_cost_ms)
    """
    # 超期预警：批次预计完工时间 vs due_date
    overdue_items: List[Dict[str, Any]] = []
    finish_by_batch: Dict[str, datetime] = {}
    for r in results:
        if not getattr(r, "end_time", None):
            continue
        bid = str(getattr(r, "batch_id", "") or "")
        cur = finish_by_batch.get(bid)
        if (cur is None) or (r.end_time > cur):
            finish_by_batch[bid] = r.end_time

    invalid_due_count = 0
    invalid_due_ids_sample: List[str] = []
    invalid_due_raw_sample: List[str] = []
    for bid, b in batches.items():
        due = svc._normalize_text(getattr(b, "due_date", None))
        if not due:
            continue
        try:
            due_date = datetime.strptime(due.replace("/", "-"), "%Y-%m-%d").date()
        except Exception:
            invalid_due_count += 1
            if len(invalid_due_ids_sample) < 10:
                invalid_due_ids_sample.append(str(bid))
            if len(invalid_due_raw_sample) < 5:
                invalid_due_raw_sample.append(f"{bid}={due!r}")
            continue
        finish = finish_by_batch.get(str(bid))
        if not finish:
            continue
        if finish.date() > due_date:
            overdue_items.append(
                {
                    "batch_id": bid,
                    "due_date": due,
                    "finish_time": svc._format_dt(finish),
                }
            )

    if invalid_due_count > 0:
        sample_ids = "，".join(invalid_due_ids_sample[:10])
        msg = f"存在 {invalid_due_count} 个批次 due_date 格式不合法，已忽略超期判断（示例批次：{sample_ids}）"
        try:
            summary.warnings.append(msg)
        except Exception:
            pass
        if svc.logger:
            try:
                raw_sample = "；".join(invalid_due_raw_sample[:5])
                svc.logger.warning(f"{msg}；示例原始 due_date：{raw_sample}")
            except Exception:
                pass

    # result_status：success/partial/failed
    if getattr(summary, "success", False):
        result_status = "success"
    elif int(getattr(summary, "scheduled_ops", 0) or 0) > 0:
        result_status = "partial"
    else:
        result_status = "failed"
    if simulate:
        result_status = "simulated"

    time_cost_ms = int((time.time() - float(t0)) * 1000)

    frozen_batch_ids = sorted(
        {
            str(op.batch_id or "")
            for op in operations
            if op and getattr(op, "id", None) and int(op.id) in frozen_op_ids and str(op.batch_id or "").strip()
        }
    )

    # 冻结窗口降级识别：目前以 warnings 前缀为准（freeze_window.py 会统一加前缀）
    all_warnings = getattr(summary, "warnings", None) or []
    freeze_warnings: List[str] = []
    try:
        for w in list(all_warnings or []):
            ws = str(w)
            if ws.startswith("【冻结窗口】"):
                freeze_warnings.append(ws)
    except Exception:
        freeze_warnings = []

    # 停机约束状态：避免“停机加载失败但摘要仍宣称硬约束已启用”
    auto_assign_enabled = getattr(cfg, "auto_assign_enabled", "no") == "yes"
    downtime_load_ok = True
    downtime_load_error = None
    downtime_extend_attempted = False
    downtime_extend_ok = True
    downtime_extend_error = None
    try:
        if isinstance(downtime_meta, dict):
            if "downtime_load_ok" in downtime_meta:
                downtime_load_ok = bool(downtime_meta.get("downtime_load_ok"))
            downtime_load_error = downtime_meta.get("downtime_load_error")
            downtime_extend_attempted = bool(downtime_meta.get("downtime_extend_attempted") or False)
            if "downtime_extend_ok" in downtime_meta and downtime_meta.get("downtime_extend_ok") is not None:
                downtime_extend_ok = bool(downtime_meta.get("downtime_extend_ok"))
            downtime_extend_error = downtime_meta.get("downtime_extend_error")
    except Exception:
        pass

    downtime_degraded = (not downtime_load_ok) or (auto_assign_enabled and downtime_extend_attempted and (not downtime_extend_ok))
    downtime_degradation_reason = None
    if downtime_degraded:
        if not downtime_load_ok:
            downtime_degradation_reason = str(downtime_load_error or "停机区间加载失败")
        elif auto_assign_enabled and downtime_extend_attempted and (not downtime_extend_ok):
            downtime_degradation_reason = str(downtime_extend_error or "停机区间扩展加载失败")

    hard_constraints: List[str] = [
        "precedence",
        "calendar",
        "resource_machine_operator",
    ]
    if not downtime_degraded:
        hard_constraints.append("downtime_avoid")
    if getattr(cfg, "freeze_window_enabled", "no") == "yes":
        hard_constraints.append("freeze_window")

    result_summary_obj: Dict[str, Any] = {
        "summary_schema_version": "1.0",
        "is_simulation": bool(simulate),
        "version": int(version),
        "strategy": used_strategy.value,
        "strategy_params": used_params or {},
        "algo": {
            "mode": algo_mode,
            "objective": objective_name,
            "time_budget_seconds": int(time_budget_seconds),
            "hard_constraints": hard_constraints,
            "soft_objectives": [objective_name],
            "best_score": list(best_score) if best_score is not None else None,
            "metrics": best_metrics.to_dict() if best_metrics is not None else None,
            "best_batch_order": list(best_order or []),
            "attempts": (attempts or [])[:12],
            "improvement_trace": (improvement_trace or [])[:200],
            "downtime_avoid": {
                "loaded_ok": bool(downtime_load_ok),
                "degraded": bool(downtime_degraded),
                "degradation_reason": downtime_degradation_reason,
                "extend_attempted": bool(downtime_extend_attempted) if auto_assign_enabled else False,
            },
            "freeze_window": {
                "enabled": getattr(cfg, "freeze_window_enabled", "no"),
                "days": int(getattr(cfg, "freeze_window_days", 0) or 0),
                "frozen_op_count": int(len(frozen_op_ids)),
                "frozen_batch_count": int(len(frozen_batch_ids)),
                "frozen_batch_ids_sample": frozen_batch_ids[:20],
                "degraded": bool(freeze_warnings),
                "degradation_reason": (freeze_warnings[0] if freeze_warnings else None),
            },
        },
        "selected_batch_ids": list(normalized_batch_ids),
        "start_time": svc._format_dt(start_dt),
        "end_date": _serialize_end_date(end_date),
        "counts": {
            "batch_count": len(batches),
            # 与调度器 summary 同口径（包含 seed_results；并考虑 seed 与 operations 去重过滤）
            "op_count": int(getattr(summary, "total_ops", 0)),
            "scheduled_ops": int(getattr(summary, "scheduled_ops", 0)),
            "failed_ops": int(getattr(summary, "failed_ops", 0)),
        },
        "overdue_batches": {"count": len(overdue_items), "items": overdue_items},
        "errors_sample": (getattr(summary, "errors", None) or [])[:10],
        "warnings": list(all_warnings or []),
        "time_cost_ms": int(time_cost_ms),
    }

    result_summary_json = json.dumps(result_summary_obj, ensure_ascii=False)
    return overdue_items, result_status, result_summary_obj, result_summary_json, time_cost_ms

