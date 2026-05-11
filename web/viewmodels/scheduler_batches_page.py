from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .scheduler_analysis_labels import objective_label_for
from .scheduler_batches_notices import (
    latest_detail_notice_items,
    latest_parse_notice_items,
    latest_warning_state,
)
from .scheduler_config_panel import SchedulerConfigPanelState
from .scheduler_history_summary import ScheduleHistoryDisplayValueError, strict_strategy_display_label
from .scheduler_run_options import UiRunOption, build_run_options
from .scheduler_summary_display import build_summary_display_state
from .ui_presenters import UiDetailsNotice, UiNotice, UiSummaryItem

_AutoAssignPersistDisplayBuilder = Callable[[Any], Dict[str, Any]]
_BatchLabelBuilder = Callable[[str], str]

_ALGO_MODE_LABELS = {
    "improve": "优化模式",
    "greedy": "快速模式",
    "single": "单次排产",
}

_REQUIRED_METRIC_KEYS = (
    "total_tardiness_hours",
    "weighted_tardiness_hours",
    "makespan_hours",
    "changeover_count",
    "machine_util_avg",
)
_LATEST_HISTORY_DEGRADED_MESSAGE = "最近一次排产历史摘要不完整，请到系统管理里的排产历史查看这次排产的提醒摘要。"


@dataclass(frozen=True)
class BatchesFilterState:
    status: str
    only_ready: str
    service_status: Optional[str]


@dataclass(frozen=True)
class LatestScheduleHistoryPanelState:
    latest_history: Optional[Dict[str, Any]]
    latest_summary: Optional[Dict[str, Any]]
    latest_summary_display: Dict[str, Any]
    latest_objective_label: str
    latest_strategy_label: str
    latest_mode_label: str
    latest_result_status_label: str
    latest_metrics: Optional[Dict[str, Any]]
    head_items: Sequence[UiSummaryItem]
    meta_items: Sequence[UiSummaryItem]
    metric_items: Sequence[UiSummaryItem]
    status_items: Sequence[UiSummaryItem]
    notice_items: Sequence[UiNotice]
    detail_notice_items: Sequence[UiDetailsNotice]
    latest_auto_assign_persist_state: Optional[Dict[str, Any]]
    latest_other_degradation_messages: Sequence[Dict[str, Any]]
    latest_warning_preview: Sequence[str]
    latest_warning_total: int
    latest_warning_hidden_count: int


@dataclass(frozen=True)
class SchedulerBatchesPageViewModel:
    filter_state: BatchesFilterState
    batches: Sequence[Dict[str, Any]]
    pager: Any
    config_panel: SchedulerConfigPanelState
    latest_panel: LatestScheduleHistoryPanelState
    default_start_dt: str
    run_options: Sequence[UiRunOption]

    def as_template_context(self) -> Dict[str, Any]:
        return {
            "batches": list(self.batches),
            "status": self.filter_state.status,
            "only_ready": self.filter_state.only_ready,
            "cfg": self.config_panel.cfg,
            "strategies": self.config_panel.strategies,
            "config_field_metadata": self.config_panel.config_field_metadata,
            "config_field_warnings": self.config_panel.config_field_warnings,
            "config_degraded_fields": self.config_panel.config_degraded_fields,
            "config_degraded_field_labels": list(self.config_panel.config_degraded_field_labels),
            "config_hidden_warnings": self.config_panel.config_hidden_warnings,
            "presets": self.config_panel.presets,
            "active_preset": self.config_panel.active_preset,
            "builtin_presets": self.config_panel.builtin_presets,
            "current_config_state": self.config_panel.current_config_state,
            "current_auto_assign_persist_state": self.config_panel.current_auto_assign_persist_state,
            "config_notice_items": self.config_panel.notice_items,
            "current_config_notice_items": self.config_panel.current_config_notice_items,
            "current_config_display_items": self.config_panel.current_config_display_items,
            "latest_history": self.latest_panel.latest_history,
            "latest_summary": self.latest_panel.latest_summary,
            "latest_summary_display": self.latest_panel.latest_summary_display,
            "latest_objective_label": self.latest_panel.latest_objective_label,
            "latest_strategy_label": self.latest_panel.latest_strategy_label,
            "latest_mode_label": self.latest_panel.latest_mode_label,
            "latest_result_status_label": self.latest_panel.latest_result_status_label,
            "latest_metrics": self.latest_panel.latest_metrics,
            "latest_head_items": self.latest_panel.head_items,
            "latest_meta_items": self.latest_panel.meta_items,
            "latest_metric_items": self.latest_panel.metric_items,
            "latest_status_items": self.latest_panel.status_items,
            "latest_notice_items": self.latest_panel.notice_items,
            "latest_detail_notice_items": self.latest_panel.detail_notice_items,
            "latest_auto_assign_persist_state": self.latest_panel.latest_auto_assign_persist_state,
            "latest_other_degradation_messages": self.latest_panel.latest_other_degradation_messages,
            "latest_warning_preview": self.latest_panel.latest_warning_preview,
            "latest_warning_total": self.latest_panel.latest_warning_total,
            "latest_warning_hidden_count": self.latest_panel.latest_warning_hidden_count,
            "default_start_dt": self.default_start_dt,
            "run_options": self.run_options,
            "pager": self.pager,
        }


