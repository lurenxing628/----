from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.infrastructure.errors import ValidationError
from core.services.equipment.machine_service import MachineService
from core.services.personnel import ResourceTeamService
from core.services.personnel.operator_service import OperatorService
from data.repositories import ScheduleRepository

from .resource_dispatch_excel import build_resource_dispatch_workbook
from .resource_dispatch_range import resolve_dispatch_range
from .resource_dispatch_support import (
    build_dispatch_filters,
    build_empty_dispatch_message,
    build_single_scope_payload,
    build_team_scope_payload,
    empty_dispatch_payload,
    extract_overdue_batch_ids,
)
from .schedule_history_query_service import ScheduleHistoryQueryService


class ResourceDispatchService:
    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.schedule_repo = ScheduleRepository(conn, logger=logger)
        self.history_service = ScheduleHistoryQueryService(conn, logger=logger, op_logger=op_logger)
        self.operator_service = OperatorService(conn, logger=logger, op_logger=op_logger)
        self.machine_service = MachineService(conn, logger=logger, op_logger=op_logger)
        self.team_service = ResourceTeamService(conn, logger=logger, op_logger=op_logger)

    @staticmethod
    def _text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _normalize_scope_type(self, value: Any) -> str:
        scope_type = str(value or "operator").strip().lower() or "operator"
        if scope_type not in {"operator", "machine", "team"}:
            raise ValidationError("视角类型不正确，请选择：人员 / 设备 / 班组。", field="视角类型")
        return scope_type

    def _normalize_team_axis(self, value: Any) -> str:
        team_axis = str(value or "operator").strip().lower() or "operator"
        if team_axis not in {"operator", "machine"}:
            raise ValidationError("班组轴类型不正确，请选择：人员轴 / 设备轴。", field="班组轴类型")
        return team_axis

    def _resolve_scope_id(
        self,
        *,
        scope_type: str,
        scope_id: Any = None,
        operator_id: Any = None,
        machine_id: Any = None,
        team_id: Any = None,
    ) -> Optional[str]:
        explicit_scope_id = self._text(scope_id)
        if explicit_scope_id:
            return explicit_scope_id
        if scope_type == "operator":
            return self._text(operator_id)
        if scope_type == "machine":
            return self._text(machine_id)
        return self._text(team_id)

    def _period_preset_label(self, value: str) -> str:
        return {"week": "按周", "month": "按月", "custom": "自定义"}.get(value, value)

    def _scope_type_label(self, value: str) -> str:
        return {"operator": "人员", "machine": "设备", "team": "班组"}.get(value, value)

    def _team_axis_label(self, value: str) -> str:
        return "人员轴" if value == "operator" else "设备轴"

    def _latest_version(self) -> int:
        return int(self.history_service.get_latest_version() or 0)

    def _list_versions(self, limit: int = 30) -> List[Dict[str, Any]]:
        return list(self.history_service.list_versions(limit=limit) or [])

    def _normalize_version(self, value: Any, *, latest_version: int) -> int:
        if value in (None, ""):
            return int(latest_version or 1)
        try:
            version = int(value)
        except Exception as exc:
            raise ValidationError("排产版本必须是整数", field="version") from exc
        if version <= 0:
            raise ValidationError("排产版本必须大于 0", field="version")
        return version

    def _scope_record(self, scope_type: str, scope_id: str):
        if scope_type == "operator":
            return self.operator_service.get_optional(scope_id)
        if scope_type == "machine":
            return self.machine_service.get_optional(scope_id)
        return self.team_service.get_optional(scope_id)

    def _scope_name(self, scope_type: str, scope_id: str) -> str:
        record = self._scope_record(scope_type, scope_id)
        if not record:
            label = self._scope_type_label(scope_type)
            raise ValidationError(f"所选{label}不存在：{scope_id}", field="scope_id")
        return str(getattr(record, "name", "") or "").strip()

    def _build_scope_options(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        operator_options = [
            {
                "id": item.operator_id,
                "name": item.name,
                "status": item.status,
                "team_id": item.team_id,
                "label": f"{item.operator_id} {item.name}".strip(),
            }
            for item in self.operator_service.list()
        ]
        machine_options = [
            {
                "id": item.machine_id,
                "name": item.name,
                "status": item.status,
                "team_id": item.team_id,
                "label": f"{item.machine_id} {item.name}".strip(),
            }
            for item in self.machine_service.list()
        ]
        team_options = [
            {
                "id": item.team_id,
                "name": item.name,
                "status": item.status,
                "label": f"{item.team_id} {item.name}".strip(),
            }
            for item in self.team_service.list(status=None)
        ]
        return operator_options, machine_options, team_options

    def _load_overdue_set(self, version: int) -> Set[str]:
        hist = self.history_service.get_by_version(int(version))
        if not hist:
            return set()
        return extract_overdue_batch_ids(hist.result_summary)

    def build_page_context(
        self,
        *,
        scope_type: Any = None,
        scope_id: Any = None,
        operator_id: Any = None,
        machine_id: Any = None,
        team_id: Any = None,
        team_axis: Any = None,
        period_preset: Any = None,
        query_date: Any = None,
        start_date: Any = None,
        end_date: Any = None,
        version: Any = None,
    ) -> Dict[str, Any]:
        normalized_scope_type = self._normalize_scope_type(scope_type)
        normalized_team_axis = self._normalize_team_axis(team_axis)
        versions = self._list_versions(limit=50)
        latest_version = int(versions[0].get("version") or 0) if versions else self._latest_version()
        dr = resolve_dispatch_range(
            period_preset=period_preset or "week",
            query_date=query_date,
            start_date=start_date,
            end_date=end_date,
        )
        selected_scope_id = self._resolve_scope_id(
            scope_type=normalized_scope_type,
            scope_id=scope_id,
            operator_id=operator_id,
            machine_id=machine_id,
            team_id=team_id,
        )
        selected_scope_name = self._scope_name(normalized_scope_type, selected_scope_id) if selected_scope_id else ""
        operator_options, machine_options, team_options = self._build_scope_options()
        selected_version = self._normalize_version(version, latest_version=latest_version)
        return {
            "filters": {
                "scope_type": normalized_scope_type,
                "scope_type_label": self._scope_type_label(normalized_scope_type),
                "scope_id": selected_scope_id or "",
                "scope_name": selected_scope_name,
                "scope_label": f"{selected_scope_id or ''} {selected_scope_name}".strip(),
                "operator_id": selected_scope_id if normalized_scope_type == "operator" else self._text(operator_id) or "",
                "machine_id": selected_scope_id if normalized_scope_type == "machine" else self._text(machine_id) or "",
                "team_id": selected_scope_id if normalized_scope_type == "team" else self._text(team_id) or "",
                "team_axis": normalized_team_axis,
                "team_axis_label": self._team_axis_label(normalized_team_axis),
                "period_preset": dr.period_preset,
                "period_preset_label": self._period_preset_label(dr.period_preset),
                "query_date": dr.query_date.isoformat(),
                "start_date": dr.start_date.isoformat(),
                "end_date": dr.end_date.isoformat(),
                "version": selected_version,
            },
            "versions": versions,
            "has_history": bool(versions),
            "operator_options": operator_options,
            "machine_options": machine_options,
            "team_options": team_options,
            "can_query": bool(selected_scope_id),
        }

    def get_dispatch_payload(
        self,
        *,
        scope_type: Any = None,
        scope_id: Any = None,
        operator_id: Any = None,
        machine_id: Any = None,
        team_id: Any = None,
        team_axis: Any = None,
        period_preset: Any = None,
        query_date: Any = None,
        start_date: Any = None,
        end_date: Any = None,
        version: Any = None,
    ) -> Dict[str, Any]:
        normalized_scope_type = self._normalize_scope_type(scope_type)
        normalized_team_axis = self._normalize_team_axis(team_axis)
        latest_version = self._latest_version()
        selected_version = self._normalize_version(version, latest_version=latest_version)
        if latest_version <= 0:
            return empty_dispatch_payload(
                scope_type=normalized_scope_type,
                scope_type_label=self._scope_type_label(normalized_scope_type),
                team_axis=normalized_team_axis,
                team_axis_label=self._team_axis_label(normalized_team_axis),
                version=selected_version,
            )

        selected_scope_id = self._resolve_scope_id(
            scope_type=normalized_scope_type,
            scope_id=scope_id,
            operator_id=operator_id,
            machine_id=machine_id,
            team_id=team_id,
        )
        if not selected_scope_id:
            raise ValidationError("请选择查询对象", field="scope_id")
        selected_scope_name = self._scope_name(normalized_scope_type, selected_scope_id)
        dr = resolve_dispatch_range(
            period_preset=period_preset or "week",
            query_date=query_date,
            start_date=start_date,
            end_date=end_date,
        )
        overdue_set = self._load_overdue_set(selected_version)
        rows = self.schedule_repo.list_dispatch_rows_with_resource_context(
            start_time=dr.start_time,
            end_time=dr.end_time,
            version=selected_version,
            scope_type=normalized_scope_type,
            scope_id=selected_scope_id,
        )

        if normalized_scope_type == "team":
            payload = build_team_scope_payload(
                selected_scope_id=selected_scope_id,
                selected_scope_name=selected_scope_name,
                normalized_team_axis=normalized_team_axis,
                dr=dr,
                rows=rows,
                overdue_set=overdue_set,
            )
        else:
            payload = build_single_scope_payload(
                normalized_scope_type=normalized_scope_type,
                selected_scope_id=selected_scope_id,
                selected_scope_name=selected_scope_name,
                dr=dr,
                rows=rows,
                overdue_set=overdue_set,
            )
        payload["filters"] = build_dispatch_filters(
            normalized_scope_type=normalized_scope_type,
            scope_type_label=self._scope_type_label(normalized_scope_type),
            selected_scope_id=selected_scope_id,
            selected_scope_name=selected_scope_name,
            normalized_team_axis=normalized_team_axis,
            team_axis_label=self._team_axis_label(normalized_team_axis),
            dr=dr,
            selected_version=selected_version,
        )
        payload["has_history"] = True
        payload["empty_message"] = build_empty_dispatch_message(
            normalized_scope_type=normalized_scope_type,
            dr=dr,
            detail_rows=payload["detail_rows"],
            operator_rows=payload["operator_rows"],
            machine_rows=payload["machine_rows"],
        )
        return payload

    def build_export(self, **kwargs) -> Tuple[Any, str, Dict[str, Any]]:
        payload = self.get_dispatch_payload(**kwargs)
        buf = build_resource_dispatch_workbook(payload)
        filters = payload.get("filters") or {}
        filename = "资源排班"
        if filters.get("scope_type_label"):
            filename += f"_{filters['scope_type_label']}"
        if filters.get("scope_id"):
            filename += f"_{filters['scope_id']}"
        if filters.get("scope_type") == "team" and filters.get("team_axis"):
            filename += f"_{filters['team_axis']}"
        if filters.get("start_date") and filters.get("end_date"):
            filename += f"_{filters['start_date']}_{filters['end_date']}"
        if filters.get("version"):
            filename += f"_v{filters['version']}"
        return buf, f"{filename}.xlsx", payload
