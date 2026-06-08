from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple, Union

from core.infrastructure.errors import ValidationError

SUPPORTED_SCHEDULE_RESOURCE_TYPES = {"machine", "operator"}
SUPPORTED_DISPATCH_RESOURCE_TYPES = {"machine", "operator", "team"}

_Message = Optional[Union[str, Callable[[str], str]]]


@dataclass(frozen=True)
class ScheduleResourceFilter:
    resource_type: str = ""
    resource_id: str = ""

    @property
    def column_name(self) -> str:
        if self.resource_type == "machine":
            return "machine_id"
        if self.resource_type == "operator":
            return "operator_id"
        return ""

    @property
    def has_filter(self) -> bool:
        return bool(self.resource_type and self.resource_id)


@dataclass(frozen=True)
class DispatchResourceFilter:
    sql_fragment: str = ""
    params: Tuple[str, ...] = ()
    include_team_context: bool = False

    @property
    def has_filter(self) -> bool:
        return bool(self.sql_fragment)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _message(template: _Message, resource_type: str, fallback: str) -> str:
    if callable(template):
        return str(template(resource_type))
    if template:
        return str(template)
    return fallback


def normalize_schedule_resource_filter(
    resource_type: Any = None,
    resource_id: Any = None,
    *,
    missing_type_message: _Message = None,
    unsupported_message: _Message = None,
    missing_id_message: _Message = None,
) -> ScheduleResourceFilter:
    resource_type_text = _text(resource_type).lower()
    resource_id_text = _text(resource_id)
    if not resource_type_text and resource_id_text:
        raise ValidationError(
            _message(missing_type_message, resource_type_text, "资源筛选缺少资源类型。"),
            field="resource_type",
            details={"resource_id": resource_id_text},
        )
    if resource_type_text and resource_type_text not in SUPPORTED_SCHEDULE_RESOURCE_TYPES:
        raise ValidationError(
            _message(unsupported_message, resource_type_text, "资源筛选只支持设备或人员维度。"),
            field="resource_type",
            details={"resource_type": resource_type_text},
        )
    if resource_type_text and not resource_id_text:
        raise ValidationError(
            _message(missing_id_message, resource_type_text, "资源筛选缺少资源编号。"),
            field="resource_id",
            details={"resource_type": resource_type_text},
        )
    return ScheduleResourceFilter(resource_type=resource_type_text, resource_id=resource_id_text)


def normalize_overdue_resource_filter(resource_type: Any = None, resource_id: Any = None) -> ScheduleResourceFilter:
    return normalize_schedule_resource_filter(
        resource_type,
        resource_id,
        missing_type_message="超期查询缺少资源类型，不能只带资源编号。",
        unsupported_message="超期查询只支持设备或人员维度。",
        missing_id_message="超期查询缺少资源编号，不能只带资源类型。",
    )


def normalize_dispatch_resource_filter(resource_type: Any = None, resource_id: Any = None) -> DispatchResourceFilter:
    resource_type_text = _text(resource_type).lower()
    resource_id_text = _text(resource_id)
    if not resource_type_text:
        if resource_id_text:
            raise ValidationError(
                "派工资源筛选缺少资源类型，不能只带资源编号。",
                field="resource_type",
                details={"resource_id": resource_id_text},
            )
        return DispatchResourceFilter()
    if resource_type_text not in SUPPORTED_DISPATCH_RESOURCE_TYPES:
        raise ValidationError(
            "派工资源筛选只支持设备、人员或班组维度。",
            field="resource_type",
            details={"resource_type": resource_type_text},
        )
    if not resource_id_text:
        # 派工页的“全部人员 / 全部设备 / 全部班组”入口故意把空 id 解释成全量，不改旧报表/超期过滤器的缺 id 拦截。
        if resource_type_text == "operator":
            return DispatchResourceFilter("TRIM(COALESCE(s.operator_id, '')) <> ''")
        if resource_type_text == "machine":
            return DispatchResourceFilter("TRIM(COALESCE(s.machine_id, '')) <> ''")
        return DispatchResourceFilter()
    if resource_type_text == "team":
        return DispatchResourceFilter(
            "((o.team_id = ?) OR (m.team_id = ?))",
            (resource_id_text, resource_id_text),
            include_team_context=True,
        )
    column_name = "operator_id" if resource_type_text == "operator" else "machine_id"
    return DispatchResourceFilter(
        f"TRIM(COALESCE(s.{column_name}, '')) = ?",
        (resource_id_text,),
    )


__all__ = [
    "SUPPORTED_SCHEDULE_RESOURCE_TYPES",
    "SUPPORTED_DISPATCH_RESOURCE_TYPES",
    "DispatchResourceFilter",
    "ScheduleResourceFilter",
    "normalize_dispatch_resource_filter",
    "normalize_overdue_resource_filter",
    "normalize_schedule_resource_filter",
]
