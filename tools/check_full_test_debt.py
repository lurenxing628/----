from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.quality_gate_ledger import load_ledger  # noqa: E402
from tools.quality_gate_shared import (  # noqa: E402
    FORMAL_FULL_TEST_PYTEST_ARGS,
    FULL_TEST_DEBT_ALLOWED_ACTIVE_XFAIL_NODEIDS,
    QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL,
    QualityGateError,
    quality_gate_required_test_nodeid_matches,
)
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
    *FORMAL_FULL_TEST_PYTEST_ARGS,
]
REPORT_MACHINE_FIELDS = (
    "xfail_marker_present",
    "xfail_marker_reason",
    "xfail_marker_strict",
    "xfail_marker_run",
    "wasxfail_reason",
    "strict_xpass",
)


def _short_text_summary(text: str, *, max_lines: int = 20, max_chars: int = 2000) -> str:
    raw = str(text or "")
    if not raw:
        return "<空>"
    lines = raw.splitlines()
    rendered = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        rendered += f"\n... 另外 {len(lines) - max_lines} 行未显示"
    if len(rendered) > max_chars:
        rendered = rendered[:max_chars] + "...<截断>"
    return rendered


def _progress(message: str) -> None:
    print(f"[full-test-debt] {message}", file=sys.stderr, flush=True)


def parse_collector_payload(stdout: str, stderr: str = "") -> Dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise QualityGateError(
            f"collector stdout 不是 JSON：{exc}；"
            f"stdout 摘要：{_short_text_summary(stdout)}；"
            f"stderr 摘要：{_short_text_summary(stderr)}"
        ) from exc
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
        _require_bool(report.get("xfail_marker_present"), f"reports[{index}].xfail_marker_present")
        _require_text(report.get("xfail_marker_reason"), f"reports[{index}].xfail_marker_reason")
        _require_bool(report.get("xfail_marker_strict"), f"reports[{index}].xfail_marker_strict")
        _require_bool(report.get("xfail_marker_run"), f"reports[{index}].xfail_marker_run")
        _require_text(report.get("wasxfail_reason"), f"reports[{index}].wasxfail_reason")
        _require_bool(report.get("strict_xpass"), f"reports[{index}].strict_xpass")
        out.append(report)
    return out


