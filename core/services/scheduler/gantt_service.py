from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.services.common.degradation import degradation_events_to_dicts
from data.repositories import ScheduleHistoryRepository, ScheduleRepository

from .calendar_service import CalendarService
from .execution_fact_provider import ExecutionFactProvider
from .gantt_contract import build_gantt_contract
from .gantt_critical_chain_provider import GanttCriticalChainProvider
from .gantt_plan_query import (
    attach_gantt_range_metadata,
    build_empty_week_plan_payload,
    get_version_time_span_dates,
    resolve_gantt_range_for_version,
)
from .gantt_range import WeekRange, resolve_week_range
from .gantt_resource_load import compute_gantt_resource_day_load
from .gantt_service_support import (
    collect_gantt_degradation_events,
    critical_chain_for_plan_detail_filter,
    log_overdue_marker_degraded,
    log_overdue_marker_partial,
    overdue_batch_ids_from_history_meta,
    plan_detail_filter_kwargs,
)
from .gantt_tasks import build_calendar_days, build_tasks
from .gantt_week_plan import build_week_plan_rows
from .plan_overdue_markers import build_overdue_meta_for_plan
from .schedule_plan_query_service import SchedulePlanQueryService
from .schedule_result_view_context import (
    ScheduleResultViewContext,
    attach_plan_metadata,
    default_plan_resolution_dict,
    resolve_schedule_result_view_context,
    selected_plan_role,
)
from .schedule_result_view_range import resolve_schedule_result_week_range
from .version_resolution import VersionResolution, require_selected_version, resolve_version_or_latest


