from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from data.repositories.schedule_plan_query_repo import (
    SOURCE_CANDIDATE_ROWS,
    SOURCE_SCHEDULE,
    SchedulePlanQueryRepository,
)
from data.repositories.schedule_rows import ScheduleDetailRow, ScheduleDispatchRow, ScheduleTimeSpanRow

ROLE_ADOPTED = "adopted"
ROLE_BASELINE_BEST = "baseline_best"
ROLE_CRITICAL_BEST = "critical_best"
VALID_PLAN_ROLES = (ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST)
PLAN_ROLE_LABELS = {
    ROLE_ADOPTED: "最终采用",
    ROLE_BASELINE_BEST: "原算法最好",
    ROLE_CRITICAL_BEST: "重点工序优先方案最好",
}


def plan_role_label(role: Optional[str]) -> str:
    normalized = _normalize_role(role)
    return PLAN_ROLE_LABELS.get(normalized, normalized)


def plan_candidate_label(label: Optional[str], *, role: Optional[str] = None, candidate_key: Optional[str] = None) -> str:
    text = str(label or "").strip()
    key = str(candidate_key or "").strip()
    if text and text != key:
        return text.replace("关键链候选", "重点工序优先方案")
    if key == "baseline":
        return "原算法方案"
    if key.startswith("graph_w") and "_of_" in key:
        parts = key.replace("graph_w", "", 1).split("_of_", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"重点工序优先方案 {int(parts[0])}/{int(parts[1])}"
    return plan_role_label(role)


@dataclass(frozen=True)
class SchedulePlanRoleOption:
    role: str
    source_table: str
    candidate_id: Optional[int]
    candidate_key: Optional[str]
    candidate_label: str
    candidate_kind: Optional[str]
    candidate_status: Optional[str]
    detail_saved: Optional[str]
    selection_candidate_id: Optional[int] = None
    resolved_candidate_id: Optional[int] = None
    candidate_missing: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "label": plan_role_label(self.role),
            "source_table": self.source_table,
            "candidate_id": self.candidate_id,
            "selection_candidate_id": self.selection_candidate_id,
            "resolved_candidate_id": self.resolved_candidate_id,
            "candidate_key": self.candidate_key,
            "candidate_label": self.candidate_label,
            "candidate_kind": self.candidate_kind,
            "candidate_status": self.candidate_status,
            "detail_saved": self.detail_saved,
            "candidate_missing": self.candidate_missing,
            "is_comparison": self.role != ROLE_ADOPTED,
        }


@dataclass(frozen=True)
class SchedulePlanResolution:
    version: int
    requested_role: str
    selected_role: str
    source_table: str
    candidate_id: Optional[int]
    candidate_key: Optional[str]
    status: str
    message: str
    available_roles: List[SchedulePlanRoleOption]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "requested_role": self.requested_role,
            "requested_label": plan_role_label(self.requested_role),
            "selected_role": self.selected_role,
            "selected_label": plan_role_label(self.selected_role),
            "source_table": self.source_table,
            "candidate_id": self.candidate_id,
            "candidate_key": self.candidate_key,
            "status": self.status,
            "message": self.message,
            "available_roles": [item.to_dict() for item in self.available_roles],
            "is_fallback": self.status == "fallback_to_adopted",
            "is_comparison": self.selected_role != ROLE_ADOPTED,
        }


def _normalize_role(role: Optional[str]) -> str:
    text = str(role or "").strip()
    return text or ROLE_ADOPTED


def _default_adopted_option() -> SchedulePlanRoleOption:
    return SchedulePlanRoleOption(
        role=ROLE_ADOPTED,
        source_table=SOURCE_SCHEDULE,
        candidate_id=None,
        candidate_key=None,
        candidate_label="最终采用",
        candidate_kind=None,
        candidate_status=None,
        detail_saved=None,
    )


class SchedulePlanQueryService:
    """统一解析 adopted / 代表候选方案，并按同一字段形状读取明细。"""

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

    def resolve_plan(self, version: int, role: Optional[str]) -> SchedulePlanResolution:
        requested_role = _normalize_role(role)
        if requested_role not in VALID_PLAN_ROLES:
            raise ValueError(f"未知的排产方案角色：{requested_role}")

        available_roles = self.list_plan_roles(int(version))
        roles_by_name = {option.role: option for option in available_roles}
        if requested_role in roles_by_name:
            option = roles_by_name[requested_role]
            self._validate_resolution_option(int(version), option)
            return SchedulePlanResolution(
                version=int(version),
                requested_role=requested_role,
                selected_role=option.role,
                source_table=option.source_table,
                candidate_id=option.candidate_id,
                candidate_key=option.candidate_key,
                status="selected",
                message="",
                available_roles=available_roles,
            )

        adopted = roles_by_name.get(ROLE_ADOPTED) or _default_adopted_option()
        self._validate_resolution_option(int(version), adopted)
        return SchedulePlanResolution(
            version=int(version),
            requested_role=requested_role,
            selected_role=ROLE_ADOPTED,
            source_table=adopted.source_table,
            candidate_id=adopted.candidate_id,
            candidate_key=adopted.candidate_key,
            status="fallback_to_adopted",
            message="当前版本没有保存这套方案明细，已显示最终采用方案。",
            available_roles=available_roles,
        )

    def get_plan_time_span(self, version: int, role: Optional[str]) -> Optional[ScheduleTimeSpanRow]:
        resolution = self.resolve_plan(version, role)
        return self.repo.get_plan_time_span(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
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
        return self.repo.list_detail_rows_between(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
            start_time=start_time,
            end_time=end_time,
        )

    def list_plan_detail_rows_all(self, *, version: int, role: Optional[str]) -> List[ScheduleDetailRow]:
        resolution = self.resolve_plan(version, role)
        return self.repo.list_detail_rows_all(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
        )

    def list_plan_overdue_base_rows(self, *, version: int, role: Optional[str]) -> List[Dict[str, Any]]:
        resolution = self.resolve_plan(version, role)
        return self.repo.list_overdue_base_rows(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
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
        return self.repo.list_dispatch_rows(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
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
                    f"候选方案角色映射损坏：version={version}, role={option.role} 指向的候选不存在。"
                )

        roles = {option.role for option in options}
        if ROLE_ADOPTED not in roles:
            raise ValueError(f"候选方案角色映射损坏：version={version} 缺少 adopted 最终采用方案。")

    def _validate_resolution_option(self, version: int, option: SchedulePlanRoleOption) -> None:
        if option.role not in VALID_PLAN_ROLES:
            raise ValueError(f"未知的排产方案角色：{option.role}")
        if option.source_table not in (SOURCE_SCHEDULE, SOURCE_CANDIDATE_ROWS):
            raise ValueError(f"未知的排产方案数据来源：{option.source_table}")
        if option.source_table == SOURCE_CANDIDATE_ROWS:
            if option.candidate_id is None:
                raise ValueError("candidate_rows 方案缺少 candidate_id")
            if option.detail_saved != "yes":
                raise ValueError("候选方案指向 candidate_rows，但这套候选没有保存明细。")
            if not self.repo.has_candidate_rows(version=int(version), candidate_id=int(option.candidate_id)):
                raise ValueError("候选方案指向 candidate_rows，但没有找到对应的候选明细。")
        if option.role == ROLE_ADOPTED and option.source_table != SOURCE_SCHEDULE:
            raise ValueError("adopted 方案必须从 Schedule 读取")
