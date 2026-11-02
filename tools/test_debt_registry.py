from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, cast

from .quality_gate_ledger import finalize_ledger_update, load_ledger
from .quality_gate_shared import (
    FORMAL_FULL_TEST_PYTEST_ARGS,
    QualityGateError,
    is_teardown_failure_report,
    is_terminal_pytest_report,
)

BASELINE_SCHEMA_VERSION = 2
BASELINE_CLASSIFICATION_KEYS = (
    "candidate_test_debt",
    "main_style_isolation_candidate",
    "required_or_quality_gate_self_failure",
)
BASELINE_REQUIRED_REPORT_FIELDS = (
    "nodeid",
    "when",
    "outcome",
    "xfail_marker_present",
    "xfail_marker_reason",
    "xfail_marker_strict",
    "xfail_marker_run",
    "wasxfail_reason",
    "strict_xpass",
)


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QualityGateError(f"{field_name} 必须是非空字符串")
    text = value.strip()
    if text.lower() == "untriaged":
        raise QualityGateError(f"{field_name} 不允许写 untriaged 占位")
    return text


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise QualityGateError(f"{field_name} 必须是字符串")
    return value


def _require_plain_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise QualityGateError(f"{field_name} 必须是整数")
    return value


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise QualityGateError(f"{field_name} 必须是布尔值")
    return value