def build_batches_filter_state(
    *,
    has_status_arg: bool,
    raw_status: Any,
    raw_only_ready: Any,
) -> BatchesFilterState:
    status = (str(raw_status or "").strip()) if has_status_arg else "pending"
    only_ready = str(raw_only_ready or "").strip()
    return BatchesFilterState(
        status=status,
        only_ready=only_ready,
        service_status=status if status else None,
    )


def build_batch_rows(
    batches: Sequence[Any],
    *,
    only_ready: str,
    priority_label: _BatchLabelBuilder,
    ready_label: _BatchLabelBuilder,
    batch_status_label: _BatchLabelBuilder,
) -> List[Dict[str, Any]]:
    view_rows: List[Dict[str, Any]] = []
    for batch in batches:
        if only_ready and (batch.ready_status or "") != only_ready:
            continue
        view_rows.append(
            {
                **batch.to_dict(),
                "priority_label": priority_label(batch.priority),
                "ready_status_label": ready_label(batch.ready_status),
                "status_label": batch_status_label(batch.status),
            }
        )
    return view_rows


def _latest_algo_mode_label(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ScheduleHistoryDisplayValueError("排产历史摘要缺少排产模式")
    if raw not in _ALGO_MODE_LABELS:
        raise ScheduleHistoryDisplayValueError(f"未知排产模式：{raw}")
    return _ALGO_MODE_LABELS[raw]


def _metric_value(value: Any, unit: str) -> str:
    return f"{value} {unit}"


def _metric_percent(metrics: Dict[str, Any], key: str) -> str:
    amount = round(_metric_number(metrics, key) * 100, 2)
    return f"{amount}%"


def _required_metric(metrics: Dict[str, Any], key: str) -> Any:
    if key not in metrics:
        raise ScheduleHistoryDisplayValueError(f"排产历史摘要 metrics 缺少字段：{key}")
    value = metrics[key]
    if value is None or value == "":
        raise ScheduleHistoryDisplayValueError(f"排产历史摘要 metrics 字段为空：{key}")
    return value


def _metric_number(metrics: Dict[str, Any], key: str) -> float:
    value = _required_metric(metrics, key)
    if isinstance(value, bool):
        raise ScheduleHistoryDisplayValueError(f"排产历史摘要 metrics 字段不是数字：{key}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ScheduleHistoryDisplayValueError(f"排产历史摘要 metrics 字段不是数字：{key}") from exc
    if not math.isfinite(number):
        raise ScheduleHistoryDisplayValueError(f"排产历史摘要 metrics 字段不是数字：{key}")
    return number


def _required_number_metric(metrics: Dict[str, Any], key: str) -> Any:
    value = _required_metric(metrics, key)
    _metric_number(metrics, key)
    return value


def _latest_history_items(
    latest_history: Optional[Dict[str, Any]],
    *,
    result_status_label: str,
) -> Tuple[str, Tuple[UiSummaryItem, ...], Tuple[UiSummaryItem, ...]]:
    if not latest_history:
        return "-", (), ()
    strategy_label = strict_strategy_display_label(latest_history.get("strategy"))
    return (
        strategy_label,
        (
            UiSummaryItem("版本", f"v{latest_history.get('version') or '-'}"),
            UiSummaryItem("结果", result_status_label),
            UiSummaryItem("排产时间", str(latest_history.get("schedule_time") or "-")),
        ),
        (UiSummaryItem("排产方式", strategy_label),),
    )


def _latest_auto_assign_enabled_item(value: Any) -> UiSummaryItem:
    normalized = str(value or "").strip().lower()
    if normalized == "yes":
        return UiSummaryItem("自动补设备人员", "已启用")
    if normalized == "no":
        return UiSummaryItem("自动补设备人员", "已关闭")
    if not normalized:
        return UiSummaryItem("自动补设备人员", "旧历史未记录", tone="warning")
    return UiSummaryItem("自动补设备人员", "记录异常", tone="warning")


def _latest_algo_items(
    latest_algo: Dict[str, Any],
    *,
    meta_items: Tuple[UiSummaryItem, ...],
    auto_assign_persist_display_builder: _AutoAssignPersistDisplayBuilder,
) -> Tuple[str, str, Optional[Dict[str, Any]], Tuple[UiSummaryItem, ...], Optional[Dict[str, Any]]]:
    objective_label = objective_label_for(latest_algo.get("objective"), algo=latest_algo)
    mode_label = _latest_algo_mode_label(latest_algo.get("mode"))
    latest_metrics = _required_latest_metrics(latest_algo)
    auto_assign_state = None
    config_snapshot = latest_algo.get("config_snapshot")
    if isinstance(config_snapshot, dict):
        auto_assign_state = auto_assign_persist_display_builder(config_snapshot.get("auto_assign_persist"))
        auto_assign_enabled_item = _latest_auto_assign_enabled_item(config_snapshot.get("auto_assign_enabled"))
    else:
        auto_assign_enabled_item = None
    return (
        objective_label,
        mode_label,
        latest_metrics,
        (
            *meta_items,
            UiSummaryItem("模式", mode_label),
            UiSummaryItem("目标", objective_label),
            *((auto_assign_enabled_item,) if auto_assign_enabled_item else ()),
        ),
        auto_assign_state,
    )


def _required_latest_algo(latest_summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if latest_summary is None:
        return None
    if "algo" not in latest_summary:
        raise ScheduleHistoryDisplayValueError("排产历史摘要缺少 algo")
    latest_algo = latest_summary.get("algo")
    if not isinstance(latest_algo, dict):
        raise ScheduleHistoryDisplayValueError("排产历史摘要 algo 字段不是对象")
    return latest_algo


def _required_latest_metrics(latest_algo: Dict[str, Any]) -> Dict[str, Any]:
    if "metrics" not in latest_algo:
        raise ScheduleHistoryDisplayValueError("排产历史摘要 algo 缺少 metrics")
    metrics = latest_algo.get("metrics")
    if not isinstance(metrics, dict):
        raise ScheduleHistoryDisplayValueError("排产历史摘要 algo.metrics 字段不是对象")
    return metrics


def _latest_metric_items(
    latest_summary: Optional[Dict[str, Any]],
    latest_metrics: Optional[Dict[str, Any]],
) -> Tuple[UiSummaryItem, ...]:
    metric_items: Tuple[UiSummaryItem, ...] = ()
    if isinstance(latest_summary, dict):
        overdue_batches = latest_summary.get("overdue_batches")
        if isinstance(overdue_batches, dict):
            metric_items = (UiSummaryItem("超期数量", f"{_required_number_metric(overdue_batches, 'count')} 个"),)
    if latest_metrics is None:
        return metric_items
    metric_values = {key: _required_number_metric(latest_metrics, key) for key in _REQUIRED_METRIC_KEYS}
    return (
        *metric_items,
        UiSummaryItem("拖期", _metric_value(metric_values["total_tardiness_hours"], "小时")),
        UiSummaryItem("加权拖期", _metric_value(metric_values["weighted_tardiness_hours"], "小时")),
        UiSummaryItem("总工期", _metric_value(metric_values["makespan_hours"], "小时")),
        UiSummaryItem("换型", _metric_value(metric_values["changeover_count"], "次")),
        UiSummaryItem("设备利用率", _metric_percent(latest_metrics, "machine_util_avg")),
    )


def build_degraded_latest_schedule_history_panel_state(
    *,
    latest_history: Optional[Dict[str, Any]],
    latest_summary: Optional[Dict[str, Any]],
    latest_summary_parse_state: Dict[str, Any],
    error: ScheduleHistoryDisplayValueError,
) -> LatestScheduleHistoryPanelState:
    latest_summary_display = build_summary_display_state(
        latest_summary if isinstance(latest_summary, dict) else None,
        result_status=(latest_history or {}).get("result_status"),
        parse_state=latest_summary_parse_state,
    )
    latest_warning_preview, latest_warning_total, latest_warning_hidden_count = latest_warning_state(
        latest_summary=latest_summary,
        latest_summary_display=latest_summary_display,
    )
    latest_result_status_label = str(latest_summary_display.get("result_status_label") or "-")
    detail_notice_items = latest_detail_notice_items(
        latest_summary_display=latest_summary_display,
        latest_warning_preview=latest_warning_preview,
        latest_warning_total=latest_warning_total,
        latest_warning_hidden_count=latest_warning_hidden_count,
    )
    head_items: Tuple[UiSummaryItem, ...] = ()
    if latest_history:
        head_items = (
            UiSummaryItem("版本", f"v{latest_history.get('version') or '-'}"),
            UiSummaryItem("结果", latest_result_status_label),
            UiSummaryItem("排产时间", str(latest_history.get("schedule_time") or "-")),
        )
    return LatestScheduleHistoryPanelState(
        latest_history=latest_history,
        latest_summary=latest_summary,
        latest_summary_display=latest_summary_display,
        latest_objective_label="-",
        latest_strategy_label="-",
        latest_mode_label="-",
        latest_result_status_label=latest_result_status_label,
        latest_metrics=None,
        head_items=head_items,
        meta_items=(),
        metric_items=(),
        status_items=(),
        notice_items=(
            UiNotice(
                "最近一次排产历史摘要不完整",
                _LATEST_HISTORY_DEGRADED_MESSAGE,
                tone="warning",
                role="status",
                aria_live="polite",
            ),
            *latest_parse_notice_items(latest_summary_display),
        ),
        detail_notice_items=detail_notice_items,
        latest_auto_assign_persist_state=None,
        latest_other_degradation_messages=list(
            latest_summary_display.get("display_secondary_degradation_messages") or []
        ),
        latest_warning_preview=latest_warning_preview,
        latest_warning_total=latest_warning_total,
        latest_warning_hidden_count=latest_warning_hidden_count,
    )


def build_latest_schedule_history_panel_state(
    *,
    latest_history: Optional[Dict[str, Any]],
    latest_summary: Optional[Dict[str, Any]],
    latest_summary_parse_state: Dict[str, Any],
    auto_assign_persist_display_builder: _AutoAssignPersistDisplayBuilder,
) -> LatestScheduleHistoryPanelState:
    latest_summary_display = build_summary_display_state(
        latest_summary if isinstance(latest_summary, dict) else None,
        result_status=(latest_history or {}).get("result_status"),
        parse_state=latest_summary_parse_state,
    )
    latest_warning_preview, latest_warning_total, latest_warning_hidden_count = latest_warning_state(
        latest_summary=latest_summary,
        latest_summary_display=latest_summary_display,
    )
    latest_result_status_label = str(latest_summary_display.get("result_status_label") or "-")
    detail_notice_items = latest_detail_notice_items(
        latest_summary_display=latest_summary_display,
        latest_warning_preview=latest_warning_preview,
        latest_warning_total=latest_warning_total,
        latest_warning_hidden_count=latest_warning_hidden_count,
    )
    latest_strategy_label, head_items, meta_items = _latest_history_items(
        latest_history,
        result_status_label=latest_result_status_label,
    )
    latest_algo = _required_latest_algo(latest_summary)
    latest_objective_label = "-"
    latest_mode_label = "-"
    latest_metrics = None
    latest_auto_assign_persist_state = None
    if latest_algo is not None:
        latest_objective_label, latest_mode_label, latest_metrics, meta_items, latest_auto_assign_persist_state = (
            _latest_algo_items(
                latest_algo,
                meta_items=meta_items,
                auto_assign_persist_display_builder=auto_assign_persist_display_builder,
            )
        )
    metric_items = _latest_metric_items(latest_summary, latest_metrics)
    return LatestScheduleHistoryPanelState(
        latest_history=latest_history,
        latest_summary=latest_summary,
        latest_summary_display=latest_summary_display,
        latest_objective_label=latest_objective_label,
        latest_strategy_label=latest_strategy_label,
        latest_mode_label=latest_mode_label,
        latest_result_status_label=latest_result_status_label,
        latest_metrics=latest_metrics,
        head_items=head_items,
        meta_items=meta_items,
        metric_items=metric_items,
        status_items=(),
        notice_items=latest_parse_notice_items(latest_summary_display),
        detail_notice_items=detail_notice_items,
        latest_auto_assign_persist_state=latest_auto_assign_persist_state,
        latest_other_degradation_messages=list(
            latest_summary_display.get("display_secondary_degradation_messages") or []
        ),
        latest_warning_preview=latest_warning_preview,
        latest_warning_total=latest_warning_total,
        latest_warning_hidden_count=latest_warning_hidden_count,
    )


def build_scheduler_batches_page_view_model(
    *,
    filter_state: BatchesFilterState,
    batches: Sequence[Dict[str, Any]],
    pager: Any,
    config_panel: SchedulerConfigPanelState,
    latest_panel: LatestScheduleHistoryPanelState,
    current_time: datetime,
) -> SchedulerBatchesPageViewModel:
    return SchedulerBatchesPageViewModel(
        filter_state=filter_state,
        batches=batches,
        pager=pager,
        config_panel=config_panel,
        latest_panel=latest_panel,
        default_start_dt=(current_time + timedelta(days=1)).strftime("%Y-%m-%d 08:00"),
        run_options=build_run_options(
            cfg=config_panel.cfg,
            config_field_warnings=config_panel.config_field_warnings,
        ),
    )


__all__ = [
    "BatchesFilterState",
    "LatestScheduleHistoryPanelState",
    "SchedulerBatchesPageViewModel",
    "ScheduleHistoryDisplayValueError",
    "UiRunOption",
    "build_batch_rows",
    "build_batches_filter_state",
    "build_degraded_latest_schedule_history_panel_state",
    "build_latest_schedule_history_panel_state",
    "build_run_options",
    "build_scheduler_batches_page_view_model",
    "_ALGO_MODE_LABELS",
]
