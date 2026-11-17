"""Verify directory claims and expose only admission-time public summaries and failure reasons."""

import re
from typing import Optional

from core.errors import AppError
from core.models.enums import RunState
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_preflight import check_stored_input
from core.models.workbench_run_history import inconsistent, local_datetime

from .candidate_values import corrupt

COMPUTATION_FAILED = "本次候选计算失败。请联系维护人员，再重新做排产检查。"
# 原话指着检查页列出的缺项，排产记录里没有这份清单，改成能照做的说法。
_FAILURE_GUIDES = {
    "input_blocked": "排产资料还有缺项，这次排产没有开始。请重新做排产检查，按检查结果补齐后再排产。",
    # 下面几条原话是旧排产页面的“冻结窗口”说法；工作台改说不重排时段，并给出能照做的出路。
    "all_operations_frozen": "要重排的工序都因不重排时段保持原安排，没有可重排的工序，这次排产没有开始。"
                             "请重新做排产检查，把不重排时段改短或不设。",
}
_HOLD_FAILURES = {
    "execution_seed_conflict": "现场报工和不重排时段里要原样保留的原安排对不上，这次排产没有完成。"
                               "请重新做排产检查，按检查结果处理后再排产。",
    "execution_completed_downstream_before_actual_finish": "要原样保留的安排排在同批已完工前道的实际完工之前，这次排产没有完成。"
                     "请重新做排产检查，按检查结果把不重排时段改短或不设，或到现场记录核对前道的实际完工时间。",
}
_CHINESE = re.compile(r"[\u4e00-\u9fff]")


def hold_failure_message(exc: AppError) -> Optional[str]:
    """要原样保留的原安排与现场报工对不上的失败（排产输入按 details["reason"] 报出）：返回工作台的说法；
    其它失败返回 None。"""
    # Any AppError may arrive here; only some carry details, and only the ones listed above a reason.
    reason = None if exc.details is None else exc.details.get("reason")
    return _HOLD_FAILURES[reason] if reason in _HOLD_FAILURES else None


def failure_message(code, message):
    """排产失败时给用户看的原因：写给用户的中文原因照原话；内部校验的英文原文只留在诊断里。"""
    if code in _FAILURE_GUIDES:
        return _FAILURE_GUIDES[code]
    if type(message) is str and _CHINESE.search(message):
        return message
    return COMPUTATION_FAILED


def job_clocks(row):
    try:
        accepted = local_datetime(row["accepted_at"])
        started = local_datetime(row["started_at"]) if row["started_at"] is not None else None
        finished = local_datetime(row["finished_at"]) if row["finished_at"] is not None else None
        if (started is not None and started < accepted) or (finished is not None and finished < (started or accepted)):
            inconsistent()
    except (ValueError, TypeError):
        inconsistent()
    return started, finished


def _stored_error(row, result):
    error = (result.get("error") if result is not None and row["state"] in (RunState.FAILED.value, RunState.INTERRUPTED.value)
             else None)
    if type(error) is dict and all(type(error.get(key)) is str and error[key] for key in ("code", "message")):
        return error
    return None


def failure_reason(row, result):
    """失败或中断的排产给出原因；读不出原因时不编造，留空。"""
    error = _stored_error(row, result)
    return None if error is None else {"code": error["code"], "message": error["message"]}


def admitted_run_input(value):
    """A run's stored normalized input, admitted once wherever it is read: the writer's key set and value
    domains (``check_stored_input``), with no default filled in; anything else is a corrupt archive."""
    try:
        check_stored_input(value)
    except WorkbenchCommandRejected:
        corrupt()
    return value


_SCOPE_FIELDS = ("start_date", "end_date", "ready_check", "missing_resource_policy", "completed_policy", "material_strategy")


def scope_input_values(settings):
    """The admitted input's public scope settings; ``hold_window`` only when the run set one."""
    return {**{key: settings[key] for key in _SCOPE_FIELDS},
            **({"hold_window": settings["hold_window"]} if "hold_window" in settings else {})}


def scope_summary(settings):
    return {**scope_input_values(settings), "batch_count": len(settings["batch_refs"]),
            "selection": "explicit_batches", "basis": "captured_at_run_admission"}