class GanttService:
    """
    Phase 8：甘特图与周计划服务（对外 façade）。

    职责：
    - 按周范围 + version 输出甘特 tasks（供 Frappe Gantt 渲染）
    - 生成周计划表导出行（按天切分时段）
    - 复用 ScheduleHistory.result_summary 的超期信息做标记
    """
    CONTRACT_VERSION = 3  # v3：新增 resource_load（fusion-gantt-load-strip）

    def __init__(self, conn, logger=None, op_logger=None, plan_query_service=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.schedule_repo = ScheduleRepository(conn, logger=logger)
        self.history_repo = ScheduleHistoryRepository(conn, logger=logger)
        self._plan_query_service = plan_query_service
        self._critical_chain_provider = None

    def resolve_version(self, value: Any) -> VersionResolution:
        latest = int(self.history_repo.get_latest_version() or 0)
        return resolve_version_or_latest(
            value,
            latest_version=latest,
            version_exists=lambda version: self.history_repo.get_by_version(int(version)) is not None,
        )

    def _get_plan_query_service(self, plan_query_service=None) -> SchedulePlanQueryService:
        if plan_query_service is not None:
            return plan_query_service
        if self._plan_query_service is None:
            self._plan_query_service = SchedulePlanQueryService(self.conn, logger=self.logger)
        return self._plan_query_service

    def _get_critical_chain_provider(self) -> GanttCriticalChainProvider:
        if self._critical_chain_provider is None:
            self._critical_chain_provider = GanttCriticalChainProvider(
                conn=self.conn,
                schedule_repo=self.schedule_repo,
                plan_query_service_factory=self._get_plan_query_service,
                logger=self.logger,
            )
        return self._critical_chain_provider

    def resolve_result_view_context(
        self,
        *,
        version: Any = None,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
        plan_query_service=None,
        require_existing_version: bool = False,
    ) -> ScheduleResultViewContext:
        latest = int(self.history_repo.get_latest_version() or 0)
        return resolve_schedule_result_view_context(
            raw_version=version,
            raw_plan_role=plan_role,
            raw_scenario_id=scenario_id,
            latest_version=latest,
            version_exists=lambda item: self.history_repo.get_by_version(int(item)) is not None,
            plan_query_service=self._get_plan_query_service(plan_query_service),
            require_existing_version=require_existing_version,
        )

    def resolve_plan_context(
        self,
        version: Optional[Any],
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
        plan_query_service=None,
    ) -> Dict[str, Any]:
        return self.resolve_result_view_context(
            version=version,
            plan_role=plan_role,
            scenario_id=scenario_id,
            plan_query_service=plan_query_service,
            require_existing_version=version is not None,
        ).plan_resolution

    def _empty_gantt_contract(
        self,
        *,
        view: str,
        week_start: Optional[str],
        offset_weeks: int,
        start_date: Optional[str],
        end_date: Optional[str],
        include_history: bool,
        resolution: VersionResolution,
        plan_role: Optional[str] = None,
        plan_resolution: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        wr, _, _ = resolve_schedule_result_week_range(
            plan_query_service=None,
            version=None,
            plan_role=None,
            week_start=week_start,
            offset_weeks=offset_weeks,
            start_date=start_date,
            end_date=end_date,
            default_to_version_span=False,
        )
        calendar_days_outcome = build_calendar_days(self.conn, wr=wr, logger=self.logger, op_logger=self.op_logger)
        out = build_gantt_contract(
            contract_version=self.CONTRACT_VERSION,
            view=view,
            version=None,
            week_start=wr.week_start_date.isoformat(),
            week_end=wr.week_end_date.isoformat(),
            tasks=[],
            calendar_days=calendar_days_outcome.value,
            critical_chain={"available": False, "reason": "no_history"},
            degraded=bool(calendar_days_outcome.has_events),
            degradation_events=degradation_events_to_dicts(calendar_days_outcome.events),
            degradation_counters=calendar_days_outcome.counters,
            empty_reason="no_history",
            include_history=include_history,
            history=None,
        )
        out["has_history"] = False
        out["status"] = resolution.status
        out["requested_version"] = resolution.requested_version
        attach_plan_metadata(out, plan_resolution or default_plan_resolution_dict(plan_role))
        return out

    def resolve_week_range(
        self,
        week_start: Optional[str] = None,
        offset_weeks: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> WeekRange:
        return resolve_week_range(week_start=week_start, offset_weeks=offset_weeks, start_date=start_date, end_date=end_date)

    def get_version_time_span_dates(
        self,
        version: int,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
        plan_query_service=None,
    ) -> Optional[Dict[str, Any]]:
        plan_query = self._get_plan_query_service(plan_query_service)
        return get_version_time_span_dates(plan_query, int(version), plan_role, scenario_id)

    def resolve_gantt_range_for_version(
        self,
        *,
        version: Optional[int],
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
        plan_query_service=None,
        week_start: Optional[str] = None,
        offset_weeks: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple[WeekRange, Optional[Dict[str, Any]], str]:
        return resolve_gantt_range_for_version(
            plan_query_service=self._get_plan_query_service(plan_query_service),
            version=version,
            plan_role=plan_role,
            scenario_id=scenario_id,
            week_start=week_start,
            offset_weeks=offset_weeks,
            start_date=start_date,
            end_date=end_date,
        )

    # 三个薄壳保签名：_overdue_batch_ids_from_history 被测试 monkeypatch、
    # _log_* 在 build_overdue_meta_for_plan 被当 callback 传出，实现在 support
    def _log_overdue_marker_degraded(self, *, version: int, reason: str, message: str) -> None:
        log_overdue_marker_degraded(self.logger, version=version, reason=reason, message=message)

    def _log_overdue_marker_partial(self, *, version: int, reason: str, message: str) -> None:
        log_overdue_marker_partial(self.logger, version=version, reason=reason, message=message)

    def _overdue_batch_ids_from_history(self, version: int) -> Dict[str, Any]:
        return overdue_batch_ids_from_history_meta(self.history_repo, self.logger, version)

    def _history_payload_for_gantt(self, *, version: int, include_history: bool) -> Optional[Dict[str, Any]]:
        if not include_history:
            return None
        hist = self.history_repo.get_by_version(version)
        return hist.to_dict() if hist else None

    def _execution_facts_by_op_id(self, rows, plan_resolution: Dict[str, Any]) -> Dict[int, Any]:
        op_ids = []
        seen = set()
        for row in rows or []:
            try:
                op_id = int((row or {}).get("op_id") or 0)
            except (TypeError, ValueError):
                continue
            if op_id <= 0 or op_id in seen:
                continue
            seen.add(op_id)
            op_ids.append(op_id)
        if not op_ids:
            return {}
        return ExecutionFactProvider(self.conn, logger=self.logger).facts_by_op_id_for_plan_rows(
            rows,
            {
                "version": plan_resolution.get("version"),
                "source_table": plan_resolution.get("source_table"),
                "effective_plan_role": selected_plan_role(plan_resolution),
                "scenario_id": plan_resolution.get("scenario_id"),
            },
            include_op_ids=op_ids,
        )

    def get_gantt_tasks(
        self,
        *,
        view: str,
        week_start: Optional[str] = None,
        offset_weeks: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        version: Optional[int] = None,
        include_history: bool = False,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        plan_query_service=None,
    ) -> Dict[str, Any]:
        """返回甘特图数据（tasks + 元信息）。"""
        view = (view or "").strip() or "machine"
        if view not in ("machine", "operator"):
            raise ValidationError("视图不正确，请选择：设备 / 人员。", field="视图")

        plan_query = self._get_plan_query_service(plan_query_service)
        view_context = self.resolve_result_view_context(
            version=version,
            plan_role=plan_role,
            scenario_id=scenario_id,
            plan_query_service=plan_query,
            require_existing_version=True,
        )
        resolution = view_context.version_resolution
        if resolution.status == "no_history":
            return self._empty_gantt_contract(
                view=view,
                week_start=week_start,
                offset_weeks=offset_weeks,
                start_date=start_date,
                end_date=end_date,
                include_history=include_history,
                resolution=resolution,
                plan_role=plan_role,
                plan_resolution=view_context.plan_resolution,
            )
        ver = require_selected_version(resolution)
        plan_resolution = view_context.plan_resolution
        wr, version_span, range_source = self.resolve_gantt_range_for_version(
            version=ver,
            plan_role=selected_plan_role(plan_resolution),
            scenario_id=plan_resolution.get("scenario_id"),
            plan_query_service=plan_query,
            week_start=week_start,
            offset_weeks=offset_weeks,
            start_date=start_date,
            end_date=end_date,
        )

        calendar_days_outcome = build_calendar_days(self.conn, wr=wr, logger=self.logger, op_logger=self.op_logger)
        detail_filters = plan_detail_filter_kwargs(resource_type=resource_type, resource_id=resource_id, batch_id=batch_id)
        rows = plan_query.list_plan_detail_rows_between_for_resolution(
            version=ver,
            source_table=str(plan_resolution.get("source_table") or ""),
            candidate_id=plan_resolution.get("candidate_id"),
            scenario_id=plan_resolution.get("scenario_id"),
            start_time=wr.start_str,
            end_time=wr.end_exclusive_str,
            **detail_filters,
        )
        effective_role = selected_plan_role(plan_resolution)
        try:
            overdue_meta = build_overdue_meta_for_plan(
                version=ver,
                role=effective_role,
                source_table=str(plan_resolution.get("source_table") or ""),
                list_plan_overdue_base_rows=lambda **_: plan_query.list_plan_overdue_base_rows_for_resolution(
                    version=ver,
                    source_table=str(plan_resolution.get("source_table") or ""),
                    candidate_id=plan_resolution.get("candidate_id"),
                    scenario_id=plan_resolution.get("scenario_id"),
                    **detail_filters,
                ),
                load_adopted_meta=self._overdue_batch_ids_from_history,
                log_degraded=self._log_overdue_marker_degraded,
            )
        except ValueError as exc:
            raise ValidationError(str(exc), field="plan_role") from exc
        overdue_set = set(overdue_meta.get("ids") or [])

        execution_facts_by_op_id = self._execution_facts_by_op_id(rows, plan_resolution)
        tasks_outcome = build_tasks(
            view=view,
            wr=wr,
            rows=rows,
            overdue_set=overdue_set,
            execution_facts_by_op_id=execution_facts_by_op_id,
        )
        empty_reason = tasks_outcome.empty_reason or calendar_days_outcome.empty_reason

        critical_chain = critical_chain_for_plan_detail_filter(rows, detail_filters)
        if critical_chain is None:
            critical_chain = self._get_critical_chain_provider().get_critical_chain(
                ver,
                plan_resolution=plan_resolution,
                plan_query_service=plan_query,
            )
        resource_load_outcome = compute_gantt_resource_day_load(
            view=view,
            rows=rows,
            wr=wr,
            calendar=CalendarService(self.conn, logger=self.logger, op_logger=self.op_logger),
        )
        degradation_collector = collect_gantt_degradation_events(
            calendar_days_outcome=calendar_days_outcome,
            tasks_outcome=tasks_outcome,
            critical_chain=critical_chain,
        )
        degradation_collector.extend(resource_load_outcome.events)
        hist_dict = self._history_payload_for_gantt(version=ver, include_history=include_history)

        data = build_gantt_contract(
            contract_version=self.CONTRACT_VERSION,
            view=view,
            version=ver,
            week_start=wr.week_start_date.isoformat(),
            week_end=wr.week_end_date.isoformat(),
            tasks=tasks_outcome.value,
            calendar_days=calendar_days_outcome.value,
            resource_load=resource_load_outcome.value,
            critical_chain=critical_chain,
            degraded=bool(degradation_collector),
            degradation_events=degradation_events_to_dicts(degradation_collector.to_list()),
            degradation_counters=degradation_collector.to_counters(),
            empty_reason=empty_reason,
            overdue_markers_degraded=bool(overdue_meta.get("degraded")),
            overdue_markers_partial=bool(overdue_meta.get("partial")),
            overdue_markers_message=str(overdue_meta.get("message") or ""),
            include_history=include_history,
            history=hist_dict if include_history else None,
        )
        attach_gantt_range_metadata(
            data,
            resolution=resolution,
            version_span=version_span,
            range_source=range_source,
            wr=wr,
            plan_resolution=plan_resolution,
        )
        return data

    def get_week_plan_rows(
        self,
        *,
        week_start: Optional[str] = None,
        offset_weeks: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        version: Optional[int] = None,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        plan_query_service=None,
    ) -> Dict[str, Any]:
        """
        返回周计划行（用于页面预览与导出）。
        字段：日期/批次号/图号/工序/设备/人员/时段/现场状态。
        """
        plan_query = self._get_plan_query_service(plan_query_service)
        wr, _, _ = resolve_schedule_result_week_range(
            plan_query_service=plan_query,
            version=None,
            plan_role=None,
            week_start=week_start,
            offset_weeks=offset_weeks,
            start_date=start_date,
            end_date=end_date,
            default_to_version_span=False,
        )
        view_context = self.resolve_result_view_context(
            version=version,
            plan_role=plan_role,
            scenario_id=scenario_id,
            plan_query_service=plan_query,
            require_existing_version=True,
        )
        resolution = view_context.version_resolution
        if resolution.status == "no_history":
            plan_resolution = view_context.plan_resolution
            return build_empty_week_plan_payload(wr=wr, resolution=resolution, plan_resolution=plan_resolution)
        ver = require_selected_version(resolution)
        plan_resolution = view_context.plan_resolution

        detail_filters = plan_detail_filter_kwargs(resource_type=resource_type, resource_id=resource_id, batch_id=batch_id)
        rows = plan_query.list_plan_detail_rows_between_for_resolution(
            version=ver,
            source_table=str(plan_resolution.get("source_table") or ""),
            candidate_id=plan_resolution.get("candidate_id"),
            scenario_id=plan_resolution.get("scenario_id"),
            start_time=wr.start_str,
            end_time=wr.end_exclusive_str,
            **detail_filters,
        )
        execution_facts = self._execution_facts_by_op_id(rows, plan_resolution)
        outcome, daily_planned_minutes = build_week_plan_rows(
            rows=rows, wr=wr, execution_facts_by_op_id=execution_facts
        )
        hist = self.history_repo.get_by_version(ver)
        data = {
            "version": ver,
            "requested_version": resolution.requested_version,
            "status": "ok",
            "has_history": True,
            "week_start": wr.week_start_date.isoformat(),
            "week_end": wr.week_end_date.isoformat(),
            "rows": outcome.value,
            "daily_planned_minutes": daily_planned_minutes,
            "degraded": outcome.has_events,
            "degradation_events": degradation_events_to_dicts(outcome.events),
            "degradation_counters": outcome.counters,
            "empty_reason": outcome.empty_reason,
            "history": hist.to_dict() if hist else None,
        }
        attach_plan_metadata(data, plan_resolution)
        return data
