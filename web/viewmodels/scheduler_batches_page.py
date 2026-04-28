from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .scheduler_analysis_labels import objective_label_for
from .scheduler_summary_display import build_summary_display_state

_AutoAssignPersistDisplayBuilder = Callable[[Any], Dict[str, Any]]
_BatchLabelBuilder = Callable[[str], str]


@dataclass(frozen=True)
class BatchesFilterState:
    status: str
    only_ready: str
    service_status: Optional[str]


@dataclass(frozen=True)
class SchedulerConfigPanelState:
    cfg: Any
    strategies: Sequence[Any]
    config_field_metadata: Dict[str, Any]
    config_field_warnings: Dict[str, str]
    config_degraded_fields: Sequence[str]
    config_degraded_field_labels: Tuple[str, ...]
    config_hidden_warnings: Sequence[str]
    presets: Sequence[Any]
    active_preset: Any
    builtin_presets: Sequence[str]
    current_config_state: Dict[str, Any]
    current_auto_assign_persist_state: Dict[str, Any]


@dataclass(frozen=True)
class LatestScheduleHistoryPanelState:
    latest_history: Optional[Dict[str, Any]]
    latest_summary: Optional[Dict[str, Any]]
    latest_summary_display: Dict[str, Any]
    latest_objective_label: str
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
            "latest_history": self.latest_panel.latest_history,
            "latest_summary": self.latest_panel.latest_summary,
            "latest_summary_display": self.latest_panel.latest_summary_display,
            "latest_objective_label": self.latest_panel.latest_objective_label,
            "latest_auto_assign_persist_state": self.latest_panel.latest_auto_assign_persist_state,
            "latest_other_degradation_messages": self.latest_panel.latest_other_degradation_messages,
            "latest_warning_preview": self.latest_panel.latest_warning_preview,
            "latest_warning_total": self.latest_panel.latest_warning_total,
            "latest_warning_hidden_count": self.latest_panel.latest_warning_hidden_count,
            "default_start_dt": self.default_start_dt,
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
                "priority_zh": priority_label(batch.priority),
                "ready_status_zh": ready_label(batch.ready_status),
                "status_zh": batch_status_label(batch.status),
            }
        )
    return view_rows


def build_scheduler_config_panel_state(
    *,
    cfg: Any,
    strategies: Sequence[Any],
    config_field_metadata: Dict[str, Any],
    config_field_warnings: Dict[str, str],
    config_degraded_fields: Sequence[str],
    config_hidden_warnings: Sequence[str],
    preset_display_state: Dict[str, Any],
    builtin_presets: Sequence[str],
    auto_assign_persist_display_builder: _AutoAssignPersistDisplayBuilder,
) -> SchedulerConfigPanelState:
    config_degraded_field_labels = tuple(
        str(getattr(config_field_metadata.get(field), "label", "") or field)
        for field in config_degraded_fields
    )
    return SchedulerConfigPanelState(
        cfg=cfg,
        strategies=strategies,
        config_field_metadata=config_field_metadata,
        config_field_warnings=config_field_warnings,
        config_degraded_fields=config_degraded_fields,
        config_degraded_field_labels=config_degraded_field_labels,
        config_hidden_warnings=config_hidden_warnings,
        presets=list(preset_display_state.get("presets") or []),
        active_preset=preset_display_state.get("active_preset"),
        builtin_presets=builtin_presets,
        current_config_state=dict(preset_display_state.get("current_config_state") or {}),
        current_auto_assign_persist_state=auto_assign_persist_display_builder(
            getattr(cfg, "auto_assign_persist", None)
        ),
    )


def _normalize_warning_texts(values: Any) -> List[str]:
    if not isinstance(values, (list, tuple)):
        return []
    out: List[str] = []
    seen = set()
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


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
    latest_warning_messages = _normalize_warning_texts(
        (latest_summary or {}).get("warnings") if isinstance(latest_summary, dict) else None
    )
    latest_warning_preview = list(latest_summary_display.get("warnings_preview") or [])
    if not latest_warning_preview and not latest_summary_display.get("warning_total"):
        latest_warning_preview = latest_warning_messages[:3]
    latest_warning_total = int(latest_summary_display.get("warning_total") or len(latest_warning_messages))
    latest_warning_hidden_count = int(
        latest_summary_display.get("warning_hidden_count") or max(0, latest_warning_total - len(latest_warning_preview))
    )
    latest_objective_label = "-"
    latest_auto_assign_persist_state = None
    latest_algo = latest_summary.get("algo") if isinstance(latest_summary, dict) else None
    if isinstance(latest_algo, dict):
        latest_objective_label = objective_label_for(latest_algo.get("objective"), algo=latest_algo)
        config_snapshot = latest_algo.get("config_snapshot")
        if isinstance(config_snapshot, dict):
            latest_auto_assign_persist_state = auto_assign_persist_display_builder(
                config_snapshot.get("auto_assign_persist")
            )
    return LatestScheduleHistoryPanelState(
        latest_history=latest_history,
        latest_summary=latest_summary,
        latest_summary_display=latest_summary_display,
        latest_objective_label=latest_objective_label,
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
    )


__all__ = [
    "BatchesFilterState",
    "LatestScheduleHistoryPanelState",
    "SchedulerBatchesPageViewModel",
    "SchedulerConfigPanelState",
    "build_batch_rows",
    "build_batches_filter_state",
    "build_latest_schedule_history_panel_state",
    "build_scheduler_batches_page_view_model",
    "build_scheduler_config_panel_state",
]
