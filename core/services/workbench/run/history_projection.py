"""Verify directory claims and expose only admission-time public summaries and failure reasons."""

import json
import math
import re

from core.models.workbench_preflight import stored_hold_window_valid
from core.models.workbench_run_history import STATES, TERMINAL_STATES, inconsistent, local_date, local_datetime

COMPUTATION_FAILED = "本次候选计算失败。请联系维护人员，再重新做排产检查。"
# 旧版本把真实原因只记在诊断里，给用户的都是这一句。
_LEGACY_FAILURE = "候选排产没有完成。请到「排产记录」查看原因，改好后重新做排产检查。"
# 原话指着检查页列出的缺项，排产记录里没有这份清单，改成能照做的说法。
_FAILURE_GUIDES = {
    "input_blocked": "排产资料还有缺项，这次排产没有开始。请重新做排产检查，按检查结果补齐后再排产。",
    # 下面几条原话是旧排产页面的“冻结窗口”说法；工作台改说不重排时段，并给出能照做的出路。
    "all_operations_frozen": "要重排的工序都因不重排时段保持原安排，没有可重排的工序，这次排产没有开始。"
                             "请重新做排产检查，把不重排时段改短或不设。",
}
_HOLD_FAILURES = {
    "freeze_window": "排产要原样保留不重排时段里的原安排，但正式计划里这段时间的安排读不出来或者对不上，这次排产没有完成。"
                     "请重新做排产检查，把不重排时段改短或不设；仍不行请联系维护人员核对正式计划。",
    "execution_seed_conflict": "现场报工和不重排时段里要原样保留的原安排对不上，这次排产没有完成。"
                               "请重新做排产检查，按检查结果处理后再排产。",
    "execution_completed_downstream_before_actual_finish": "要原样保留的安排排在同批已完工前道的实际完工之前，这次排产没有完成。"
                     "请重新做排产检查，按检查结果把不重排时段改短或不设，或到现场记录核对前道的实际完工时间。",
}
_CHINESE = re.compile(r"[\u4e00-\u9fff]")


def hold_failure_message(exc):
    """旧排产服务按“冻结窗口”说的失败（读原安排、现场报工与原安排对不上）：返回工作台的说法；不是这类返回 None。"""
    details = getattr(exc, "details", None)
    details = details if isinstance(details, dict) else {}
    for key in (details.get("reason"), details.get("field")):
        if key in _HOLD_FAILURES:
            return _HOLD_FAILURES[key]
    return None


def failure_message(code, message):
    """排产失败时给用户看的原因：写给用户的中文原因照原话；内部校验的英文原文只留在诊断里。"""
    if code in _FAILURE_GUIDES:
        return _FAILURE_GUIDES[code]
    if type(message) is str and _CHINESE.search(message):
        return message
    return COMPUTATION_FAILED


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            inconsistent()
        result[key] = value
    return result


def _constant(value):
    inconsistent()


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        inconsistent()
    return result


def stored_json(value):
    if type(value) is not str:
        inconsistent()
    try:
        result = json.loads(value, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)
    except (ValueError, TypeError, RecursionError):
        inconsistent()
    if type(result) is not dict:
        inconsistent()
    return result


