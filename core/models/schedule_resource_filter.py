from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Union

from core.errors import ValidationError

SUPPORTED_SCHEDULE_RESOURCE_TYPES = {"machine", "operator"}

_Message = Optional[Union[str, Callable[[str], str]]]


@dataclass(frozen=True)
class ScheduleResourceFilter:
    resource_type: str = ""
    resource_id: str = ""


def _message(template: _Message, resource_type: str, fallback: str) -> str:
    if callable(template):
        return str(template(resource_type))
    if template:
        return str(template)
    return fallback


def normalize_schedule_resource_filter(
    resource_type_text: str,
    resource_id_text: str,
    *,
    missing_type_message: _Message = None,
    unsupported_message: _Message = None,
    missing_id_message: _Message = None,
) -> ScheduleResourceFilter:
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


__all__ = [
    "SUPPORTED_SCHEDULE_RESOURCE_TYPES",
    "ScheduleResourceFilter",
    "normalize_schedule_resource_filter",
]
