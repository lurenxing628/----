from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.services.common.degradation import DegradationCollector, DegradationEvent, degradation_events_to_dicts
from data.repositories import ScheduleHistoryRepository, ScheduleRepository

from .gantt_contract import build_gantt_contract
from .gantt_critical_chain import compute_critical_chain, compute_critical_chain_from_rows
from .gantt_plan_query import (
    attach_gantt_range_metadata,
    attach_plan_metadata,
    build_empty_week_plan_payload,
    default_plan_resolution_dict,
    get_version_time_span_dates,
    resolve_gantt_range_for_version,
    resolve_plan,
    selected_plan_role,
)
from .gantt_range import WeekRange, resolve_week_range
from .gantt_tasks import build_calendar_days, build_tasks
from .gantt_week_plan import build_week_plan_rows
from .plan_overdue_markers import build_overdue_meta_for_plan
from .resource_dispatch_support import extract_overdue_batch_ids_with_meta
from .schedule_plan_query_service import ROLE_ADOPTED, SchedulePlanQueryService
from .version_resolution import VersionResolution, require_selected_version, resolve_version_or_latest


class GanttService:
    """
    Phase 8：甘特图与周计划服务（对外 façade）。

    职责：
    - 按周范围 + version 输出甘特 tasks（供 Frappe Gantt 渲染）
    - 生成周计划表导出行（按天切分时段）
    - 复用 ScheduleHistory.result_summary 的超期信息做标记
    """
    CONTRACT_VERSION = 2
    _CRITICAL_CHAIN_CACHE_MAX = 64
    _CRITICAL_CHAIN_CACHE: OrderedDict[tuple, Dict[str, Any]] = OrderedDict()
    _CRITICAL_CHAIN_CACHE_LOCK = threading.Lock()

    def __init__(self, conn, logger=None, op_logger=None, plan_query_service=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.schedule_repo = ScheduleRepository(conn, logger=logger)
        self.history_repo = ScheduleHistoryRepository(conn, logger=logger)
        self._plan_query_service = plan_query_service

    def get_latest_version_or_1(self) -> int:
        v = int(self.history_repo.get_latest_version() or 0)
        return v if v > 0 else 0

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

    def resolve_plan_context(self, version: int, plan_role: Optional[str] = None, plan_query_service=None) -> Dict[str, Any]:
        plan_query = self._get_plan_query_service(plan_query_service)
        return resolve_plan(plan_query, int(version), plan_role).to_dict()

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
    ) -> Dict[str, Any]:
        wr = self.resolve_week_range(
            week_start=week_start,
            offset_weeks=offset_weeks,
            start_date=start_date,
            end_date=end_date,
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
        attach_plan_metadata(out, default_plan_resolution_dict(plan_role))
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
        plan_query_service=None,
    ) -> Optional[Dict[str, Any]]:
        plan_query = self._get_plan_query_service(plan_query_service)
        return get_version_time_span_dates(plan_query, int(version), plan_role)

    def resolve_gantt_range_for_version(
        self,
        *,
        version: Optional[int],
        plan_role: Optional[str] = None,
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
            week_start=week_start,
            offset_weeks=offset_weeks,
            start_date=start_date,
            end_date=end_date,
        )

    def _log_overdue_marker_degraded(self, *, version: int, reason: str, message: str) -> None:
        if self.logger is None:
            return
        self.logger.warning(
            "甘特图超期标记降级（service=GanttService, page=gantt, version=%s, source=%s, message=%s）",
            version,
            reason or "unknown",
            message or "",
        )

    def _log_overdue_marker_partial(self, *, version: int, reason: str, message: str) -> None:
        if self.logger is None:
            return
        self.logger.warning(
            "甘特图超期标记部分不完整（service=GanttService, page=gantt, version=%s, source=%s, message=%s）",
            version,
            reason or "unknown",
            message or "",
        )

    def _overdue_batch_ids_from_history(self, version: int) -> Dict[str, Any]:
        hist = self.history_repo.get_by_version(int(version))
        if not hist:
            meta = {
                "ids": [],
                "degraded": True,
                "partial": False,
                "message": "排产历史缺失，超期标记可能不完整。",
                "reason": "history_missing",
            }
            self._log_overdue_marker_degraded(version=int(version), reason=str(meta["reason"]), message=str(meta["message"]))
            return meta

        meta = extract_overdue_batch_ids_with_meta(hist.result_summary)
        if meta.get("degraded"):
            self._log_overdue_marker_degraded(
                version=int(version), reason=str(meta.get("reason") or "unknown"), message=str(meta.get("message") or "")
            )
        elif meta.get("partial"):
            self._log_overdue_marker_partial(
                version=int(version), reason=str(meta.get("reason") or "unknown"), message=str(meta.get("message") or "")
            )
        return meta

    def _critical_chain_cache_key(self, version: int, *, plan_resolution: Dict[str, Any]) -> tuple:
        scope = str(id(self.conn))
        try:
            rows = self.conn.execute("PRAGMA database_list").fetchall()
            for r in rows or []:
                try:
                    name = r["name"] if isinstance(r, dict) or hasattr(r, "keys") else r[1]
                    if str(name) != "main":
                        continue
                    file_path = r["file"] if isinstance(r, dict) or hasattr(r, "keys") else r[2]
                    if file_path:
                        scope = str(file_path)
                    break
                except Exception:
                    continue
        except Exception:
            pass
        return (
            scope,
            int(version),
            str(plan_resolution.get("selected_role") or ROLE_ADOPTED),
            str(plan_resolution.get("source_table") or "schedule"),
            int(plan_resolution.get("candidate_id") or 0),
        )

    @staticmethod
    def _normalize_critical_chain_result(raw: Any) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            raw = {}
        available = raw.get("available")
        if isinstance(available, bool):
            is_available = available
        else:
            is_available = True
        reason_text = str(raw.get("reason") or "").strip()
        if is_available:
            reason_text = ""
        return {
            "ids": list(raw.get("ids") or []),
            "edges": list(raw.get("edges") or []),
            "makespan_end": raw.get("makespan_end"),
            "edge_type_stats": dict(
                raw.get("edge_type_stats") or {"process": 0, "machine": 0, "operator": 0, "unknown": 0}
            ),
            "edge_count": int(raw.get("edge_count") or 0),
            "available": is_available,
            "reason": reason_text,
        }

    @staticmethod
    def _critical_chain_cacheable(result: Dict[str, Any]) -> bool:
        return bool(result.get("available", True))

    def _get_critical_chain(
        self,
        version: int,
        *,
        plan_resolution: Optional[Dict[str, Any]] = None,
        plan_query_service=None,
    ) -> Dict[str, Any]:
        plan_resolution = plan_resolution or default_plan_resolution_dict(ROLE_ADOPTED)
        key = self._critical_chain_cache_key(version, plan_resolution=plan_resolution)
        with self._CRITICAL_CHAIN_CACHE_LOCK:
            cached = self._CRITICAL_CHAIN_CACHE.get(key)
            if cached is not None:
                try:
                    self._CRITICAL_CHAIN_CACHE.move_to_end(key)
                except Exception:
                    pass
                out = dict(cached)
                out["cache_hit"] = True
                return out

        role = str(plan_resolution.get("selected_role") or ROLE_ADOPTED)
        if role == ROLE_ADOPTED:
            raw = compute_critical_chain(self.schedule_repo, int(version))
        else:
            if plan_query_service is None:
                plan_query_service = self._get_plan_query_service()
            rows = plan_query_service.list_plan_detail_rows_all(version=int(version), role=role)
            raw = compute_critical_chain_from_rows([dict(row) for row in rows])
        computed = self._normalize_critical_chain_result(raw)
        computed["cache_hit"] = False

        if not self._critical_chain_cacheable(computed):
            return dict(computed)

        with self._CRITICAL_CHAIN_CACHE_LOCK:
            cached = self._CRITICAL_CHAIN_CACHE.get(key)
            if cached is not None:
                try:
                    self._CRITICAL_CHAIN_CACHE.move_to_end(key)
                except Exception:
                    pass
                out = dict(cached)
                out["cache_hit"] = True
                return out

            self._CRITICAL_CHAIN_CACHE[key] = computed
            while len(self._CRITICAL_CHAIN_CACHE) > int(self._CRITICAL_CHAIN_CACHE_MAX):
                try:
                    self._CRITICAL_CHAIN_CACHE.popitem(last=False)
                except Exception:
                    break
            return dict(computed)

    def _history_payload_for_gantt(self, *, version: int, include_history: bool) -> Optional[Dict[str, Any]]:
        if not include_history:
            return None
        hist = self.history_repo.get_by_version(version)
        return hist.to_dict() if hist else None

    @staticmethod
    def _collect_gantt_degradation_events(
        *,
        calendar_days_outcome: Any,
        tasks_outcome: Any,
        critical_chain: Dict[str, Any],
    ) -> DegradationCollector:
        collector = DegradationCollector()
        collector.extend(calendar_days_outcome.events)
        collector.extend(tasks_outcome.events)
        if critical_chain.get("available") is False:
            reason = str(critical_chain.get("reason") or "").strip() or "unknown"
            collector.add(
                DegradationEvent(
                    code="critical_chain_unavailable",
                    scope="scheduler.gantt",
                    field="critical_chain",
                    message=f"关键链不可用（reason={reason}）。",
                )
            )
        return collector

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
        plan_query_service=None,
    ) -> Dict[str, Any]:
        """返回甘特图数据（tasks + 元信息）。"""
        view = (view or "").strip() or "machine"
        if view not in ("machine", "operator"):
            raise ValidationError("视图不正确，请选择：设备 / 人员。", field="视图")

        resolution = self.resolve_version(version)
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
        )
        ver = require_selected_version(resolution)
        plan_query = self._get_plan_query_service(plan_query_service)
        plan_resolution_obj = resolve_plan(plan_query, ver, plan_role)
        plan_resolution = plan_resolution_obj.to_dict()
        wr, version_span, range_source = self.resolve_gantt_range_for_version(
            version=ver,
            plan_role=selected_plan_role(plan_resolution),
            plan_query_service=plan_query,
            week_start=week_start,
            offset_weeks=offset_weeks,
            start_date=start_date,
            end_date=end_date,
        )

        calendar_days_outcome = build_calendar_days(self.conn, wr=wr, logger=self.logger, op_logger=self.op_logger)
        rows = plan_query.list_plan_detail_rows_between(
            version=ver,
            role=selected_plan_role(plan_resolution),
            start_time=wr.start_str,
            end_time=wr.end_exclusive_str,
        )
        effective_role = selected_plan_role(plan_resolution)
        try:
            overdue_meta = build_overdue_meta_for_plan(
                version=ver,
                role=effective_role,
                list_plan_overdue_base_rows=plan_query.list_plan_overdue_base_rows,
                load_adopted_meta=self._overdue_batch_ids_from_history,
                log_degraded=self._log_overdue_marker_degraded,
            )
        except ValueError as exc:
            raise ValidationError(str(exc), field="plan_role") from exc
        overdue_set = set(overdue_meta.get("ids") or [])

        tasks_outcome = build_tasks(view=view, wr=wr, rows=rows, overdue_set=overdue_set)
        empty_reason = tasks_outcome.empty_reason or calendar_days_outcome.empty_reason

        critical_chain = self._get_critical_chain(ver, plan_resolution=plan_resolution, plan_query_service=plan_query)
        degradation_collector = self._collect_gantt_degradation_events(
            calendar_days_outcome=calendar_days_outcome,
            tasks_outcome=tasks_outcome,
            critical_chain=critical_chain,
        )
        hist_dict = self._history_payload_for_gantt(version=ver, include_history=include_history)

        data = build_gantt_contract(
            contract_version=self.CONTRACT_VERSION,
            view=view,
            version=ver,
            week_start=wr.week_start_date.isoformat(),
            week_end=wr.week_end_date.isoformat(),
            tasks=tasks_outcome.value,
            calendar_days=calendar_days_outcome.value,
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
        plan_query_service=None,
    ) -> Dict[str, Any]:
        """
        返回周计划行（用于页面预览与导出）。
        字段：日期/批次号/图号/工序/设备/人员/时段
        """
        wr = self.resolve_week_range(week_start=week_start, offset_weeks=offset_weeks, start_date=start_date, end_date=end_date)
        resolution = self.resolve_version(version)
        if resolution.status == "no_history":
            plan_resolution = default_plan_resolution_dict(plan_role)
            return build_empty_week_plan_payload(wr=wr, resolution=resolution, plan_resolution=plan_resolution)
        ver = require_selected_version(resolution)
        plan_query = self._get_plan_query_service(plan_query_service)
        plan_resolution_obj = resolve_plan(plan_query, ver, plan_role)
        plan_resolution = plan_resolution_obj.to_dict()

        rows = plan_query.list_plan_detail_rows_between(
            version=ver,
            role=selected_plan_role(plan_resolution),
            start_time=wr.start_str,
            end_time=wr.end_exclusive_str,
        )
        outcome = build_week_plan_rows(rows=rows, wr=wr)

        hist = self.history_repo.get_by_version(ver)
        data = {
            "version": ver,
            "requested_version": resolution.requested_version,
            "status": "ok",
            "has_history": True,
            "week_start": wr.week_start_date.isoformat(),
            "week_end": wr.week_end_date.isoformat(),
            "rows": outcome.value,
            "degraded": outcome.has_events,
            "degradation_events": degradation_events_to_dicts(outcome.events),
            "degradation_counters": outcome.counters,
            "empty_reason": outcome.empty_reason,
            "history": hist.to_dict() if hist else None,
        }
        attach_plan_metadata(data, plan_resolution)
        return data
