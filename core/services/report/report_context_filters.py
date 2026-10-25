from __future__ import annotations

from typing import Any, Dict, Tuple

from core.errors import ValidationError
from core.models.schedule_resource_filter import normalize_schedule_resource_filter

# normalize_report_resource_filter 的 6 个资源筛选实参名(顺序=签名参数序)。
# web 侧从 request.args 抄这组键时一律遍历本常量,不要再手维第二份键名列表(R67 收口点)。
REPORT_RESOURCE_FILTER_ARG_KEYS = (
    "resource_type",
    "resource_id",
    "scope_type",
    "scope_id",
    "machine_id",
    "operator_id",
)


def _report_resource_validation_messages() -> Dict[str, Any]:
    return {
        "missing_type_message": "资源筛选缺少资源类型，请重新从设备或人员入口进入报表。",
        "unsupported_message": lambda kind: f"当前报表暂不支持{'班组' if kind == 'team' else kind}维度筛选，请切换到设备或人员后再查看。",
        "missing_id_message": lambda kind: (
            "资源筛选类型是设备，但缺少设备编号，请重新从设备入口进入报表。"
            if kind == "machine"
            else "资源筛选类型是人员，但缺少人员编号，请重新从人员入口进入报表。"
        ),
    }


def _raise_resource_conflict(message: str, *, field: str, details: Dict[str, str]) -> None:
    raise ValidationError(message, field=field, details=details)


def _merge_primary_and_scope_aliases(
    resource_type_text: str,
    resource_id_text: str,
    scope_type_text: str,
    scope_id_text: str,
) -> Tuple[str, str]:
    if resource_type_text and scope_type_text and resource_type_text != scope_type_text:
        _raise_resource_conflict(
            "资源筛选类型冲突，请只保留一个资源维度后再查看报表。",
            field="resource_type",
            details={"resource_type": resource_type_text, "scope_type": scope_type_text},
        )
    if resource_id_text and scope_id_text and resource_id_text != scope_id_text:
        _raise_resource_conflict(
            "资源筛选编号冲突，请只保留一个资源编号后再查看报表。",
            field="resource_id",
            details={"resource_id": resource_id_text, "scope_id": scope_id_text},
        )
    return resource_type_text or scope_type_text, resource_id_text or scope_id_text


def _infer_single_resource_alias(
    resource_type_text: str,
    resource_id_text: str,
    machine_id_text: str,
    operator_id_text: str,
) -> Tuple[str, str]:
    if resource_type_text or resource_id_text:
        return resource_type_text, resource_id_text
    if machine_id_text and operator_id_text:
        _raise_resource_conflict(
            "资源筛选同时包含设备和人员，请只保留一个资源维度后再查看报表。",
            field="resource_type",
            details={"machine_id": machine_id_text, "operator_id": operator_id_text},
        )
    if machine_id_text:
        return "machine", machine_id_text
    if operator_id_text:
        return "operator", operator_id_text
    return "", ""


def _merge_machine_alias(resource_id_text: str, machine_id_text: str, operator_id_text: str) -> str:
    if operator_id_text:
        _raise_resource_conflict(
            "资源筛选类型是设备，但同时收到了人员编号，请重新从设备入口进入报表。",
            field="resource_id",
            details={"resource_type": "machine", "operator_id": operator_id_text},
        )
    if resource_id_text and machine_id_text and resource_id_text != machine_id_text:
        _raise_resource_conflict(
            "资源筛选设备编号冲突，请只保留一个设备编号后再查看报表。",
            field="resource_id",
            details={"resource_type": "machine", "resource_id": resource_id_text, "machine_id": machine_id_text},
        )
    return resource_id_text or machine_id_text


def _merge_operator_alias(resource_id_text: str, machine_id_text: str, operator_id_text: str) -> str:
    if machine_id_text:
        _raise_resource_conflict(
            "资源筛选类型是人员，但同时收到了设备编号，请重新从人员入口进入报表。",
            field="resource_id",
            details={"resource_type": "operator", "machine_id": machine_id_text},
        )
    if resource_id_text and operator_id_text and resource_id_text != operator_id_text:
        _raise_resource_conflict(
            "资源筛选人员编号冲突，请只保留一个人员编号后再查看报表。",
            field="resource_id",
            details={"resource_type": "operator", "resource_id": resource_id_text, "operator_id": operator_id_text},
        )
    return resource_id_text or operator_id_text


def _merge_resource_specific_aliases(
    resource_type_text: str,
    resource_id_text: str,
    machine_id_text: str,
    operator_id_text: str,
) -> str:
    if resource_type_text == "machine":
        return _merge_machine_alias(resource_id_text, machine_id_text, operator_id_text)
    if resource_type_text == "operator":
        return _merge_operator_alias(resource_id_text, machine_id_text, operator_id_text)
    return resource_id_text


def normalize_report_resource_filter(
    resource_type: Any = None,
    resource_id: Any = None,
    *,
    scope_type: Any = None,
    scope_id: Any = None,
    machine_id: Any = None,
    operator_id: Any = None,
) -> Tuple[str, str]:
    resource_type_text, resource_id_text = _merge_primary_and_scope_aliases(
        str(resource_type or "").strip().lower(),
        str(resource_id or "").strip(),
        str(scope_type or "").strip().lower(),
        str(scope_id or "").strip(),
    )
    machine_id_text = str(machine_id or "").strip()
    operator_id_text = str(operator_id or "").strip()
    resource_type_text, resource_id_text = _infer_single_resource_alias(
        resource_type_text,
        resource_id_text,
        machine_id_text,
        operator_id_text,
    )
    resource_id_text = _merge_resource_specific_aliases(
        resource_type_text,
        resource_id_text,
        machine_id_text,
        operator_id_text,
    )
    resource_filter = normalize_schedule_resource_filter(
        resource_type_text,
        resource_id_text,
        **_report_resource_validation_messages(),
    )
    return resource_filter.resource_type, resource_filter.resource_id
