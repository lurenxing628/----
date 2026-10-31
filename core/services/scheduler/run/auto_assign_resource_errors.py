from __future__ import annotations

from typing import Any, Dict, Sequence, Set

from core.models.scheduler_public_errors import public_error_from_structured_failure

AUTO_ASSIGN_RESOURCE_ERROR_CODES = {
    "auto_assign_resource_pool_incomplete",
    "auto_assign_no_resource_combination",
}


def is_auto_assign_resource_failure(detail: Dict[str, Any]) -> bool:
    return detail["code"] in AUTO_ASSIGN_RESOURCE_ERROR_CODES


def first_public_auto_assign_resource_error(failure_details: Sequence[Dict[str, Any]]) -> str:
    for detail in failure_details:
        if not is_auto_assign_resource_failure(detail):
            continue
        return public_error_from_structured_failure(detail)["message"]
    return ""


def auto_assign_failed_op_ids_from_failure_details(failure_details: Sequence[Dict[str, Any]]) -> Set[int]:
    return {
        detail["op_id"]
        for detail in failure_details
        if is_auto_assign_resource_failure(detail)
    }
