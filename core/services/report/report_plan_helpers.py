from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, cast

from core.infrastructure.errors import ValidationError
from core.services.scheduler.schedule_plan_query_service import SchedulePlanResolution, plan_role_label

from . import calculations


class _ReportPlanHost(Protocol):
    history_repo: Any
    plan_query_service: Any


class ReportPlanMixin:
    # -------------------------
    # Version helpers
    # -------------------------
    def list_versions(self, limit: int = 30) -> List[Dict[str, Any]]:
        host = cast(_ReportPlanHost, self)
        return list(host.history_repo.list_versions(limit=int(limit)))

    def latest_version(self) -> int:
        host = cast(_ReportPlanHost, self)
        return int(host.history_repo.get_latest_version() or 0)

    def _resolve_plan(
        self,
        version: int,
        plan_role: Optional[str],
        scenario_id: Optional[str] = None,
    ) -> SchedulePlanResolution:
        host = cast(_ReportPlanHost, self)
        try:
            return host.plan_query_service.resolve_plan_view(int(version), plan_role, scenario_id)
        except ValueError as exc:
            raise ValidationError(str(exc), field="scenario_id" if scenario_id else "plan_role") from exc

    def resolve_plan_context(
        self,
        version: int,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._resolve_plan(version, plan_role, scenario_id).to_dict()

    def _get_plan_time_span(self, version: int, plan_role: Optional[str], scenario_id: Optional[str] = None):
        host = cast(_ReportPlanHost, self)
        try:
            return host.plan_query_service.get_plan_time_span_for_view(int(version), plan_role, scenario_id)
        except ValueError as exc:
            raise ValidationError(str(exc), field="scenario_id" if scenario_id else "plan_role") from exc

    def _list_plan_rows_between(
        self,
        *,
        version: int,
        plan_role: Optional[str],
        scenario_id: Optional[str] = None,
        start_time: str,
        end_time: str,
    ):
        host = cast(_ReportPlanHost, self)
        try:
            return host.plan_query_service.list_plan_detail_rows_between_for_view(
                version=int(version),
                role=plan_role,
                scenario_id=scenario_id,
                start_time=start_time,
                end_time=end_time,
            )
        except ValueError as exc:
            raise ValidationError(str(exc), field="scenario_id" if scenario_id else "plan_role") from exc

    def _list_plan_rows_all(
        self,
        *,
        version: int,
        plan_role: Optional[str],
        scenario_id: Optional[str] = None,
    ):
        host = cast(_ReportPlanHost, self)
        try:
            resolution = self._resolve_plan(version, plan_role, scenario_id)
            return host.plan_query_service.list_plan_detail_rows_all_for_resolution(
                version=int(version),
                source_table=resolution.source_table,
                candidate_id=resolution.candidate_id,
                scenario_id=resolution.scenario_id,
            )
        except ValueError as exc:
            raise ValidationError(str(exc), field="scenario_id" if scenario_id else "plan_role") from exc

    def _plan_meta(self, resolution: SchedulePlanResolution) -> Dict[str, Any]:
        return {
            "plan_role": resolution.selected_role,
            "plan_role_label": plan_role_label(resolution.selected_role),
            "requested_plan_role": resolution.requested_role,
            "requested_plan_role_label": plan_role_label(resolution.requested_role),
            "scenario_id": resolution.scenario_id,
            "scenario_name": resolution.scenario_name,
            "is_scenario_preview": bool(resolution.is_scenario_preview),
            "plan_resolution": resolution.to_dict(),
        }

    def _filename_plan_label(self, resolution: SchedulePlanResolution) -> str:
        label = resolution.scenario_display_name or plan_role_label(resolution.selected_role)
        for old, new in (("/", "-"), ("\\", "-"), (":", "-"), ("*", ""), ("?", ""), ('"', ""), ("<", ""), (">", ""), ("|", "-")):
            label = label.replace(old, new)
        return label.strip() or plan_role_label(resolution.selected_role)

    def _public_plan_label(self, resolution: SchedulePlanResolution) -> str:
        if resolution.is_scenario_preview:
            return resolution.scenario_display_name
        identity = resolution.plan_identity
        if identity is not None:
            return identity.user_label or identity.label or plan_role_label(resolution.selected_role)
        return plan_role_label(resolution.selected_role)

    def _scenario_export_summary_rows(
        self,
        resolution: SchedulePlanResolution,
        *,
        date_range: Optional[str] = None,
    ) -> List[List[Any]]:
        if not resolution.is_scenario_preview:
            return []
        rows: List[List[Any]] = [
            ["导出类型", "模拟方案预览"],
            ["提示", "这是模拟方案预览，正式计划还没有改变。"],
            ["模拟方案", resolution.scenario_display_name],
            ["预览依据版本", f"v{int(resolution.version)}"],
            ["预览依据方案", plan_role_label(resolution.selected_role)],
        ]
        if date_range:
            rows.append(["查询日期", date_range])
        rows.append(["导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        return rows

    def version_date_range(
        self,
        version: int,
        plan_role: Optional[str] = None,
        scenario_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        返回指定版本的排程日期范围（用于报表默认筛选）。
        """
        v = int(version or 0)
        out: Dict[str, Any] = {
            "version": v,
            "start_time": None,
            "end_time": None,
            "start_date": None,
            "end_date": None,
            "has_data": False,
            "plan_role": "adopted",
            "plan_role_label": plan_role_label("adopted"),
            "plan_resolution": None,
        }
        if v <= 0:
            return out

        resolution = self._resolve_plan(v, plan_role, scenario_id)
        out.update(self._plan_meta(resolution))

        span = self._get_plan_time_span(v, plan_role, scenario_id)
        if not span:
            return out

        start_time = span.get("start_time")
        end_time = span.get("end_time")
        start_dt = calculations.parse_dt(start_time)
        end_dt = calculations.parse_dt(end_time)
        if not start_dt or not end_dt:
            return out

        out["start_time"] = str(start_time)
        out["end_time"] = str(end_time)
        out["start_date"] = start_dt.date().isoformat()
        out["end_date"] = end_dt.date().isoformat()
        out["has_data"] = True
        return out
