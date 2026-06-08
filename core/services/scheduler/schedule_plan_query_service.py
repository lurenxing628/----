from __future__ import annotations

import sqlite3
from dataclasses import replace
from typing import Any, Dict, List, Optional

from core.infrastructure.errors import ValidationError
from core.models.schedule_plan_resolution import SchedulePlanResolution, SchedulePlanRoleOption
from core.models.schedule_plan_role import (
    ROLE_ADOPTED,
    ROLE_BASELINE_BEST,
    ROLE_CRITICAL_BEST,
    SOURCE_ADJUSTMENT_SCENARIO_ROWS,
    SOURCE_CANDIDATE_ROWS,
    SOURCE_SCHEDULE,
    VALID_PLAN_ROLES,
    _normalize_role,
    is_comparison_plan,
    plan_candidate_label,
    plan_role_label,
)
from core.models.schedule_resource_filter import normalize_overdue_resource_filter
from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository
from data.repositories.schedule_rows import ScheduleDetailRow, ScheduleDispatchRow, ScheduleTimeSpanRow

from .schedule_plan_identity_builder import build_plan_identity, latest_official_version


def _resolution_status(role: Optional[str], *, source_table: Optional[str] = None) -> str:
    if is_comparison_plan(role=role, source_table=source_table):
        return "resolved_comparison"
    return "resolved_adopted"


def _default_adopted_option() -> SchedulePlanRoleOption:
    return SchedulePlanRoleOption(
        role=ROLE_ADOPTED,
        source_table=SOURCE_SCHEDULE,
        candidate_id=None,
        candidate_key=None,
        candidate_label=plan_role_label(ROLE_ADOPTED),
        candidate_kind=None,
        candidate_status=None,
        detail_saved=None,
    )


