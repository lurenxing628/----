from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Sequence, Tuple, cast

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.quality_gate_ledger import load_ledger  # noqa: E402
from tools.quality_gate_shared import QualityGateError, quality_gate_required_test_nodeid_matches  # noqa: E402
from tools.test_debt_registry import (  # noqa: E402
    registered_test_debt_entries,
    validate_current_candidate_payload,
)

CHECK_SCHEMA_VERSION = 1
COLLECTOR_DISPLAY = "python tools/collect_full_test_debt.py --baseline-kind after_main_style_isolation -- tests -q --tb=short -ra -p no:cacheprovider"
COLLECTOR_ARGS = [
    "tools/collect_full_test_debt.py",
    "--baseline-kind",
    "after_main_style_isolation",
    "--",
    "tests",
    "-q",
    "--tb=short",
    "-ra",
    "-p",
    "no:cacheprovider",
]
REPORT_MACHINE_FIELDS = (
    "xfail_marker_reason",
    "xfail_marker_strict",
    "wasxfail_reason",
    "strict_xpass",
)


def parse_collector_payload(stdout: str) -> Dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise QualityGateError(f"collector stdout 不是 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise QualityGateError("collector stdout JSON 顶层必须是对象")
    return cast(Dict[str, Any], payload)


def _require_dict(value: Any, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise QualityGateError(f"{field_name} 必须是对象")
    return cast(Dict[str, Any], value)


def _require_list(value: Any, field_name: str) -> List[Any]:
    if not isinstance(value, list):
        raise QualityGateError(f"{field_name} 必须是列表")
    return list(value)


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise QualityGateError(f"{field_name} 必须是字符串")
    return value


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise QualityGateError(f"{field_name} 必须是布尔值")
    return value


def _require_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise QualityGateError(f"{field_name} 必须是整数")
    return int(value)


def _registered_entries_by_mode(ledger: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    entries = registered_test_debt_entries(ledger)
    active = [entry for entry in entries if str(entry["mode"]) == "xfail"]
    fixed = [entry for entry in entries if str(entry["mode"]) == "fixed"]
    return active, fixed


def _max_registered_xfail(ledger: Dict[str, Any]) -> int:
    test_debt = _require_dict(ledger.get("test_debt"), "test_debt")
    ratchet = _require_dict(test_debt.get("ratchet"), "test_debt.ratchet")
    return _require_int(ratchet.get("max_registered_xfail"), "test_debt.ratchet.max_registered_xfail")


def _reports(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for index, raw_report in enumerate(_require_list(payload.get("reports"), "reports")):
        report = _require_dict(raw_report, f"reports[{index}]")
        for field_name in REPORT_MACHINE_FIELDS:
            if field_name not in report:
                raise QualityGateError(f"reports[{index}] 缺少字段 {field_name}")
        _require_text(report.get("nodeid"), f"reports[{index}].nodeid")
        _require_text(report.get("when"), f"reports[{index}].when")
        _require_text(report.get("outcome"), f"reports[{index}].outcome")
        _require_text(report.get("xfail_marker_reason"), f"reports[{index}].xfail_marker_reason")
        _require_bool(report.get("xfail_marker_strict"), f"reports[{index}].xfail_marker_strict")
        _require_text(report.get("wasxfail_reason"), f"reports[{index}].wasxfail_reason")
        _require_bool(report.get("strict_xpass"), f"reports[{index}].strict_xpass")
        out.append(report)
    return out


def _call_reports(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [report for report in _reports(payload) if str(report["when"]) == "call"]


def _collect_report_maps(
    call_reports: Sequence[Dict[str, Any]],
) -> Tuple[Dict[str, List[str]], Dict[str, List[bool]], Dict[str, List[str]], List[str]]:
    marker_reasons_by_nodeid: Dict[str, List[str]] = {}
    marker_strict_by_nodeid: Dict[str, List[bool]] = {}
    wasxfail_reasons_by_nodeid: Dict[str, List[str]] = {}
    strict_xpass_nodeids: List[str] = []
    for report in call_reports:
        nodeid = str(report["nodeid"])
        marker_reason = str(report["xfail_marker_reason"])
        wasxfail_reason = str(report["wasxfail_reason"])
        if marker_reason:
            marker_reasons_by_nodeid.setdefault(nodeid, []).append(marker_reason)
            marker_strict_by_nodeid.setdefault(nodeid, []).append(bool(report["xfail_marker_strict"]))
        if wasxfail_reason:
            wasxfail_reasons_by_nodeid.setdefault(nodeid, []).append(wasxfail_reason)
        if bool(report["strict_xpass"]):
            strict_xpass_nodeids.append(nodeid)
    return marker_reasons_by_nodeid, marker_strict_by_nodeid, wasxfail_reasons_by_nodeid, sorted(set(strict_xpass_nodeids))


def _classification_errors(payload: Dict[str, Any]) -> List[str]:
    summary = _require_dict(payload.get("summary"), "summary")
    classifications = _require_dict(payload.get("classifications"), "classifications")
    errors: List[str] = []
    collection_error_count = _require_int(summary.get("collection_error_count"), "summary.collection_error_count")
    if collection_error_count != 0 or _require_list(payload.get("collection_errors"), "collection_errors"):
        errors.append("collection_errors 非空")
    for key in [
        "required_or_quality_gate_self_failure",
        "main_style_isolation_candidate",
        "candidate_test_debt",
    ]:
        values = _require_list(classifications.get(key), key)
        if values:
            errors.append(f"{key} 非空")
    return errors


def _validate_active_entries(
    active_entries: Sequence[Dict[str, Any]],
    *,
    collected_nodeids: Sequence[str],
    marker_reasons_by_nodeid: Dict[str, List[str]],
    marker_strict_by_nodeid: Dict[str, List[bool]],
    wasxfail_reasons_by_nodeid: Dict[str, List[str]],
) -> List[str]:
    collected = set(str(nodeid) for nodeid in collected_nodeids)
    errors: List[str] = []
    for entry in active_entries:
        nodeid = str(entry["nodeid"])
        if quality_gate_required_test_nodeid_matches(nodeid):
            errors.append(f"required/proof active xfail: {nodeid}")
        if nodeid not in collected:
            errors.append(f"active xfail nodeid 未被 collect：{nodeid}")
        expected_reason = f"{entry['debt_id']}: {entry['reason']}"
        if marker_reasons_by_nodeid.get(nodeid) != [expected_reason]:
            errors.append(f"xfail marker reason 不一致：{nodeid}")
        if marker_strict_by_nodeid.get(nodeid) != [True]:
            errors.append(f"xfail marker strict 不为 true：{nodeid}")
        if nodeid not in wasxfail_reasons_by_nodeid:
            errors.append(f"xfail reason 缺失：{nodeid}")
            continue
        if wasxfail_reasons_by_nodeid[nodeid] != [expected_reason]:
            errors.append(f"xfail reason 不一致：{nodeid}")
    return errors


def _validate_fixed_entries(
    fixed_entries: Sequence[Dict[str, Any]],
    *,
    marker_reasons_by_nodeid: Dict[str, List[str]],
    wasxfail_reasons_by_nodeid: Dict[str, List[str]],
) -> List[str]:
    errors: List[str] = []
    for entry in fixed_entries:
        nodeid = str(entry["nodeid"])
        if nodeid in marker_reasons_by_nodeid or nodeid in wasxfail_reasons_by_nodeid:
            errors.append(f"fixed 测试债务仍被 xfail 标记：{nodeid}")
    return errors


def build_full_test_debt_summary(payload: Dict[str, Any], *, ledger: Dict[str, Any]) -> Dict[str, Any]:
    validate_current_candidate_payload(payload, expected_nodeids=[])
    exitstatus = _require_int(payload.get("exitstatus"), "exitstatus")
    if exitstatus != 0:
        raise QualityGateError(f"exitstatus 必须为 0：{exitstatus}")
    collected_nodeids = [str(nodeid) for nodeid in _require_list(payload.get("collected_nodeids"), "collected_nodeids")]
    if not collected_nodeids:
        raise QualityGateError("collected_nodeids 不能为空")

    active_entries, fixed_entries = _registered_entries_by_mode(ledger)
    max_registered_xfail = _max_registered_xfail(ledger)
    call_reports = _call_reports(payload)
    marker_reasons_by_nodeid, marker_strict_by_nodeid, wasxfail_reasons_by_nodeid, strict_xpass_nodeids = (
        _collect_report_maps(call_reports)
    )
    errors = []
    errors.extend(_classification_errors(payload))
    errors.extend(
        _validate_active_entries(
            active_entries,
            collected_nodeids=collected_nodeids,
            marker_reasons_by_nodeid=marker_reasons_by_nodeid,
            marker_strict_by_nodeid=marker_strict_by_nodeid,
            wasxfail_reasons_by_nodeid=wasxfail_reasons_by_nodeid,
        )
    )
    errors.extend(
        _validate_fixed_entries(
            fixed_entries,
            marker_reasons_by_nodeid=marker_reasons_by_nodeid,
            wasxfail_reasons_by_nodeid=wasxfail_reasons_by_nodeid,
        )
    )
    if strict_xpass_nodeids:
        errors.append("strict XPASS 非空：" + ", ".join(strict_xpass_nodeids))
    if errors:
        raise QualityGateError("full-test-debt proof 失败：" + "; ".join(errors))

    active_summary = [
        {
            "debt_id": str(entry["debt_id"]),
            "nodeid": str(entry["nodeid"]),
            "reason": str(entry["reason"]),
        }
        for entry in sorted(active_entries, key=lambda item: str(item["nodeid"]))
    ]
    return {
        "schema_version": CHECK_SCHEMA_VERSION,
        "status": "passed",
        "active_xfail_count": len(active_entries),
        "collected_count": len(collected_nodeids),
        "collection_error_count": 0,
        "fixed_count": len(fixed_entries),
        "max_registered_xfail": max_registered_xfail,
        "unexpected_failure_count": 0,
        "active_xfail_entries": active_summary,
    }


def collect_current_payload() -> Dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, *COLLECTOR_ARGS],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if not isinstance(completed.stdout, str):
        raise QualityGateError("collector stdout 必须是字符串")
    payload = parse_collector_payload(completed.stdout)
    payload_exitstatus = _require_int(payload.get("exitstatus"), "collector payload.exitstatus")
    if int(completed.returncode) != int(payload_exitstatus):
        raise QualityGateError(
            f"collector returncode 与 payload.exitstatus 不一致：returncode={completed.returncode} exitstatus={payload_exitstatus}"
        )
    return payload


def run_check() -> Dict[str, Any]:
    ledger = load_ledger(required=True)
    payload = collect_current_payload()
    return build_full_test_debt_summary(payload, ledger=ledger)


def main() -> int:
    try:
        summary = run_check()
    except QualityGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
