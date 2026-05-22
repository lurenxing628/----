from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from core.infrastructure.errors import ValidationError
from data.repositories.schedule_plan_query_repo import SOURCE_SCHEDULE

from .schedule_plan_query_service import (
    ROLE_ADOPTED,
    VALID_PLAN_ROLES,
    is_comparison_source,
    plan_role_label,
)
from .version_resolution import VersionResolution, require_selected_version, resolve_version_or_latest

_PLAN_ROLE_COMPARE_HINT = "当前查看的是对比方案，只用来和最终采用方案比一比；现场执行仍以“最终采用”为准。"


@dataclass(frozen=True)
class ScheduleResultViewContext:
    version_resolution: VersionResolution
    selected_version: Optional[int]
    requested_version: Optional[int]
    has_history: bool
    plan_resolution: Dict[str, Any]
    requested_role: str
    selected_role: str
    source_table: Optional[str]
    candidate_id: Any
    candidate_key: Any
    available_roles: List[Dict[str, Any]]
    is_fallback: bool
    is_comparison: bool
    is_scenario_preview: bool
    scenario_id: Any
    scenario_name: Any
    plan_role_notice: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_resolution": self.version_resolution.to_dict(),
            "selected_version": self.selected_version,
            "requested_version": self.requested_version,
            "has_history": self.has_history,
            "plan_resolution": dict(self.plan_resolution),
            "requested_role": self.requested_role,
            "selected_role": self.selected_role,
            "source_table": self.source_table,
            "candidate_id": self.candidate_id,
            "candidate_key": self.candidate_key,
            "available_roles": list(self.available_roles),
            "is_fallback": self.is_fallback,
            "is_comparison": self.is_comparison,
            "is_scenario_preview": self.is_scenario_preview,
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "plan_role_notice": self.plan_role_notice,
        }


def normalize_plan_role(value: Any) -> str:
    plan_role = str(value or "").strip() or ROLE_ADOPTED
    if plan_role not in VALID_PLAN_ROLES:
        valid_labels = " / ".join(plan_role_label(role) for role in VALID_PLAN_ROLES)
        raise ValidationError(f"排产方案不正确，请选择：{valid_labels}。", field="plan_role")
    return plan_role


def default_plan_resolution_dict(plan_role: Optional[str] = None) -> Dict[str, Any]:
    requested_role = normalize_plan_role(plan_role)
    selected_label = plan_role_label(ROLE_ADOPTED)
    return {
        "version": None,
        "requested_role": requested_role,
        "requested_label": plan_role_label(requested_role),
        "selected_role": ROLE_ADOPTED,
        "selected_label": selected_label,
        "source_table": SOURCE_SCHEDULE,
        "candidate_id": None,
        "candidate_key": None,
        "status": "selected" if requested_role == ROLE_ADOPTED else "fallback_to_adopted",
        "message": "" if requested_role == ROLE_ADOPTED else "当前版本没有保存这套方案明细，已显示最终采用方案。",
        "available_roles": [
            {
                "role": ROLE_ADOPTED,
                "label": selected_label,
                "source_table": SOURCE_SCHEDULE,
                "candidate_id": None,
                "candidate_key": None,
                "candidate_label": selected_label,
                "candidate_kind": None,
                "candidate_status": None,
                "detail_saved": None,
                "is_comparison": False,
            }
        ],
        "is_fallback": requested_role != ROLE_ADOPTED,
        "is_comparison": False,
        "is_scenario_preview": False,
        "scenario_id": None,
        "scenario_name": None,
    }


def _resolution_to_dict(resolution: Any) -> Dict[str, Any]:
    if resolution is None:
        return default_plan_resolution_dict()
    if isinstance(resolution, ScheduleResultViewContext):
        return dict(resolution.plan_resolution)
    if isinstance(resolution, dict):
        if isinstance(resolution.get("plan_resolution"), dict):
            return dict(resolution.get("plan_resolution") or {})
        return dict(resolution)
    if hasattr(resolution, "to_dict"):
        return dict(resolution.to_dict())

    source_table = getattr(resolution, "source_table", None)
    requested_role = getattr(resolution, "requested_role", ROLE_ADOPTED)
    selected_role = getattr(resolution, "selected_role", ROLE_ADOPTED)
    return {
        "version": getattr(resolution, "version", None),
        "requested_role": requested_role,
        "requested_label": plan_role_label(requested_role),
        "selected_role": selected_role,
        "selected_label": plan_role_label(selected_role),
        "source_table": source_table,
        "candidate_id": getattr(resolution, "candidate_id", None),
        "candidate_key": getattr(resolution, "candidate_key", None),
        "status": getattr(resolution, "status", "selected"),
        "message": getattr(resolution, "message", ""),
        "available_roles": serialize_plan_role_options(getattr(resolution, "available_roles", None)),
        "is_fallback": getattr(resolution, "status", "") == "fallback_to_adopted",
        "is_comparison": is_comparison_source(source_table),
        "is_scenario_preview": bool(getattr(resolution, "is_scenario_preview", False)),
        "scenario_id": getattr(resolution, "scenario_id", None),
        "scenario_name": getattr(resolution, "scenario_name", None),
    }