class SchedulePlanQueryService:
    """统一解析 adopted / 代表方案，并按同一字段形状读取明细。"""

    def __init__(
        self,
        conn: sqlite3.Connection,
        logger=None,
        repo: Optional[SchedulePlanQueryRepository] = None,
    ):
        self.repo = repo if repo is not None else SchedulePlanQueryRepository(conn, logger=logger)

    def list_plan_roles(self, version: int) -> List[SchedulePlanRoleOption]:
        rows = self.repo.list_plan_role_options(int(version))
        options = [self._role_option_from_row(row) for row in rows]
        if not options:
            return [_default_adopted_option()]
        self._validate_plan_role_options_integrity(int(version), options)
        return options

    def _option_for_resolution(self, resolution: SchedulePlanResolution) -> Optional[SchedulePlanRoleOption]:
        for option in resolution.available_roles:
            if option.role == resolution.selected_role:
                return option
        return None

    def _with_plan_identity(self, resolution: SchedulePlanResolution) -> SchedulePlanResolution:
        history_row = self.repo.get_history_identity_row(int(resolution.version)) or {}
        source_row = self.repo.get_first_plan_identity_row(
            version=int(resolution.version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
            scenario_id=resolution.scenario_id,
        ) or {}
        option = self._option_for_resolution(resolution)
        identity = build_plan_identity(
            version=int(resolution.version),
            requested_role=resolution.requested_role,
            effective_role=resolution.selected_role,
            status=resolution.status,
            source_table=resolution.source_table,
            source_row_id=source_row.get("source_row_id"),
            candidate_id=resolution.candidate_id,
            candidate_key=resolution.candidate_key,
            scenario_id=resolution.scenario_id,
            scenario_display_name=resolution.scenario_display_name,
            schedule_result_status=history_row.get("result_status"),
            result_summary=history_row.get("result_summary"),
            latest_official_version=latest_official_version(self.repo.list_history_identity_rows()),
            schedule_lock_status=source_row.get("lock_status"),
            detail_saved=getattr(option, "detail_saved", None),
        )
        return replace(resolution, plan_identity=identity)

    def resolve_plan(self, version: int, role: Optional[str]) -> SchedulePlanResolution:
        requested_role = _normalize_role(role)
        if requested_role not in VALID_PLAN_ROLES:
            raise ValueError(f"未知的排产方案角色：{requested_role}")

        available_roles = self.list_plan_roles(int(version))
        roles_by_name = {option.role: option for option in available_roles}
        if requested_role in roles_by_name:
            option = roles_by_name[requested_role]
            self._validate_resolution_option(int(version), option)
            return self._with_plan_identity(SchedulePlanResolution(
                version=int(version),
                requested_role=requested_role,
                selected_role=option.role,
                source_table=option.source_table,
                candidate_id=option.candidate_id,
                candidate_key=option.candidate_key,
                status=_resolution_status(option.role, source_table=option.source_table),
                message="",
                available_roles=available_roles,
            ))

        adopted = roles_by_name.get(ROLE_ADOPTED) or _default_adopted_option()
        self._validate_resolution_option(int(version), adopted)
        return self._with_plan_identity(SchedulePlanResolution(
            version=int(version),
            requested_role=requested_role,
            selected_role=ROLE_ADOPTED,
            source_table=adopted.source_table,
            candidate_id=adopted.candidate_id,
            candidate_key=adopted.candidate_key,
            status="fallback_to_adopted",
            message=f"你原本选择的是“{plan_role_label(requested_role)}”，但当前版本没有保存这套方案明细，已显示正式采用方案。",
            available_roles=available_roles,
        ))

    def resolve_existing_plan(self, version: int, role: str) -> SchedulePlanResolution:
        requested_role = str(role or "").strip()
        if not requested_role:
            raise ValueError("请选择要查看的方案。")
        if requested_role not in VALID_PLAN_ROLES:
            raise ValueError(f"未知的排产方案角色：{requested_role}")

        available_roles = self.list_plan_roles(int(version))
        roles_by_name = {option.role: option for option in available_roles}
        option = roles_by_name.get(requested_role)
        if option is None:
            raise ValueError("所选方案不存在。")

        try:
            self._validate_resolution_option(int(version), option)
        except ValueError as exc:
            raise ValueError("所选方案没有可查看的明细。") from exc
        if self.repo.get_plan_time_span(
            version=int(version),
            source_table=option.source_table,
            candidate_id=option.candidate_id,
        ) is None:
            raise ValueError("所选方案没有可查看的明细。")
        return self._with_plan_identity(SchedulePlanResolution(
            version=int(version),
            requested_role=requested_role,
            selected_role=option.role,
            source_table=option.source_table,
            candidate_id=option.candidate_id,
            candidate_key=option.candidate_key,
            status=_resolution_status(option.role, source_table=option.source_table),
            message="",
            available_roles=available_roles,
        ))

    def resolve_plan_view(
        self,
        version: int,
        role: Optional[str],
        scenario_id: Optional[str] = None,
    ) -> SchedulePlanResolution:
        scenario_key = str(scenario_id or "").strip()
        if not scenario_key:
            return self.resolve_plan(version, role)
        return self._resolve_scenario_plan(version=int(version), role=role, scenario_id=scenario_key)

    def get_plan_time_span(self, version: int, role: Optional[str]) -> Optional[ScheduleTimeSpanRow]:
        resolution = self.resolve_plan(version, role)
        return self.get_plan_time_span_for_resolution(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
            scenario_id=resolution.scenario_id,
        )

    def get_plan_time_span_for_view(
        self,
        version: int,
        role: Optional[str],
        scenario_id: Optional[str] = None,
    ) -> Optional[ScheduleTimeSpanRow]:
        resolution = self.resolve_plan_view(version, role, scenario_id)
        return self.get_plan_time_span_for_resolution(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
            scenario_id=resolution.scenario_id,
        )

    def get_plan_time_span_for_resolution(
        self,
        *,
        version: int,
        source_table: str,
        candidate_id: Optional[int],
        scenario_id: Optional[str] = None,
    ) -> Optional[ScheduleTimeSpanRow]:
        return self.repo.get_plan_time_span(
            version=int(version),
            source_table=source_table,
            candidate_id=candidate_id,
            scenario_id=scenario_id,
        )

    def list_plan_detail_rows_between(
        self,
        *,
        version: int,
        role: Optional[str],
        start_time: str,
        end_time: str,
    ) -> List[ScheduleDetailRow]:
        resolution = self.resolve_plan(version, role)
        return self.list_plan_detail_rows_between_for_resolution(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
            scenario_id=resolution.scenario_id,
            start_time=start_time,
            end_time=end_time,
        )

    def list_plan_detail_rows_between_for_view(
        self,
        *,
        version: int,
        role: Optional[str],
        scenario_id: Optional[str] = None,
        start_time: str,
        end_time: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> List[ScheduleDetailRow]:
        resolution = self.resolve_plan_view(version, role, scenario_id)
        return self.list_plan_detail_rows_between_for_resolution(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
            scenario_id=resolution.scenario_id,
            start_time=start_time,
            end_time=end_time,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=batch_id,
        )

    def list_plan_detail_rows_between_for_resolution(
        self,
        *,
        version: int,
        source_table: str,
        candidate_id: Optional[int],
        scenario_id: Optional[str] = None,
        start_time: str,
        end_time: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> List[ScheduleDetailRow]:
        return self.repo.list_detail_rows_between(
            version=int(version),
            source_table=source_table,
            candidate_id=candidate_id,
            scenario_id=scenario_id,
            start_time=start_time,
            end_time=end_time,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=batch_id,
        )

    def list_plan_detail_rows_all(
        self,
        *,
        version: int,
        role: Optional[str],
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> List[ScheduleDetailRow]:
        resolution = self.resolve_plan(version, role)
        return self.list_plan_detail_rows_all_for_resolution(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
            scenario_id=resolution.scenario_id,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=batch_id,
        )

    def list_plan_detail_rows_all_for_resolution(
        self,
        *,
        version: int,
        source_table: str,
        candidate_id: Optional[int],
        scenario_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> List[ScheduleDetailRow]:
        return self.repo.list_detail_rows_all(
            version=int(version),
            source_table=source_table,
            candidate_id=candidate_id,
            scenario_id=scenario_id,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=batch_id,
        )

    def list_plan_overdue_base_rows(self, *, version: int, role: Optional[str]) -> List[Dict[str, Any]]:
        resolution = self.resolve_plan(version, role)
        return self.list_plan_overdue_base_rows_for_resolution(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
            scenario_id=resolution.scenario_id,
        )

    def list_plan_overdue_base_rows_for_resolution(
        self,
        *,
        version: int,
        source_table: str,
        candidate_id: Optional[int],
        scenario_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        resource_filter = normalize_overdue_resource_filter(resource_type, resource_id)
        return self.repo.list_overdue_base_rows(
            version=int(version),
            source_table=source_table,
            candidate_id=candidate_id,
            scenario_id=scenario_id,
            resource_type=resource_filter.resource_type,
            resource_id=resource_filter.resource_id,
            batch_id=batch_id,
        )

    def list_plan_dispatch_rows(
        self,
        *,
        version: int,
        role: Optional[str],
        start_time: str,
        end_time: str,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
    ) -> List[ScheduleDispatchRow]:
        resolution = self.resolve_plan(version, role)
        return self.list_plan_dispatch_rows_for_resolution(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
            scenario_id=resolution.scenario_id,
            start_time=start_time,
            end_time=end_time,
            scope_type=scope_type,
            scope_id=scope_id,
        )

    def list_plan_dispatch_rows_for_resolution(
        self,
        *,
        version: int,
        source_table: str,
        candidate_id: Optional[int],
        scenario_id: Optional[str] = None,
        start_time: str,
        end_time: str,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
    ) -> List[ScheduleDispatchRow]:
        return self.repo.list_dispatch_rows(
            version=int(version),
            source_table=source_table,
            candidate_id=candidate_id,
            scenario_id=scenario_id,
            start_time=start_time,
            end_time=end_time,
            scope_type=scope_type,
            scope_id=scope_id,
        )

    @staticmethod
    def _role_option_from_row(row: Dict[str, Any]) -> SchedulePlanRoleOption:
        selection_candidate_id = row.get("selection_candidate_id")
        resolved_candidate_id = row.get("resolved_candidate_id")
        return SchedulePlanRoleOption(
            role=str(row.get("role") or ""),
            source_table=str(row.get("source_table") or ""),
            candidate_id=int(resolved_candidate_id) if resolved_candidate_id is not None else None,
            candidate_key=str(row.get("candidate_key")) if row.get("candidate_key") is not None else None,
            candidate_label=plan_candidate_label(
                row.get("candidate_label"),
                role=str(row.get("role") or ""),
                candidate_key=str(row.get("candidate_key")) if row.get("candidate_key") is not None else None,
            ),
            candidate_kind=str(row.get("candidate_kind")) if row.get("candidate_kind") is not None else None,
            candidate_status=str(row.get("candidate_status")) if row.get("candidate_status") is not None else None,
            detail_saved=str(row.get("detail_saved")) if row.get("detail_saved") is not None else None,
            selection_candidate_id=int(selection_candidate_id) if selection_candidate_id is not None else None,
            resolved_candidate_id=int(resolved_candidate_id) if resolved_candidate_id is not None else None,
            candidate_missing=selection_candidate_id is not None and resolved_candidate_id is None,
        )

    def _validate_plan_role_options_integrity(self, version: int, options: List[SchedulePlanRoleOption]) -> None:
        for option in options:
            if option.candidate_missing:
                raise ValueError(
                    f"方案对比记录不完整：version={version}, role={option.role} 指向的方案不存在。"
                )

        roles = {option.role for option in options}
        if ROLE_ADOPTED not in roles:
            raise ValueError(f"方案对比记录不完整：version={version} 缺少正式采用方案。")

    def _validate_resolution_option(self, version: int, option: SchedulePlanRoleOption) -> None:
        if option.role not in VALID_PLAN_ROLES:
            raise ValueError(f"未知的排产方案角色：{option.role}")
        if option.source_table not in (SOURCE_SCHEDULE, SOURCE_CANDIDATE_ROWS):
            raise ValueError(f"未知的排产方案数据来源：{option.source_table}")
        if option.role != ROLE_ADOPTED and str(option.candidate_status or "").strip().lower() != "completed":
            raise ValueError("这套对比参考方案当前不是已完成状态，不能查看明细。")
        if option.source_table == SOURCE_CANDIDATE_ROWS:
            if option.candidate_id is None:
                raise ValueError("方案对比明细缺少编号。")
            if option.detail_saved != "yes":
                raise ValueError("方案对比明细没有保存。")
            if not self.repo.has_candidate_rows(version=int(version), candidate_id=int(option.candidate_id)):
                raise ValueError("方案对比明细没有找到对应排程。")
        if option.role == ROLE_ADOPTED and option.source_table != SOURCE_SCHEDULE:
            raise ValueError("adopted 方案必须从 Schedule 读取")

    def _resolve_scenario_plan(
        self,
        *,
        version: int,
        role: Optional[str],
        scenario_id: str,
    ) -> SchedulePlanResolution:
        row = self.repo.get_scenario_context(scenario_id)
        if row is None:
            raise ValueError("模拟方案不存在。")
        if str(row.get("status") or "") != "active":
            raise ValueError("模拟方案不是可预览状态。")
        if int(row.get("base_version") or 0) != int(version):
            raise ValueError("模拟方案不属于当前排产版本。")
        base_role = str(row.get("base_plan_role") or "").strip()
        requested_role = str(role or "").strip() or base_role
        if requested_role != base_role:
            raise ValueError("模拟方案不属于当前排产方案。")
        if not self.repo.has_scenario_rows(scenario_id=scenario_id):
            raise ValueError("模拟方案明细不存在。")
        available_roles = self.list_plan_roles(int(version))
        scenario_name = str(row.get("scenario_name") or "").strip() or None
        return self._with_plan_identity(SchedulePlanResolution(
            version=int(version),
            requested_role=base_role,
            selected_role=base_role,
            source_table=SOURCE_ADJUSTMENT_SCENARIO_ROWS,
            candidate_id=None,
            candidate_key=str(row.get("base_candidate_key")) if row.get("base_candidate_key") is not None else None,
            status="scenario_preview",
            message="当前正在预览模拟方案，正式计划还没有改变。",
            available_roles=available_roles,
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            is_scenario_preview=True,
        ))
