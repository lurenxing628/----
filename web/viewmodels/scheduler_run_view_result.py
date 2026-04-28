from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple, cast

from .scheduler_summary_display import build_summary_display_state

_STATUS_SUCCESS = "success"
_STATUS_PARTIAL = "partial"
_STATUS_FAILED = "failed"
_STATUS_SIMULATED = "simulated"


@dataclass(frozen=True)
class RunScheduleViewResult:
    result_status: str
    headline_message: str
    headline_category: str
    primary_degradation_message: Optional[str]
    overdue_sample: Tuple[str, ...]
    overdue_sample_message: Optional[str]
    secondary_degradation_messages: object
    warning_messages: object
    error_preview: Optional[Sequence[str]]
    error_total: int


def _result_status(result: Dict[str, Any]) -> str:
    return str(result.get("result_status") or _STATUS_SUCCESS).strip().lower()


def _headline_prefix_and_category(result_status: str) -> Tuple[str, str]:
    prefix = "排产完成"
    category = "success"
    if result_status == _STATUS_PARTIAL:
        prefix = "排产部分完成"
        category = "warning"
    elif result_status == _STATUS_FAILED:
        prefix = "排产失败"
        category = "error"
    elif result_status == _STATUS_SIMULATED:
        raise RuntimeError("unexpected simulated result_status on /scheduler/run")
    return prefix, category


def _headline_message(
    result: Dict[str, Any],
    *,
    result_status: str,
    overdue_text: str,
) -> Tuple[str, str]:
    ver = result.get("version")
    summary = result.get("summary") or {}
    prefix, category = _headline_prefix_and_category(result_status)
    version_text = f"（版本 {ver}）" if ver else ""
    message = (
        f"{prefix}{version_text}：成功 {summary.get('scheduled_ops')}/{summary.get('total_ops')}，"
        f"失败 {summary.get('failed_ops')}。{overdue_text}。"
    )
    return message, category


def _overdue_text(overdue_batches: Any) -> str:
    return f"超期 {len(overdue_batches)} 个" if overdue_batches else "无超期"


def _overdue_sample(overdue_batches: Any) -> Tuple[str, ...]:
    sample = [item.get("batch_id") for item in overdue_batches[:10] if item.get("batch_id")]
    return cast(Tuple[str, ...], tuple(sample))


def _overdue_sample_message(overdue_sample: Tuple[str, ...]) -> Optional[str]:
    if not overdue_sample:
        return None
    return f"超期批次（最多展示10个）：{'，'.join(overdue_sample)}"


def _primary_degradation_message(summary_display: Dict[str, Any]) -> Optional[str]:
    primary_degradation = summary_display.get("primary_degradation")
    if not isinstance(primary_degradation, dict):
        return None
    details = "、".join(list(primary_degradation.get("details") or []))
    detail = f" 原因：{details}" if details else ""
    return f"{primary_degradation.get('message')}{detail}"


def build_run_schedule_view_result(result: Dict[str, Any]) -> RunScheduleViewResult:
    result_status = _result_status(result)
    summary = result.get("summary") or {}
    summary_display = build_summary_display_state(
        summary if isinstance(summary, dict) else None,
        result_status=result.get("result_status"),
    )
    overdue_batches = result.get("overdue_batches") or []
    overdue_sample = _overdue_sample(overdue_batches)
    headline_message, headline_category = _headline_message(
        result,
        result_status=result_status,
        overdue_text=_overdue_text(overdue_batches),
    )

    return RunScheduleViewResult(
        result_status=result_status,
        headline_message=headline_message,
        headline_category=headline_category,
        primary_degradation_message=_primary_degradation_message(summary_display),
        overdue_sample=overdue_sample,
        overdue_sample_message=_overdue_sample_message(overdue_sample),
        secondary_degradation_messages=summary_display.get("display_secondary_degradation_messages"),
        warning_messages=summary.get("warnings"),
        error_preview=cast(Optional[Sequence[str]], summary_display.get("errors_preview")),
        error_total=int(summary_display.get("error_total") or 0),
    )


__all__ = ["RunScheduleViewResult", "build_run_schedule_view_result"]
