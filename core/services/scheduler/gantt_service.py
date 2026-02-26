from __future__ import annotations

import json
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional, Sequence

from core.infrastructure.errors import ValidationError
from data.repositories import ScheduleHistoryRepository, ScheduleRepository

from .gantt_contract import build_gantt_contract
from .gantt_critical_chain import compute_critical_chain
from .gantt_range import WeekRange, resolve_week_range
from .gantt_tasks import build_calendar_days, build_tasks
from .gantt_week_plan import build_week_plan_rows


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
    _CRITICAL_CHAIN_CACHE: "OrderedDict[tuple, Dict[str, Any]]" = OrderedDict()
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

    def _overdue_batch_ids_from_history(self, version: int) -> Sequence[str]:
        hist = self.history_repo.get_by_version(int(version))
        if not hist or not hist.result_summary:
            return []
        try:
            obj = json.loads(hist.result_summary or "{}")
        except Exception:
            return []

        overdue = obj.get("overdue_batches")
        # 兼容两种结构：list 或 {count, items}
        if isinstance(overdue, list):
            return [str(x.get("batch_id")) for x in overdue if isinstance(x, dict) and x.get("batch_id")]
        if isinstance(overdue, dict):
            items = overdue.get("items") or []
            if isinstance(items, list):
                return [str(x.get("batch_id")) for x in items if isinstance(x, dict) and x.get("batch_id")]
        return []

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

        computed = compute_critical_chain(self.schedule_repo, int(version))
        if not isinstance(computed, dict):
            computed = {
                "ids": [],
                "edges": [],
                "makespan_end": None,
                "edge_type_stats": {"process": 0, "machine": 0, "operator": 0, "unknown": 0},
                "edge_count": 0,
            }
        computed["cache_hit"] = False

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
            raise ValidationError("view 不合法（允许：machine/operator）", field="view")

        wr = self.resolve_week_range(week_start=week_start, offset_weeks=offset_weeks, start_date=start_date, end_date=end_date)
        ver = int(version) if version is not None and str(version).strip() != "" else self.get_latest_version_or_1()

        calendar_days = build_calendar_days(self.conn, wr=wr, logger=self.logger, op_logger=self.op_logger)
        rows = self.schedule_repo.list_overlapping_with_details(wr.start_str, wr.end_exclusive_str, ver)
        overdue_set = set(self._overdue_batch_ids_from_history(ver))

        tasks = build_tasks(view=view, wr=wr, rows=rows, overdue_set=overdue_set)

        hist_dict = None
        if include_history:
            hist = self.history_repo.get_by_version(ver)
            hist_dict = hist.to_dict() if hist else None

        critical_chain = self._get_critical_chain(ver)

        return build_gantt_contract(
            contract_version=self.CONTRACT_VERSION,
            view=view,
            version=ver,
            week_start=wr.week_start_date.isoformat(),
            week_end=wr.week_end_date.isoformat(),
            tasks=tasks,
            calendar_days=calendar_days,
            critical_chain=critical_chain,
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
        out = build_week_plan_rows(rows=rows, wr=wr)

        hist = self.history_repo.get_by_version(ver)
        return {
            "version": ver,
            "week_start": wr.week_start_date.isoformat(),
            "week_end": wr.week_end_date.isoformat(),
            "rows": out,
            "history": hist.to_dict() if hist else None,
        }

