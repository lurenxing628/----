from __future__ import annotations

from typing import Dict

from flask import has_request_context, request

from core.services.report.report_context_filters import (
    REPORT_RESOURCE_FILTER_ARG_KEYS,
    normalize_report_resource_filter,
)


def _text(value) -> str:
    return str(value or "").strip()


def _request_arg(name: str) -> str:
    if not has_request_context():
        return ""
    return _text(request.args.get(name))


def _request_resource_values() -> Dict[str, str]:
    # R67 收编:6 键名单一来源 = 收口点常量,勿在此手维第二份键名列表。
    return {key: _request_arg(key) for key in REPORT_RESOURCE_FILTER_ARG_KEYS}


def _has_request_resource_filter(values: Dict[str, str]) -> bool:
    return any(values.values())


def request_report_resource_context() -> Dict[str, str]:
    values = _request_resource_values()
    if not _has_request_resource_filter(values):
        return {"resource_type": "", "resource_id": "", "resource_label": ""}
    resource_type, resource_id = normalize_report_resource_filter(**values)
    return {"resource_type": resource_type, "resource_id": resource_id, "resource_label": resource_id}


__all__ = ["request_report_resource_context"]