def resolve_plan(plan_query_service, version: int, plan_role: Optional[str], scenario_id: Optional[str] = None):
    try:
        if scenario_id:
            return plan_query_service.resolve_plan_view(int(version), plan_role, scenario_id)
        return plan_query_service.resolve_plan(int(version), plan_role)
    except ValueError as exc:
        raise ValidationError(str(exc), field="plan_role") from exc


def selected_plan_role(plan_resolution: Dict[str, Any]) -> str:
    return str((plan_resolution or {}).get("selected_role") or ROLE_ADOPTED)


def attach_plan_metadata(data: Dict[str, Any], plan_resolution: Dict[str, Any]) -> None:
    data.update(
        requested_plan_role=plan_resolution.get("requested_role"),
        requested_plan_role_label=plan_resolution.get("requested_label"),
        effective_plan_role=plan_resolution.get("selected_role"),
        effective_plan_role_label=plan_resolution.get("selected_label"),
        plan_role_status=plan_resolution.get("status"),
        plan_role_message=plan_resolution.get("message"),
        plan_role_resolution=plan_resolution,
        available_plan_roles=list(plan_resolution.get("available_roles") or []),
        is_comparison_plan=bool(plan_resolution.get("is_comparison")),
        is_scenario_preview=bool(plan_resolution.get("is_scenario_preview")),
        scenario_id=plan_resolution.get("scenario_id"),
        scenario_name=plan_resolution.get("scenario_name"),
    )


def _truthy_override_or_data(
    overrides: Dict[str, Any],
    data: Dict[str, Any],
    override_key: str,
    data_keys: tuple,
    default: Any,
) -> Any:
    override_value = overrides.get(override_key)
    if override_value:
        return override_value
    for key in data_keys:
        data_value = data.get(key)
        if data_value:
            return data_value
    return default


def _override_or_data(overrides: Dict[str, Any], data: Dict[str, Any], key: str) -> Any:
    return overrides.get(key) if key in overrides else data.get(key)


def _plan_role_message(overrides: Dict[str, Any], data: Dict[str, Any]) -> str:
    override_value = overrides.get("message")
    if override_value is not None:
        return str(override_value)
    return str(data.get("message") or "")


def _plan_role_is_comparison(overrides: Dict[str, Any], data: Dict[str, Any], source_table: Any) -> bool:
    if "is_comparison" in overrides:
        return bool(overrides.get("is_comparison"))
    return bool(data.get("is_comparison") or is_comparison_source(source_table))


def plan_role_filter_fields(plan_resolution_or_context: Any = None, **overrides: Any) -> Dict[str, Any]:
    data = {} if plan_resolution_or_context is None else _resolution_to_dict(plan_resolution_or_context)
    requested_role = str(_truthy_override_or_data(overrides, data, "requested_role", ("requested_role",), ROLE_ADOPTED))
    effective_role = str(
        _truthy_override_or_data(overrides, data, "effective_role", ("selected_role", "effective_plan_role"), ROLE_ADOPTED)
    )
    status = str(_truthy_override_or_data(overrides, data, "status", ("status", "plan_role_status"), "selected"))
    message = _plan_role_message(overrides, data)
    candidate_id = _override_or_data(overrides, data, "candidate_id")
    candidate_key = _override_or_data(overrides, data, "candidate_key")
    source_table = _override_or_data(overrides, data, "source_table")
    is_comparison = _plan_role_is_comparison(overrides, data, source_table)
    scenario_id = _override_or_data(overrides, data, "scenario_id")
    scenario_name = _override_or_data(overrides, data, "scenario_name")
    is_scenario_preview = bool(_override_or_data(overrides, data, "is_scenario_preview"))

    return {
        "plan_role": requested_role,
        "requested_plan_role": requested_role,
        "effective_plan_role": effective_role,
        "plan_role_status": status,
        "plan_role_message": message,
        "plan_role_label": plan_role_label(effective_role),
        "requested_plan_role_label": plan_role_label(requested_role),
        "effective_plan_role_label": plan_role_label(effective_role),
        "candidate_id": candidate_id,
        "candidate_key": candidate_key,
        "source_table": source_table,
        "is_comparison": bool(is_comparison),
        "is_scenario_preview": is_scenario_preview,
        "scenario_id": scenario_id,
        "scenario_name": scenario_name,
    }