def _ref(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{48}", value) is None:
        inconsistent()
    return value


def _job_clocks(row):
    try:
        accepted = local_datetime(row["accepted_at"])
        started = local_datetime(row["started_at"]) if row["started_at"] is not None else None
        finished = local_datetime(row["finished_at"]) if row["finished_at"] is not None else None
        if (started is not None and started < accepted) or (finished is not None and finished < (started or accepted)):
            inconsistent()
    except (ValueError, TypeError):
        inconsistent()
    return started, finished


def _job_lifecycle(row, started, finished):
    state = row["state"]
    if ((state == "queued" and (started is not None or row["executor_ref"] is not None))
            or (state == "running" and (started is None or not row["executor_ref"]))
            or ((state in TERMINAL_STATES) != (finished is not None))):
        inconsistent()


def _job(row):
    _ref(row["run_ref"])
    state, stage = row["state"], row["stage"]
    if state not in STATES:
        inconsistent()
    expected = {"queued": ("queued", "awaiting_reconciliation"), "running": ("computing", "awaiting_reconciliation")}
    if stage not in expected.get(state, ("finished",)):
        inconsistent()
    started, finished = _job_clocks(row)
    _job_lifecycle(row, started, finished)
    admission = stored_json(row["admission_json"])
    if (row["admission_action"] != "scheduling.run" or row["admission_context"] != row["input_ref"]
            or admission.get("data") != {"run_ref": row["run_ref"]}):
        inconsistent()


def _candidates(rows):
    result = {}
    for row in rows:
        ref = _ref(row["candidate_ref"])
        count = row["task_count"]
        if (ref in result or type(count) is not int or count < 0 or count != row["actual_count"]
                or row["status"] not in ("completed", "failed", "skipped")
                or (row["status"] != "completed" and count != 0)
                or type(row["sequence"]) is not int or row["sequence"] < 0
                or (count > 0 and (row["first_ordinal"] != 0 or row["last_ordinal"] != count - 1))):
            inconsistent()
        result[ref] = row
    return result


def _receipt_manifest(row, result, candidates):
    if (row["state"] not in TERMINAL_STATES or row["receipt_state"] != row["state"] or result.get("state") != row["state"]
            or row["recorded_at"] != row["finished_at"]):
        inconsistent()
    succeeded = row["state"] in ("complete", "partial")
    manifest = result.get("candidates")
    if (result.get("result_persisted") is not succeeded or type(manifest) is not list
            or len(manifest) != len(candidates) or bool(candidates) is not succeeded):
        inconsistent()
    return succeeded, manifest


def _manifest_candidates(manifest, candidates):
    seen = set()
    for item in manifest:
        if type(item) is not dict:
            inconsistent()
        ref = _ref(item.get("candidate_ref"))
        actual = candidates.get(ref)
        if (ref in seen or actual is None or type(item.get("task_count")) is not int
                or item["task_count"] != actual["task_count"] or item.get("status") != actual["status"]):
            inconsistent()
        seen.add(ref)


def _manifest(row, candidates):
    if row["result_json"] is None:
        if row["state"] in TERMINAL_STATES or candidates or row["receipt_state"] is not None:
            inconsistent()
        return None
    result = stored_json(row["result_json"])
    succeeded, manifest = _receipt_manifest(row, result, candidates)
    _manifest_candidates(manifest, candidates)
    if succeeded and not any(item["status"] == "completed" for item in candidates.values()):
        inconsistent()
    return result


def _stored_error(row, result):
    error = result.get("error") if result is not None and row["state"] in ("failed", "interrupted") else None
    if type(error) is dict and all(type(error.get(key)) is str and error[key] for key in ("code", "message")):
        return error
    return None


def _failure(row, result):
    """失败或中断的排产给出原因；读不出原因时不编造，留空。"""
    error = _stored_error(row, result)
    if error is None:
        return None
    message = error["message"]
    if message == _LEGACY_FAILURE:
        # 旧记录：只取当时本来就写给用户看的业务原因，其他异常原文不外露。
        diagnostic = result.get("diagnostic") if type(result.get("diagnostic")) is dict else {}
        written = diagnostic.get("exception_type") in ("CandidateRunInputError", "WorkbenchCommandRejected")
        message = failure_message(error["code"], diagnostic.get("message") if written else None)
    return {"code": error["code"], "message": message}


def _gap(field, value):
    return {"field": field, "code": "not_recorded" if value is None else "invalid_stored_value",
            "message": "排产时未记录此项。"}


def _scope_value_valid(key, value):
    if key == "hold_window":
        return stored_hold_window_valid(value)
    domains = {"missing_resource_policy": ("auto_assign", "exclude"), "completed_policy": ("preserve_actuals",), "material_strategy": ("strict", "stage", "split")}
    if key in domains:
        return type(value) is str and value in domains[key]
    if key == "ready_check":
        return type(value) is bool
    try:
        local_date(value)
        return True
    except (ValueError, TypeError):
        return False


def _scope_batch_count(refs, gaps):
    valid_refs = (type(refs) is list and bool(refs)
                  and all(type(ref) is str and re.fullmatch(r"[0-9a-f]{48}", ref) is not None for ref in refs))
    count = None
    if valid_refs and type(refs) is list:
        if len(set(refs)) != len(refs):
            inconsistent()
        count = len(refs)
    if not valid_refs:
        gaps.append(_gap("batch_count", refs))
    return count


def scope_summary(raw):
    settings, result, gaps = stored_json(raw), {}, []
    optional = tuple(key for key in ("material_strategy", "hold_window") if key in settings)
    for key in ("start_date", "end_date", "ready_check", "missing_resource_policy", "completed_policy") + optional:
        value = settings.get(key)
        valid = _scope_value_valid(key, value)
        result[key] = value if valid else None
        if not valid:
            gaps.append(_gap(key, value))
    if result["start_date"] is not None and result["end_date"] is not None and result["start_date"] > result["end_date"]:
        inconsistent()
    result["batch_count"] = _scope_batch_count(settings.get("batch_refs"), gaps)
    return {**result, "selection": "explicit_batches", "basis": "captured_at_run_admission", "data_gaps": gaps}


def public_run(row, rows):
    _job(row)
    candidates = _candidates(rows)
    result = _manifest(row, candidates)
    pending = row["stage"] == "awaiting_reconciliation"
    return {"run_ref": row["run_ref"], "state": row["state"], "stage": row["stage"],
            "accepted_at": row["accepted_at"], "started_at": row["started_at"], "finished_at": row["finished_at"],
            "candidate_count": len(candidates), "task_count": sum(item["task_count"] for item in rows),
            "task_count_basis": "persisted_rows_across_candidates", "counts_final": row["state"] in TERMINAL_STATES,
            "scope_summary": scope_summary(row["normalized_input_json"]), "recovery_required": pending,
            "recovery_reason": {"code": "awaiting_reconciliation", "message": "运行状态待核对，本次读取未恢复或重跑。"} if pending else None,
            "error": _failure(row, result),
            "completion_semantics": "execution_state_only", "constraint_verification": "not_checked_by_history",
            "task_content_verification": "candidate_workspace_required"}