def _require_dict(value: Any, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise QualityGateError(f"{field_name} 必须是对象")
    return cast(Dict[str, Any], value)


def _require_list(value: Any, field_name: str) -> List[Any]:
    if not isinstance(value, list):
        raise QualityGateError(f"{field_name} 必须是列表")
    return value


def _require_string_list(value: Any, field_name: str, *, allow_empty: bool = True) -> List[str]:
    raw_values = _require_list(value, field_name)
    for raw_value in raw_values:
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise QualityGateError(f"{field_name} 必须只包含非空字符串")
    if not allow_empty and not raw_values:
        raise QualityGateError(f"{field_name} 不能为空")
    return cast(List[str], raw_values)


def _validate_baseline_classifications(payload: Dict[str, Any]) -> Dict[str, List[str]]:
    classifications = _require_dict(payload.get("classifications"), "classifications")
    if set(classifications) != set(BASELINE_CLASSIFICATION_KEYS):
        raise QualityGateError("classifications 必须精确包含三类测试债务分类")
    return {key: _require_string_list(classifications[key], key) for key in BASELINE_CLASSIFICATION_KEYS}


def _validate_baseline_summary(
    payload: Dict[str, Any],
    classification_lists: Dict[str, List[str]],
    collection_errors: List[Any],
) -> None:
    summary = _require_dict(payload.get("summary"), "summary")
    counts = _require_dict(summary.get("classification_counts"), "classification_counts")
    if set(counts) != set(BASELINE_CLASSIFICATION_KEYS):
        raise QualityGateError("classification_counts 必须精确包含三类测试债务分类")
    for key in BASELINE_CLASSIFICATION_KEYS:
        count = _require_plain_int(counts[key], key)
        if count != len(classification_lists[key]):
            raise QualityGateError(f"{key} 统计数与实际列表不一致")
    failed_nodeid_count = _require_plain_int(summary.get("failed_nodeid_count"), "failed_nodeid_count")
    collection_error_count = _require_plain_int(summary.get("collection_error_count"), "collection_error_count")
    if collection_error_count != len(collection_errors):
        raise QualityGateError("collection_error_count 与 collection_errors 数量不一致")
    expected_failed_nodeid_count = sum(len(values) for values in classification_lists.values()) + collection_error_count
    if failed_nodeid_count != expected_failed_nodeid_count:
        raise QualityGateError("failed_nodeid_count 与分类列表和 collection_errors 总数不一致")
    outcome_counts = _require_dict(summary.get("outcome_counts"), "outcome_counts")
    for key, value in outcome_counts.items():
        _require_text(key, "outcome_counts.key")
        _require_plain_int(value, f"outcome_counts.{key}")


def _validate_baseline_reports(
    payload: Dict[str, Any],
    collected_nodeids: Sequence[str],
    classification_lists: Dict[str, List[str]],
) -> None:
    collected_set = set(collected_nodeids)
    report_nodeids: Set[str] = set()
    terminal_report_nodeids: Set[str] = set()
    failed_report_nodeids: Set[str] = set()
    teardown_failed_nodeids: Set[str] = set()
    for index, raw_report in enumerate(_require_list(payload.get("reports"), "reports")):
        report = _require_dict(raw_report, f"reports[{index}]")
        for field_name in BASELINE_REQUIRED_REPORT_FIELDS:
            if field_name not in report:
                raise QualityGateError(f"reports[{index}] 缺少字段 {field_name}")
        nodeid = _require_text(report.get("nodeid"), f"reports[{index}].nodeid")
        report_nodeids.add(nodeid)
        when = _require_text(report.get("when"), f"reports[{index}].when")
        outcome = _require_text(report.get("outcome"), f"reports[{index}].outcome")
        if is_terminal_pytest_report(when, outcome):
            terminal_report_nodeids.add(nodeid)
        if outcome == "failed":
            failed_report_nodeids.add(nodeid)
            if is_teardown_failure_report(when, outcome):
                teardown_failed_nodeids.add(nodeid)
        _require_bool(report.get("xfail_marker_present"), f"reports[{index}].xfail_marker_present")
        _require_string(report.get("xfail_marker_reason"), f"reports[{index}].xfail_marker_reason")
        _require_bool(report.get("xfail_marker_strict"), f"reports[{index}].xfail_marker_strict")
        _require_bool(report.get("xfail_marker_run"), f"reports[{index}].xfail_marker_run")
        _require_string(report.get("wasxfail_reason"), f"reports[{index}].wasxfail_reason")
        _require_bool(report.get("strict_xpass"), f"reports[{index}].strict_xpass")
    uncollected_reports = sorted(report_nodeids - collected_set)
    if uncollected_reports:
        raise QualityGateError(
            "reports 存在未出现在 collected_nodeids 中的 nodeid："
            + _format_nodeid_list(uncollected_reports)
        )
    missing_terminal_reports = [nodeid for nodeid in collected_nodeids if nodeid not in terminal_report_nodeids]
    if missing_terminal_reports:
        raise QualityGateError(
            "collected_nodeids 每个 nodeid 都必须有合法的 pytest 终态报告，缺少："
            + _format_nodeid_list(missing_terminal_reports)
        )
    if teardown_failed_nodeids:
        raise QualityGateError(
            "reports 存在 teardown 失败，不能通过测试债务证明："
            + _format_nodeid_list(sorted(teardown_failed_nodeids))
        )
    candidate_nodeids = set(classification_lists["candidate_test_debt"])
    classified_failed_nodeids = {nodeid for values in classification_lists.values() for nodeid in values}
    missing_reports = sorted(candidate_nodeids - report_nodeids)
    if missing_reports:
        raise QualityGateError(
            "candidate_test_debt 每个 nodeid 都必须有失败报告 reports 明细，缺少："
            + _format_nodeid_list(missing_reports)
        )
    missing_failed_reports = sorted(candidate_nodeids - failed_report_nodeids)
    if missing_failed_reports:
        raise QualityGateError(
            "candidate_test_debt 每个 nodeid 都必须有 outcome=failed 的 reports 证据，缺少："
            + _format_nodeid_list(missing_failed_reports)
        )
    unclassified_failed_reports = sorted(failed_report_nodeids - classified_failed_nodeids)
    if unclassified_failed_reports:
        raise QualityGateError(
            "reports 存在未纳入 classifications 的失败 nodeid："
            + _format_nodeid_list(unclassified_failed_reports)
        )


def validate_clean_worktree_proof(payload: Dict[str, Any]) -> None:
    """收集器写入的干净工作区证明，只接受 worktree_clean_before 为 True 且 git_status_short_before 为 []。

    两个字段不在非导入的机器契约里，这里是唯一的读取边界；严格比较本身已拒绝缺失、None 和错类型。
    """
    if payload.get("worktree_clean_before") is not True:
        raise QualityGateError("worktree_clean_before 必须为 true")
    if payload.get("git_status_short_before") != []:
        raise QualityGateError("git_status_short_before 必须为空")


def _validate_formal_full_test_args(payload: Dict[str, Any]) -> None:
    pytest_args = _require_string_list(payload.get("pytest_args"), "pytest_args", allow_empty=False)
    if pytest_args != FORMAL_FULL_TEST_PYTEST_ARGS:
        raise QualityGateError(
            "pytest_args 必须是正式 full pytest 参数："
            + " ".join(FORMAL_FULL_TEST_PYTEST_ARGS)
            + "；实际："
            + " ".join(pytest_args)
        )


def _validate_baseline_machine_contract(payload: Dict[str, Any]) -> None:
    schema_version = _require_plain_int(payload.get("schema_version"), "schema_version")
    if schema_version != BASELINE_SCHEMA_VERSION:
        raise QualityGateError(f"schema_version 必须等于 {BASELINE_SCHEMA_VERSION}")
    if payload.get("baseline_kind") != "after_main_style_isolation":
        raise QualityGateError("baseline_kind 必须是 after_main_style_isolation")
    importable = _require_bool(payload.get("importable"), "importable")
    if importable is not False:
        raise QualityGateError("importable 与当前导入口径不一致")
    _require_plain_int(payload.get("exitstatus"), "exitstatus")
    _validate_formal_full_test_args(payload)
    collected_nodeids = _require_string_list(payload.get("collected_nodeids"), "collected_nodeids")
    collection_errors = _require_list(payload.get("collection_errors"), "collection_errors")
    _require_string_list(payload.get("importable_blockers"), "importable_blockers")
    classification_lists = _validate_baseline_classifications(payload)
    _validate_baseline_reports(payload, collected_nodeids, classification_lists)
    _validate_baseline_summary(payload, classification_lists, collection_errors)


def _format_nodeid_list(values: Sequence[Any], *, limit: int = 20) -> str:
    nodeids = [str(value) for value in values]
    visible = nodeids[:limit]
    parts = [f"\n  - {nodeid}" for nodeid in visible]
    hidden_count = len(nodeids) - len(visible)
    if hidden_count > 0:
        parts.append(f"\n  - ... 另外 {hidden_count} 个未显示")
    return "".join(parts)


def _format_collection_error_items(values: Sequence[Any], *, limit: int = 20) -> str:
    visible = list(values)[:limit]
    parts = []
    for item in visible:
        if isinstance(item, dict):
            nodeid = str(item.get("nodeid") or "<unknown>")
            outcome = str(item.get("outcome") or "")
            longrepr_first_line = next(
                (line.strip() for line in str(item.get("longrepr") or "").splitlines() if line.strip()),
                "",
            )
            row = [nodeid]
            if outcome:
                row.append(outcome)
            if longrepr_first_line:
                row.append(longrepr_first_line)
            parts.append("\n  - " + " | ".join(row))
        else:
            parts.append(f"\n  - {item}")
    hidden_count = len(values) - len(visible)
    if hidden_count > 0:
        parts.append(f"\n  - ... 另外 {hidden_count} 个未显示")
    return "".join(parts)


def _count_or_actual_blocker(payload: Dict[str, Any], key: str) -> Optional[str]:
    nodeids = payload["classifications"][key]
    if nodeids:
        return f"{key}（{len(nodeids)} 个）：{_format_nodeid_list(nodeids)}"
    return None


def _collection_error_blocker(payload: Dict[str, Any]) -> Optional[str]:
    errors = payload["collection_errors"]
    if errors:
        return f"collection_errors 非空（{len(errors)} 个）：{_format_collection_error_items(errors)}"
    return None


def validate_full_test_proof(payload: Dict[str, Any]) -> None:
    """check 与 verify 共用的 full pytest 证明。

    机器契约之上要求 exitstatus == 0、collected_nodeids 非空、三类分类与 collection_errors 全空。
    """
    _validate_baseline_machine_contract(payload)
    failures = []
    if payload["exitstatus"] != 0:
        failures.append(f"exitstatus 必须为 0：{payload['exitstatus']}")
    if not payload["collected_nodeids"]:
        failures.append("collected_nodeids 不能为空")
    for key in BASELINE_CLASSIFICATION_KEYS:
        blocker = _count_or_actual_blocker(payload, key)
        if blocker:
            failures.append(blocker)
    collection_blocker = _collection_error_blocker(payload)
    if collection_blocker:
        failures.append(collection_blocker)
    if failures:
        raise QualityGateError("full pytest 证明不成立：" + ", ".join(failures))


def mark_test_debt_fixed(
    ledger: Dict[str, Any],
    debt_id: str,
    *,
    fixed_at: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """ledger 必须来自 load_ledger：debt_id 唯一、条目字段类型已由 validate_ledger 准入。"""
    target_debt_id = _require_text(debt_id, "debt_id")
    matches = [entry for entry in ledger["test_debt"]["entries"] if entry["debt_id"] == target_debt_id]
    if not matches:
        raise QualityGateError(f"测试债务 debt_id 不存在：{target_debt_id}")
    target = matches[0]
    if target["mode"] == "fixed":
        raise QualityGateError(f"测试债务已经是 fixed：{target_debt_id}")
    if target["mode"] != "xfail":
        raise QualityGateError(f"测试债务不是 active xfail：{target_debt_id}")

    next_ledger = copy.deepcopy(ledger)
    test_debt = next_ledger["test_debt"]
    for entry in test_debt["entries"]:
        if entry["debt_id"] == target_debt_id:
            entry["mode"] = "fixed"
            entry["last_verified_at"] = fixed_at
    active_xfail_count = sum(1 for entry in test_debt["entries"] if entry["mode"] == "xfail")
    fixed_count = sum(1 for entry in test_debt["entries"] if entry["mode"] == "fixed")
    previous_max = test_debt["ratchet"]["max_registered_xfail"]
    test_debt["ratchet"]["max_registered_xfail"] = active_xfail_count

    finalized = finalize_ledger_update(next_ledger, current=ledger, updated_at=fixed_at)
    summary = {
        "debt_id": target_debt_id,
        "nodeid": target["nodeid"],
        "previous_max_registered_xfail": previous_max,
        "next_max_registered_xfail": active_xfail_count,
        "active_xfail_count": active_xfail_count,
        "fixed_count": fixed_count,
        "updated_at": finalized["updated_at"],
    }
    return finalized, summary


def retire_test_debt(
    ledger: Dict[str, Any],
    debt_id: str,
    *,
    reason: str,
    retired_at: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Retain a fixed debt's history after its actual test responsibility retires.

    ledger 必须来自 load_ledger；retirement_reason 的 untriaged 占位不在 validate_ledger 范围内，故在这里拒绝。
    """
    target_debt_id = _require_text(debt_id, "debt_id")
    retirement_reason = _require_text(reason, "reason")
    matches = [entry for entry in ledger["test_debt"]["entries"] if entry["debt_id"] == target_debt_id]
    if not matches:
        raise QualityGateError(f"测试债务 debt_id 不存在：{target_debt_id}")
    target = matches[0]
    if target["mode"] != "fixed":
        raise QualityGateError(f"只有 fixed 测试债务可以退役：{target_debt_id}")

    next_ledger = copy.deepcopy(ledger)
    for entry in next_ledger["test_debt"]["entries"]:
        if entry["debt_id"] == target_debt_id:
            entry.update(mode="retired", retired_at=retired_at, retirement_reason=retirement_reason)
    finalized = finalize_ledger_update(next_ledger, current=ledger, updated_at=retired_at)
    return finalized, {
        "debt_id": target_debt_id,
        "nodeid": target["nodeid"],
        "mode": "retired",
        "retired_at": retired_at,
        "retirement_reason": retirement_reason,
    }


def active_xfail_entries_by_nodeid() -> Dict[str, Dict[str, Any]]:
    return {
        entry["nodeid"]: entry
        for entry in load_ledger(required=True)["test_debt"]["entries"]
        if entry["mode"] == "xfail"
    }


__all__ = [
    "active_xfail_entries_by_nodeid",
    "mark_test_debt_fixed",
    "retire_test_debt",
    "validate_clean_worktree_proof",
    "validate_full_test_proof",
]
