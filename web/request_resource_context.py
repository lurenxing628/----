from __future__ import annotations

from typing import Dict

from flask import has_request_context, request

from core.services.report.report_context_filters import normalize_report_resource_filter


def _text(value) -> str:
    return str(value or "").strip()


def _request_arg(name: str) -> str:
    if not has_request_context():
        return ""
    return _text(request.args.get(name))


def _request_resource_values() -> Dict[str, str]:
    return {
        "resource_type": _request_arg("resource_type"),
        "resource_id": _request_arg("resource_id"),
        "scope_type": _request_arg("scope_type"),
        "scope_id": _request_arg("scope_id"),
        "machine_id": _request_arg("machine_id"),
        "operator_id": _request_arg("operator_id"),
    }


def _has_request_resource_filter(values: Dict[str, str]) -> bool:
    return any(values.values())


def request_report_resource_context() -> Dict[str, str]:
    values = _request_resource_values()
    if not _has_request_resource_filter(values):
        return {"resource_type": "", "resource_id": "", "resource_label": ""}
    resource_type, resource_id = normalize_report_resource_filter(**values)
    return {"resource_type": resource_type, "resource_id": resource_id, "resource_label": resource_id}


__all__ = ["request_report_resource_context"]
