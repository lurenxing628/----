from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Dict, Optional, Sequence

from core.infrastructure.errors import ValidationError
from core.services.common.degradation import DegradationCollector, DegradationEvent, degradation_events_to_dicts
from data.repositories import ScheduleHistoryRepository, ScheduleRepository

from .gantt_contract import build_gantt_contract
from .gantt_critical_chain import compute_critical_chain
from .gantt_range import WeekRange, resolve_week_range
from .gantt_tasks import build_calendar_days, build_tasks
from .gantt_week_plan import build_week_plan_rows
from .resource_dispatch_support import extract_overdue_batch_ids_with_meta


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

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.schedule_repo = ScheduleRepository(conn, logger=logger)
        self.history_repo = ScheduleHistoryRepository(conn, logger=logger)

    def get_latest_version_or_1(self) -> int:
        v = int(self.history_repo.get_latest_version() or 0)
        return v if v > 0 else 1

    def resolve_week_range(
        self,
        week_start: Optional[str] = None,
        offset_weeks: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> WeekRange:
        return resolve_week_range(week_start=week_start, offset_weeks=offset_weeks, start_date=start_date, end_date=end_date)

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

    def _critical_chain_cache_key(self, version: int) -> tuple:
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
        return (scope, int(version))

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

    def _get_critical_chain(self, version: int) -> Dict[str, Any]:
        key = self._critical_chain_cache_key(version)
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

        computed = self._normalize_critical_chain_result(compute_critical_chain(self.schedule_repo, int(version)))
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
    ) -> Dict[str, Any]:
        """
        返回甘特图数据（tasks + 元信息）。
        view：machine / operator
        """
        view = (view or "").strip() or "machine"
        if view not in ("machine", "operator"):
            raise ValidationError("视图不正确，请选择：设备 / 人员。", field="视图")

        wr = self.resolve_week_range(week_start=week_start, offset_weeks=offset_weeks, start_date=start_date, end_date=end_date)
        ver = int(version) if version is not None and str(version).strip() != "" else self.get_latest_version_or_1()

        calendar_days_outcome = build_calendar_days(self.conn, wr=wr, logger=self.logger, op_logger=self.op_logger)
        rows = self.schedule_repo.list_overlapping_with_details(wr.start_str, wr.end_exclusive_str, ver)
        overdue_meta = self._overdue_batch_ids_from_history(ver)
        overdue_set = set(overdue_meta.get("ids") or [])

        hist_dict = None
        if include_history:
            hist = self.history_repo.get_by_version(ver)
            hist_dict = hist.to_dict() if hist else None

        tasks_outcome = build_tasks(view=view, wr=wr, rows=rows, overdue_set=overdue_set)
        degradation_collector = DegradationCollector()
        degradation_collector.extend(calendar_days_outcome.events)
        degradation_collector.extend(tasks_outcome.events)
        empty_reason = tasks_outcome.empty_reason or calendar_days_outcome.empty_reason

        critical_chain = self._get_critical_chain(ver)
        if critical_chain.get("available") is False:
            reason = str(critical_chain.get("reason") or "").strip() or "unknown"
            degradation_collector.add(
                DegradationEvent(
                    code="critical_chain_unavailable",
                    scope="scheduler.gantt",
                    field="critical_chain",
                    message=f"关键链不可用（reason={reason}）。",
                )
            )

        return build_gantt_contract(
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

    def get_week_plan_rows(
        self,
        *,
        week_start: Optional[str] = None,
        offset_weeks: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        返回周计划行（用于页面预览与导出）。
        字段：日期/批次号/图号/工序/设备/人员/时段
        """
        wr = self.resolve_week_range(week_start=week_start, offset_weeks=offset_weeks, start_date=start_date, end_date=end_date)
        ver = int(version) if version is not None and str(version).strip() != "" else self.get_latest_version_or_1()

        rows = self.schedule_repo.list_overlapping_with_details(wr.start_str, wr.end_exclusive_str, ver)
        outcome = build_week_plan_rows(rows=rows, wr=wr)

        hist = self.history_repo.get_by_version(ver)
        return {
            "version": ver,
            "week_start": wr.week_start_date.isoformat(),
            "week_end": wr.week_end_date.isoformat(),
            "rows": outcome.value,
            "degraded": outcome.has_events,
            "degradation_events": degradation_events_to_dicts(outcome.events),
            "degradation_counters": outcome.counters,
            "empty_reason": outcome.empty_reason,
            "history": hist.to_dict() if hist else None,
        }

