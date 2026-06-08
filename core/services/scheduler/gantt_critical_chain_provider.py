from __future__ import annotations

import sqlite3
import threading
from collections import OrderedDict
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Tuple,
)
from typing import (
    OrderedDict as OrderedDictType,
)

from core.models.schedule_plan_role import SOURCE_SCHEDULE

from .gantt_critical_chain import (
    _normalize_critical_chain_result,
    compute_critical_chain,
    compute_critical_chain_from_rows,
)
from .schedule_plan_query_service import ROLE_ADOPTED, SchedulePlanQueryService
from .schedule_result_view_context import default_plan_resolution_dict, selected_plan_role


class GanttCriticalChainProvider:
    """Loads and caches critical-chain results for adopted and candidate plans."""

    _CRITICAL_CHAIN_CACHE_MAX = 64
    _CRITICAL_CHAIN_CACHE: OrderedDictType[Tuple[Any, ...], Dict[str, Any]] = OrderedDict()
    _CRITICAL_CHAIN_CACHE_LOCK = threading.Lock()
    _CRITICAL_CHAIN_CACHE_EPOCH = 0

    def __init__(
        self,
        *,
        conn,
        schedule_repo,
        plan_query_service_factory: Optional[Callable[[], SchedulePlanQueryService]] = None,
        plan_query_service: Optional[SchedulePlanQueryService] = None,
        logger=None,
    ):
        self.conn = conn
        self.schedule_repo = schedule_repo
        self._plan_query_service_factory = plan_query_service_factory
        self._plan_query_service = plan_query_service
        self.logger = logger

    @classmethod
    def clear_cache(cls) -> None:
        with cls._CRITICAL_CHAIN_CACHE_LOCK:
            cls._CRITICAL_CHAIN_CACHE.clear()
            cls._CRITICAL_CHAIN_CACHE_EPOCH += 1

    def _get_plan_query_service(self, plan_query_service=None) -> SchedulePlanQueryService:
        if plan_query_service is not None:
            return plan_query_service
        if self._plan_query_service is not None:
            return self._plan_query_service
        if self._plan_query_service_factory is None:
            raise RuntimeError("GanttCriticalChainProvider 缺少 plan_query_service_factory")
        self._plan_query_service = self._plan_query_service_factory()
        return self._plan_query_service

    def _database_scope(self) -> str:
        scope = str(id(self.conn))
        for row in self._database_list_rows():
            name = self._database_row_value(row, key="name", index=1)
            if str(name) != "main":
                continue
            file_path = self._database_row_value(row, key="file", index=2)
            if file_path:
                scope = str(file_path)
            break
        return scope

    def _database_list_rows(self):
        try:
            return list(self.conn.execute("PRAGMA database_list").fetchall() or [])
        except (AttributeError, TypeError, RuntimeError, sqlite3.Error):
            return []

    @staticmethod
    def _database_row_value(row: Any, *, key: str, index: int):
        if isinstance(row, dict):
            return row.get(key)
        keys_method = getattr(row, "keys", None)
        keys = keys_method() if callable(keys_method) else ()
        if isinstance(keys, (list, tuple)) and key in keys:
            return row[key]
        if isinstance(row, (list, tuple)) and len(row) > index:
            return row[index]
        return None

    def _critical_chain_cache_key(self, version: int, *, plan_resolution: Dict[str, Any]) -> Tuple[Any, ...]:
        return (
            self._database_scope(),
            int(version),
            str(plan_resolution.get("selected_role") or ROLE_ADOPTED),
            str(plan_resolution.get("source_table") or "schedule"),
            int(plan_resolution.get("candidate_id") or 0),
            str(plan_resolution.get("scenario_id") or ""),
        )

    @staticmethod
    def _copy_critical_chain_result(result: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(result or {})
        out["ids"] = list(out.get("ids") or [])
        out["edges"] = [dict(edge) if isinstance(edge, dict) else edge for edge in list(out.get("edges") or [])]
        out["edge_type_stats"] = dict(out.get("edge_type_stats") or {})
        out["reason_code"] = str(out.get("reason_code") or "").strip()
        return out

    @staticmethod
    def _critical_chain_cacheable(result: Dict[str, Any]) -> bool:
        return bool(result.get("available", True))

    def get_critical_chain(
        self,
        version: int,
        *,
        plan_resolution: Optional[Dict[str, Any]] = None,
        plan_query_service=None,
    ) -> Dict[str, Any]:
        plan_resolution = plan_resolution or default_plan_resolution_dict(ROLE_ADOPTED)
        key = self._critical_chain_cache_key(version, plan_resolution=plan_resolution)
        with self._CRITICAL_CHAIN_CACHE_LOCK:
            cache_epoch = int(self._CRITICAL_CHAIN_CACHE_EPOCH)
            cached = self._CRITICAL_CHAIN_CACHE.get(key)
            if cached is not None:
                self._CRITICAL_CHAIN_CACHE.move_to_end(key)
                out = self._copy_critical_chain_result(cached)
                out["cache_hit"] = True
                return out

        role = selected_plan_role(plan_resolution)
        source_table = str(plan_resolution.get("source_table") or "schedule")
        if role == ROLE_ADOPTED and source_table == SOURCE_SCHEDULE:
            raw = compute_critical_chain(self.schedule_repo, int(version))
        else:
            try:
                plan_query = self._get_plan_query_service(plan_query_service)
                query_kwargs = {
                    "version": int(version),
                    "source_table": source_table,
                    "candidate_id": plan_resolution.get("candidate_id"),
                }
                if plan_resolution.get("scenario_id"):
                    query_kwargs["scenario_id"] = plan_resolution.get("scenario_id")
                rows = plan_query.list_plan_detail_rows_all_for_resolution(**query_kwargs)
            except (RuntimeError, ValueError, TypeError, KeyError, IndexError, sqlite3.Error):
                raw = {"available": False, "reason": "rows_load_exception", "reason_code": "rows_load_exception"}
            else:
                raw = compute_critical_chain_from_rows([dict(row) for row in rows])
        computed = _normalize_critical_chain_result(raw)
        computed["cache_hit"] = False

        if not self._critical_chain_cacheable(computed):
            return self._copy_critical_chain_result(computed)

        with self._CRITICAL_CHAIN_CACHE_LOCK:
            if cache_epoch != int(self._CRITICAL_CHAIN_CACHE_EPOCH):
                return self._copy_critical_chain_result(computed)
            cached = self._CRITICAL_CHAIN_CACHE.get(key)
            if cached is not None:
                self._CRITICAL_CHAIN_CACHE.move_to_end(key)
                out = self._copy_critical_chain_result(cached)
                out["cache_hit"] = True
                return out

            self._CRITICAL_CHAIN_CACHE[key] = self._copy_critical_chain_result(computed)
            while len(self._CRITICAL_CHAIN_CACHE) > int(self._CRITICAL_CHAIN_CACHE_MAX) and self._CRITICAL_CHAIN_CACHE:
                self._CRITICAL_CHAIN_CACHE.popitem(last=False)
            return self._copy_critical_chain_result(computed)