def serialize_plan_role_options(options: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for option in options or []:
        if isinstance(option, dict):
            item = dict(option)
        elif hasattr(option, "to_dict"):
            item = dict(option.to_dict())
        else:
            role = str(getattr(option, "role", "") or "").strip()
            source_table = getattr(option, "source_table", None)
            item = {
                "role": role,
                "label": plan_role_label(role),
                "source_table": source_table,
                "candidate_id": getattr(option, "candidate_id", None),
                "selection_candidate_id": getattr(option, "selection_candidate_id", None),
                "resolved_candidate_id": getattr(option, "resolved_candidate_id", None),
                "candidate_key": getattr(option, "candidate_key", None),
                "candidate_label": getattr(option, "candidate_label", None),
                "candidate_kind": getattr(option, "candidate_kind", None),
                "candidate_status": getattr(option, "candidate_status", None),
                "detail_saved": getattr(option, "detail_saved", None),
                "candidate_missing": getattr(option, "candidate_missing", False),
                "is_comparison": is_comparison_source(source_table),
            }
        role = str(item.get("role") or "").strip()
        if not role:
            continue
        out.append(item)
    if out:
        return out
    return [{"role": ROLE_ADOPTED, "label": plan_role_label(ROLE_ADOPTED), "is_comparison": False}]


def plan_role_notice_from_fields(fields: Dict[str, Any]) -> str:
    if bool(fields.get("is_comparison")):
        if bool(fields.get("is_scenario_preview")):
            return "当前正在预览模拟方案，正式计划还没有改变。"
        return _PLAN_ROLE_COMPARE_HINT
    return str(fields.get("plan_role_message") or "").strip()


def plan_role_notice_from_context(context: ScheduleResultViewContext) -> str:
    return plan_role_notice_from_fields(plan_role_filter_fields(context))


def _build_view_context(
    *,
    version_resolution: VersionResolution,
    plan_resolution: Dict[str, Any],
) -> ScheduleResultViewContext:
    available_roles = list(plan_resolution.get("available_roles") or [])
    fields = plan_role_filter_fields(plan_resolution)
    return ScheduleResultViewContext(
        version_resolution=version_resolution,
        selected_version=version_resolution.selected_version,
        requested_version=version_resolution.requested_version,
        has_history=bool(version_resolution.has_history),
        plan_resolution=plan_resolution,
        requested_role=str(plan_resolution.get("requested_role") or ROLE_ADOPTED),
        selected_role=selected_plan_role(plan_resolution),
        source_table=plan_resolution.get("source_table"),
        candidate_id=plan_resolution.get("candidate_id"),
        candidate_key=plan_resolution.get("candidate_key"),
        available_roles=available_roles,
        is_fallback=bool(plan_resolution.get("is_fallback")),
        is_comparison=bool(plan_resolution.get("is_comparison")),
        is_scenario_preview=bool(plan_resolution.get("is_scenario_preview")),
        scenario_id=plan_resolution.get("scenario_id"),
        scenario_name=plan_resolution.get("scenario_name"),
        plan_role_notice=plan_role_notice_from_fields(fields),
    )


def resolve_schedule_result_view_context(
    *,
    raw_version: Any,
    raw_plan_role: Any,
    latest_version: int,
    version_exists: Callable[[int], bool],
    plan_query_service,
    require_existing_version: bool = False,
    raw_scenario_id: Any = None,
) -> ScheduleResultViewContext:
    version_resolution = resolve_version_or_latest(
        raw_version,
        latest_version=int(latest_version or 0),
        version_exists=version_exists,
    )
    if version_resolution.status == "no_history":
        return _build_view_context(
            version_resolution=version_resolution,
            plan_resolution=default_plan_resolution_dict(raw_plan_role),
        )

    if version_resolution.status == "missing_history":
        if require_existing_version:
            require_selected_version(version_resolution)
        return _build_view_context(
            version_resolution=version_resolution,
            plan_resolution=default_plan_resolution_dict(raw_plan_role),
        )

    selected_version = require_selected_version(version_resolution)
    plan_resolution_obj = resolve_plan(plan_query_service, selected_version, raw_plan_role, raw_scenario_id)
    return _build_view_context(
        version_resolution=version_resolution,
        plan_resolution=_resolution_to_dict(plan_resolution_obj),
    )
