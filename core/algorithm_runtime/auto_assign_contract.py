from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

AUTO_ASSIGN_REASON_SUCCESS = ""
AUTO_ASSIGN_REASON_MISSING_MACHINE_POOL = "auto_assign_missing_machine_pool"
AUTO_ASSIGN_REASON_NO_MACHINE_CANDIDATE = "auto_assign_no_machine_candidate"
AUTO_ASSIGN_REASON_NO_OPERATOR_CANDIDATE = "auto_assign_no_operator_candidate"
# 全部机-人组合的完工时间都越过排产截止窗口（blocked_by_window）时的专属归因；
# 避免把截止日期问题误导成资质问题。
AUTO_ASSIGN_REASON_WINDOW_BLOCKED = "auto_assign_window_blocked"


@dataclass(frozen=True)
class AutoAssignAttempt:
    machine_id: str = ""
    operator_id: str = ""
    reason: str = AUTO_ASSIGN_REASON_SUCCESS
    # Native probes report whether two feasible pairs tied on (end_time, changeover), the only
    # case in which the resource-demand window can influence the chosen pair. None means the
    # attempt came from a caller that does not report it, so consumers must not assume either way.
    pair_tie_occurred: Optional[bool] = None
