from __future__ import annotations

from dataclasses import dataclass
from typing import Any

AUTO_ASSIGN_REASON_SUCCESS = ""
AUTO_ASSIGN_REASON_MISSING_OP_TYPE_ID = "auto_assign_missing_op_type_id"
AUTO_ASSIGN_REASON_MISSING_MACHINE_POOL = "auto_assign_missing_machine_pool"
AUTO_ASSIGN_REASON_NO_MACHINE_CANDIDATE = "auto_assign_no_machine_candidate"
AUTO_ASSIGN_REASON_NO_OPERATOR_CANDIDATE = "auto_assign_no_operator_candidate"
AUTO_ASSIGN_REASON_NO_FEASIBLE_PAIR = "auto_assign_no_feasible_pair"
# 全部机-人组合的完工时间都越过排产截止窗口（blocked_by_window）时的专属归因；
# 与 NO_FEASIBLE_PAIR（资源/时间通用不可行）区分，避免把截止日期问题误导成资质问题。
AUTO_ASSIGN_REASON_WINDOW_BLOCKED = "auto_assign_window_blocked"
AUTO_ASSIGN_REASON_INVALID_INTERNAL_HOURS = "invalid_internal_hours"


@dataclass(frozen=True)
class AutoAssignAttempt:
    machine_id: str = ""
    operator_id: str = ""
    reason: str = AUTO_ASSIGN_REASON_SUCCESS


def auto_assign_attempt_from_result(
    result: Any,
    *,
    failure_reason: str = AUTO_ASSIGN_REASON_NO_FEASIBLE_PAIR,
) -> AutoAssignAttempt:
    if isinstance(result, AutoAssignAttempt):
        return result
    if result is None:
        return AutoAssignAttempt(reason=failure_reason)
    if not isinstance(result, (list, tuple)) or len(result) < 2:
        raise TypeError("auto_assign probe result is not a pair")
    machine_id = str(result[0] or "").strip()
    operator_id = str(result[1] or "").strip()
    if machine_id and operator_id:
        return AutoAssignAttempt(machine_id=machine_id, operator_id=operator_id)
    return AutoAssignAttempt(machine_id=machine_id, operator_id=operator_id, reason=failure_reason)