def _call_reports(reports: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [report for report in reports if str(report["when"]) == "call"]


def _has_xfail_signal(report: Dict[str, Any]) -> bool:
    return (
        bool(report["xfail_marker_present"])
        or bool(str(report["xfail_marker_reason"]))
        or bool(str(report["wasxfail_reason"]))
    )


def _unique_values(values: Sequence[Any]) -> List[Any]:
    out: List[Any] = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def _collect_report_maps(
    reports: Sequence[Dict[str, Any]],
) -> Tuple[
    Dict[str, List[bool]],
    Dict[str, List[str]],
    Dict[str, List[bool]],
    Dict[str, List[bool]],
    Dict[str, List[str]],
    List[str],
]:
    marker_present_by_nodeid: Dict[str, List[bool]] = {}
    marker_reasons_by_nodeid: Dict[str, List[str]] = {}
    marker_strict_by_nodeid: Dict[str, List[bool]] = {}
    marker_run_by_nodeid: Dict[str, List[bool]] = {}
    wasxfail_reasons_by_nodeid: Dict[str, List[str]] = {}
    strict_xpass_nodeids: List[str] = []
    for report in reports:
        nodeid = str(report["nodeid"])
        marker_reason = str(report["xfail_marker_reason"])
        wasxfail_reason = str(report["wasxfail_reason"])
        if bool(report["xfail_marker_present"]):
            marker_present_by_nodeid.setdefault(nodeid, []).append(True)
            marker_run_by_nodeid.setdefault(nodeid, []).append(bool(report["xfail_marker_run"]))
        if marker_reason:
            marker_reasons_by_nodeid.setdefault(nodeid, []).append(marker_reason)
            marker_strict_by_nodeid.setdefault(nodeid, []).append(bool(report["xfail_marker_strict"]))
            marker_run_by_nodeid.setdefault(nodeid, []).append(bool(report["xfail_marker_run"]))
        if wasxfail_reason:
            wasxfail_reasons_by_nodeid.setdefault(nodeid, []).append(wasxfail_reason)
        if bool(report["strict_xpass"]):
            strict_xpass_nodeids.append(nodeid)
    return (
        marker_present_by_nodeid,
        marker_reasons_by_nodeid,
        marker_strict_by_nodeid,
        marker_run_by_nodeid,
        wasxfail_reasons_by_nodeid,
        sorted(set(strict_xpass_nodeids)),
    )


def _classification_errors(payload: Dict[str, Any]) -> List[str]:
    summary = _require_dict(payload.get("summary"), "summary")
    classifications = _require_dict(payload.get("classifications"), "classifications")
    errors: List[str] = []
    collection_error_count = _require_int(summary.get("collection_error_count"), "summary.collection_error_count")
    collection_errors = _require_list(payload.get("collection_errors"), "collection_errors")
    if collection_error_count != 0 or collection_errors:
        errors.append(_format_collection_errors(collection_errors, collection_error_count=collection_error_count))
    for key in [
        "required_or_quality_gate_self_failure",
        "main_style_isolation_candidate",
        "candidate_test_debt",
    ]:
        values = _require_list(classifications.get(key), key)
        if values:
            errors.append(_format_classification_error(key, values))
    return errors


def _format_nodeid_list(values: Sequence[Any], *, limit: int = 20) -> str:
    nodeids = [str(value) for value in values]
    visible = nodeids[:limit]
    lines = [f"\n  - {nodeid}" for nodeid in visible]
    hidden_count = len(nodeids) - len(visible)
    if hidden_count > 0:
        lines.append(f"\n  - ... 另外 {hidden_count} 个未显示")
    return "".join(lines)


def _format_collection_error_items(values: Sequence[Any], *, limit: int = 20) -> str:
    visible = list(values)[:limit]
    lines = []
    for item in visible:
        if isinstance(item, dict):
            nodeid = str(item.get("nodeid") or "<unknown>")
            outcome = str(item.get("outcome") or "")
            first_longrepr_line = next(
                (line.strip() for line in str(item.get("longrepr") or "").splitlines() if line.strip()),
                "",
            )
            parts = [nodeid]
            if outcome:
                parts.append(outcome)
            if first_longrepr_line:
                parts.append(first_longrepr_line)
            lines.append("\n  - " + " | ".join(parts))
        else:
            lines.append(f"\n  - {item}")
    hidden_count = len(values) - len(visible)
    if hidden_count > 0:
        lines.append(f"\n  - ... 另外 {hidden_count} 个未显示")
    return "".join(lines)


def _format_classification_error(key: str, values: Sequence[Any]) -> str:
    return f"{key} 非空（{len(values)} 个）：{_format_nodeid_list(values)}"


def _format_collection_errors(values: Sequence[Any], *, collection_error_count: int) -> str:
    if not values:
        return f"collection_errors 计数非 0（{collection_error_count} 个），但明细为空"
    return f"collection_errors 非空（{collection_error_count} 个）：{_format_collection_error_items(values)}"


def _validate_active_entries(
    active_entries: Sequence[Dict[str, Any]],
    *,
    collected_nodeids: Sequence[str],
    marker_reasons_by_nodeid: Dict[str, List[str]],
    marker_strict_by_nodeid: Dict[str, List[bool]],
    marker_run_by_nodeid: Dict[str, List[bool]],
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
        if _unique_values(marker_reasons_by_nodeid.get(nodeid, [])) != [expected_reason]:
            errors.append(f"xfail marker reason 不一致：{nodeid}")
        if _unique_values(marker_strict_by_nodeid.get(nodeid, [])) != [True]:
            errors.append(f"xfail marker strict 不为 true：{nodeid}")
        if _unique_values(marker_run_by_nodeid.get(nodeid, [])) != [True]:
            errors.append(f"xfail marker run 不为 true：{nodeid}")
        if nodeid not in wasxfail_reasons_by_nodeid:
            errors.append(f"xfail reason 缺失：{nodeid}")
            continue
        if _unique_values(wasxfail_reasons_by_nodeid[nodeid]) != [expected_reason]:
            errors.append(f"xfail reason 不一致：{nodeid}")
    return errors


def _validate_fixed_entries(
    fixed_entries: Sequence[Dict[str, Any]],
    *,
    collected_nodeids: Sequence[str],
    call_reports: Sequence[Dict[str, Any]],
    marker_present_by_nodeid: Dict[str, List[bool]],
    marker_reasons_by_nodeid: Dict[str, List[str]],
    wasxfail_reasons_by_nodeid: Dict[str, List[str]],
) -> List[str]:
    collected = set(str(nodeid) for nodeid in collected_nodeids)
    call_reports_by_nodeid: Dict[str, List[Dict[str, Any]]] = {}
    for report in call_reports:
        call_reports_by_nodeid.setdefault(str(report["nodeid"]), []).append(report)
    errors: List[str] = []
    for entry in fixed_entries:
        nodeid = str(entry["nodeid"])
        if nodeid not in collected:
            errors.append(f"fixed 测试债务未被 collect：{nodeid}")
        if not any(str(report["outcome"]) == "passed" for report in call_reports_by_nodeid.get(nodeid, [])):
            errors.append(f"fixed 测试债务没有普通通过报告：{nodeid}")
        if (
            nodeid in marker_present_by_nodeid
            or nodeid in marker_reasons_by_nodeid
            or nodeid in wasxfail_reasons_by_nodeid
        ):
            errors.append(f"fixed 测试债务仍被 xfail 标记：{nodeid}")
    return errors


def _validate_no_unregistered_xfails(
    reports: Sequence[Dict[str, Any]],
    *,
    active_entries: Sequence[Dict[str, Any]],
) -> List[str]:
    registered_active_nodeids = {str(entry["nodeid"]) for entry in active_entries}
    errors: List[str] = []
    reported_nodeids = set()
    for report in reports:
        nodeid = str(report["nodeid"])
        if nodeid in registered_active_nodeids or nodeid in reported_nodeids:
            continue
        if _has_xfail_signal(report):
            errors.append(f"未登记 xfail 出现在 proof 报告：{nodeid}")
            reported_nodeids.add(nodeid)
    return errors


def _validate_historical_debt_entries_present(
    collected_nodeids: Sequence[str],
    *,
    active_entries: Sequence[Dict[str, Any]],
    fixed_entries: Sequence[Dict[str, Any]],
    require_all_historical: bool = False,
) -> List[str]:
    registered_nodeids = {str(entry["nodeid"]) for entry in list(active_entries) + list(fixed_entries)}
    historical_nodeids = {str(nodeid) for nodeid in FULL_TEST_DEBT_ALLOWED_ACTIVE_XFAIL_NODEIDS}
    if require_all_historical:
        missing = sorted(historical_nodeids - registered_nodeids)
    else:
        missing = sorted(({str(nodeid) for nodeid in collected_nodeids} & historical_nodeids) - registered_nodeids)
    if not missing:
        return []
    return ["历史 full pytest 测试债务缺少 xfail/fixed 登记：" + _format_nodeid_list(missing)]


def build_full_test_debt_summary(
    payload: Dict[str, Any],
    *,
    ledger: Dict[str, Any],
    require_historical_registry: bool = False,
    require_clean_worktree_proof: bool = False,
) -> Dict[str, Any]:
    validate_current_candidate_payload(payload, expected_nodeids=[])
    if require_clean_worktree_proof:
        if _require_bool(payload.get("worktree_clean_before"), "worktree_clean_before") is not True:
            raise QualityGateError("worktree_clean_before 必须为 true")
        if _require_list(payload.get("git_status_short_before"), "git_status_short_before") != []:
            raise QualityGateError("git_status_short_before 必须为空")
    exitstatus = _require_int(payload.get("exitstatus"), "exitstatus")
    if exitstatus != 0:
        raise QualityGateError(f"exitstatus 必须为 0：{exitstatus}")
    collected_nodeids = [str(nodeid) for nodeid in _require_list(payload.get("collected_nodeids"), "collected_nodeids")]
    if not collected_nodeids:
        raise QualityGateError("collected_nodeids 不能为空")

    active_entries, fixed_entries = _registered_entries_by_mode(ledger)
    max_registered_xfail = _max_registered_xfail(ledger)
    reports = _reports(payload)
    call_reports = _call_reports(reports)
    (
        marker_present_by_nodeid,
        marker_reasons_by_nodeid,
        marker_strict_by_nodeid,
        marker_run_by_nodeid,
        wasxfail_reasons_by_nodeid,
        strict_xpass_nodeids,
    ) = _collect_report_maps(reports)
    errors = []
    errors.extend(_classification_errors(payload))
    errors.extend(_validate_no_unregistered_xfails(reports, active_entries=active_entries))
    errors.extend(
        _validate_historical_debt_entries_present(
            collected_nodeids,
            active_entries=active_entries,
            fixed_entries=fixed_entries,
            require_all_historical=bool(require_historical_registry),
        )
    )
    errors.extend(
        _validate_active_entries(
            active_entries,
            collected_nodeids=collected_nodeids,
            marker_reasons_by_nodeid=marker_reasons_by_nodeid,
            marker_strict_by_nodeid=marker_strict_by_nodeid,
            marker_run_by_nodeid=marker_run_by_nodeid,
            wasxfail_reasons_by_nodeid=wasxfail_reasons_by_nodeid,
        )
    )
    errors.extend(
        _validate_fixed_entries(
            fixed_entries,
            collected_nodeids=collected_nodeids,
            call_reports=call_reports,
            marker_present_by_nodeid=marker_present_by_nodeid,
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
    _progress(f"开始收集 full pytest 结果：{COLLECTOR_DISPLAY}")
    stderr_chunks: List[str] = []

    def pump_stderr(stream) -> None:
        try:
            for chunk in iter(stream.readline, ""):
                stderr_chunks.append(str(chunk))
                print(str(chunk), end="", file=sys.stderr, flush=True)
        finally:
            stream.close()

    process = subprocess.Popen(
        [sys.executable, *COLLECTOR_ARGS],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.stdout is None or process.stderr is None:  # pragma: no cover
        raise QualityGateError("无法捕获 collector stdout/stderr")
    assert process.stdout is not None
    assert process.stderr is not None
    stderr_thread = threading.Thread(target=pump_stderr, args=(process.stderr,), daemon=True)
    stderr_thread.start()
    stdout = process.stdout.read()
    returncode = process.wait()
    stderr_thread.join()
    stderr = "".join(stderr_chunks)
    _progress("collector 已结束，正在解析 current payload JSON")

    if not isinstance(stdout, str):
        raise QualityGateError("collector stdout 必须是字符串")
    payload = parse_collector_payload(stdout, stderr)
    payload_exitstatus = _require_int(payload.get("exitstatus"), "collector payload.exitstatus")
    if int(returncode) != int(payload_exitstatus):
        raise QualityGateError(
            f"collector returncode 与 payload.exitstatus 不一致：returncode={returncode} exitstatus={payload_exitstatus}；"
            f"stdout 摘要：{_short_text_summary(stdout)}；"
            f"stderr 摘要：{_short_text_summary(stderr)}"
        )
    _progress("collector payload 已解析，开始校验测试债务台账")
    return payload


def run_check(*, require_clean_worktree_proof: bool = True) -> Dict[str, Any]:
    _progress("开始加载治理台账")
    ledger = load_ledger(required=True)
    _progress("治理台账已加载")
    payload = collect_current_payload()
    summary = build_full_test_debt_summary(
        payload,
        ledger=ledger,
        require_historical_registry=True,
        require_clean_worktree_proof=bool(require_clean_worktree_proof),
    )
    _progress("full-test-debt proof 校验完成")
    return summary


def _write_json_atomically(rel_path: str, payload: Dict[str, Any]) -> None:
    abs_path = os.path.join(REPO_ROOT, rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    temp_path = f"{abs_path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temp_path, abs_path)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="APS full pytest 测试债务 proof")
    parser.add_argument(
        "--allow-dirty-worktree-proof",
        action="store_true",
        help="仅供 run_quality_gate.py --allow-dirty-worktree 诊断跑使用；不声明 clean worktree proof",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        summary = run_check(require_clean_worktree_proof=not bool(args.allow_dirty_worktree_proof))
    except QualityGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 2
    _write_json_atomically(QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
