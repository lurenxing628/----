from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, cast

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.quality_gate_ledger import load_ledger  # noqa: E402
from tools.quality_gate_shared import (  # noqa: E402
    FORMAL_FULL_TEST_PYTEST_ARGS,
    FULL_TEST_DEBT_ALLOWED_ACTIVE_XFAIL_NODEIDS,
    QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL,
    QualityGateError,
    is_xfail_signal_report,
)
from tools.test_debt_registry import (  # noqa: E402
    _format_nodeid_list,
    validate_clean_worktree_proof,
    validate_full_test_proof,
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


def _short_text_summary(text: str, *, max_lines: int = 20, max_chars: int = 2000) -> str:
    if not text:
        return "<空>"
    lines = text.splitlines()
    rendered = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        rendered += f"\n... 另外 {len(lines) - max_lines} 行未显示"
    if len(rendered) > max_chars:
        rendered = rendered[:max_chars] + "...<截断>"
    return rendered


def _progress(message: str) -> None:
    print(f"[full-test-debt] {message}", file=sys.stderr, flush=True)


def parse_collector_payload(stdout: str, stderr: str) -> Dict[str, Any]:
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


def _unique_values(values: Sequence[Any]) -> List[Any]:
    out: List[Any] = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def _collect_report_maps(
    reports: Sequence[Dict[str, Any]],
) -> Tuple[
    Dict[str, List[str]],
    Dict[str, List[bool]],
    Dict[str, List[bool]],
    Dict[str, List[str]],
]:
    marker_reasons_by_nodeid: Dict[str, List[str]] = {}
    marker_strict_by_nodeid: Dict[str, List[bool]] = {}
    marker_run_by_nodeid: Dict[str, List[bool]] = {}
    wasxfail_reasons_by_nodeid: Dict[str, List[str]] = {}
    for report in reports:
        nodeid = report["nodeid"]
        if report["xfail_marker_present"]:
            marker_run_by_nodeid.setdefault(nodeid, []).append(report["xfail_marker_run"])
        if report["xfail_marker_reason"]:
            marker_reasons_by_nodeid.setdefault(nodeid, []).append(report["xfail_marker_reason"])
            marker_strict_by_nodeid.setdefault(nodeid, []).append(report["xfail_marker_strict"])
        if report["wasxfail_reason"]:
            wasxfail_reasons_by_nodeid.setdefault(nodeid, []).append(report["wasxfail_reason"])
    return (
        marker_reasons_by_nodeid,
        marker_strict_by_nodeid,
        marker_run_by_nodeid,
        wasxfail_reasons_by_nodeid,
    )


def _validate_active_entries(
    active_entries: Sequence[Dict[str, Any]],
    *,
    collected: Set[str],
    marker_reasons_by_nodeid: Dict[str, List[str]],
    marker_strict_by_nodeid: Dict[str, List[bool]],
    marker_run_by_nodeid: Dict[str, List[bool]],
    wasxfail_reasons_by_nodeid: Dict[str, List[str]],
) -> List[str]:
    errors: List[str] = []
    for entry in active_entries:
        nodeid = entry["nodeid"]
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
    collected: Set[str],
    reports: Sequence[Dict[str, Any]],
    xfail_signal_nodeids: Sequence[str],
) -> List[str]:
    passed_call_nodeids = {
        report["nodeid"] for report in reports if report["when"] == "call" and report["outcome"] == "passed"
    }
    errors: List[str] = []
    for entry in fixed_entries:
        nodeid = entry["nodeid"]
        if nodeid not in collected:
            errors.append(f"fixed 测试债务未被 collect：{nodeid}")
        if nodeid not in passed_call_nodeids:
            errors.append(f"fixed 测试债务没有普通通过报告：{nodeid}")
        if nodeid in xfail_signal_nodeids:
            errors.append(f"fixed 测试债务仍被 xfail 标记：{nodeid}")
    return errors


def _validate_no_unregistered_xfails(
    xfail_signal_nodeids: Sequence[str],
    *,
    active_entries: Sequence[Dict[str, Any]],
) -> List[str]:
    registered_active_nodeids = {entry["nodeid"] for entry in active_entries}
    return [
        f"未登记 xfail 出现在 proof 报告：{nodeid}"
        for nodeid in xfail_signal_nodeids
        if nodeid not in registered_active_nodeids
    ]


def _validate_historical_debt_entries_present(entries: Sequence[Dict[str, Any]]) -> List[str]:
    missing = sorted(set(FULL_TEST_DEBT_ALLOWED_ACTIVE_XFAIL_NODEIDS) - {entry["nodeid"] for entry in entries})
    if not missing:
        return []
    return ["历史 full pytest 测试债务缺少 xfail/fixed/retired 登记：" + _format_nodeid_list(missing)]


def build_full_test_debt_summary(
    payload: Dict[str, Any],
    *,
    ledger: Dict[str, Any],
    require_clean_worktree_proof: bool,
) -> Dict[str, Any]:
    """payload 由 validate_full_test_proof 一次准入；ledger 必须来自 load_ledger（已排序、已校验）。"""
    validate_full_test_proof(payload)
    if require_clean_worktree_proof:
        validate_clean_worktree_proof(payload)
    collected_nodeids = payload["collected_nodeids"]
    collected = set(collected_nodeids)

    test_debt = ledger["test_debt"]
    entries = test_debt["entries"]
    active_entries = [entry for entry in entries if entry["mode"] == "xfail"]
    fixed_entries = [entry for entry in entries if entry["mode"] == "fixed"]
    retired_count = sum(1 for entry in entries if entry["mode"] == "retired")
    reports = payload["reports"]
    xfail_signal_nodeids = list(dict.fromkeys(report["nodeid"] for report in reports if is_xfail_signal_report(report)))
    (
        marker_reasons_by_nodeid,
        marker_strict_by_nodeid,
        marker_run_by_nodeid,
        wasxfail_reasons_by_nodeid,
    ) = _collect_report_maps(reports)
    errors = []
    errors.extend(_validate_no_unregistered_xfails(xfail_signal_nodeids, active_entries=active_entries))
    errors.extend(_validate_historical_debt_entries_present(entries))
    errors.extend(
        _validate_active_entries(
            active_entries,
            collected=collected,
            marker_reasons_by_nodeid=marker_reasons_by_nodeid,
            marker_strict_by_nodeid=marker_strict_by_nodeid,
            marker_run_by_nodeid=marker_run_by_nodeid,
            wasxfail_reasons_by_nodeid=wasxfail_reasons_by_nodeid,
        )
    )
    errors.extend(
        _validate_fixed_entries(
            fixed_entries,
            collected=collected,
            reports=reports,
            xfail_signal_nodeids=xfail_signal_nodeids,
        )
    )
    if errors:
        raise QualityGateError("full-test-debt proof 失败：" + "; ".join(errors))

    active_summary = [
        {"debt_id": entry["debt_id"], "nodeid": entry["nodeid"], "reason": entry["reason"]}
        for entry in active_entries
    ]
    return {
        "schema_version": CHECK_SCHEMA_VERSION,
        "status": "passed",
        "active_xfail_count": len(active_entries),
        "collected_count": len(collected_nodeids),
        "collection_error_count": 0,
        "fixed_count": len(fixed_entries),
        "retired_count": retired_count,
        "max_registered_xfail": test_debt["ratchet"]["max_registered_xfail"],
        "unexpected_failure_count": 0,
        "active_xfail_entries": active_summary,
    }


def _resolve_shard_options(
    *,
    sharded: Optional[bool],
    shard_count: Optional[int],
) -> Tuple[bool, str]:
    resolved_sharded = os.environ.get("APS_FULL_TEST_DEBT_SHARDED") == "1" if sharded is None else sharded
    resolved_shard_count = (
        str(shard_count) if shard_count is not None else os.environ.get("APS_FULL_TEST_DEBT_SHARD_COUNT") or "3"
    )
    return resolved_sharded, resolved_shard_count


def collect_current_payload(
    *,
    sharded: Optional[bool],
    shard_count: Optional[int],
) -> Dict[str, Any]:
    collector_args = list(COLLECTOR_ARGS)
    collector_display = COLLECTOR_DISPLAY
    resolved_sharded, resolved_shard_count = _resolve_shard_options(sharded=sharded, shard_count=shard_count)
    if resolved_sharded:
        collector_args = [
            "tools/collect_full_test_debt.py",
            "--baseline-kind",
            "after_main_style_isolation",
            "--sharded",
            "--shard-count",
            resolved_shard_count,
            "--",
            *FORMAL_FULL_TEST_PYTEST_ARGS,
        ]
        collector_display = (
            "python tools/collect_full_test_debt.py --baseline-kind after_main_style_isolation "
            f"--sharded --shard-count {resolved_shard_count} -- tests -q --tb=short -ra -p no:cacheprovider"
        )
    _progress(f"开始收集 full pytest 结果：{collector_display}")
    stderr_chunks: List[str] = []

    def pump_stderr(stream) -> None:
        try:
            for chunk in iter(stream.readline, ""):
                stderr_chunks.append(chunk)
                print(chunk, end="", file=sys.stderr, flush=True)
        finally:
            stream.close()

    process = subprocess.Popen(
        [sys.executable, *collector_args],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    stderr_thread = threading.Thread(target=pump_stderr, args=(process.stderr,), daemon=True)
    stderr_thread.start()
    stdout = process.stdout.read()
    returncode = process.wait()
    stderr_thread.join()
    stderr = "".join(stderr_chunks)
    _progress("collector 已结束，正在解析 current payload JSON")

    payload = parse_collector_payload(stdout, stderr)
    # exitstatus 的类型准入归紧随其后的 validate_full_test_proof；这里只比对进程返回码。
    payload_exitstatus = payload.get("exitstatus")
    if payload_exitstatus != returncode:
        raise QualityGateError(
            f"collector returncode 与 payload.exitstatus 不一致：returncode={returncode} exitstatus={payload_exitstatus}；"
            f"stdout 摘要：{_short_text_summary(stdout)}；"
            f"stderr 摘要：{_short_text_summary(stderr)}"
        )
    _progress("collector payload 已解析，开始校验测试债务台账")
    return payload


def run_check(
    *,
    require_clean_worktree_proof: bool,
    sharded: Optional[bool],
    shard_count: Optional[int],
) -> Dict[str, Any]:
    _progress("开始加载治理台账")
    ledger = load_ledger(required=True)
    _progress("治理台账已加载")
    payload = collect_current_payload(sharded=sharded, shard_count=shard_count)
    summary = build_full_test_debt_summary(
        payload,
        ledger=ledger,
        require_clean_worktree_proof=require_clean_worktree_proof,
    )
    _progress("full-test-debt proof 校验完成")
    return summary


def write_full_test_debt_summary(summary: Dict[str, Any], *, repo_root: str = REPO_ROOT) -> None:
    _write_json_atomically(QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL, summary, repo_root=repo_root)


def _write_json_atomically(rel_path: str, payload: Dict[str, Any], *, repo_root: str = REPO_ROOT) -> None:
    abs_path = os.path.join(str(repo_root), rel_path.replace("\\", "/").replace("/", os.sep))
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
    parser.add_argument(
        "--sharded",
        action="store_const",
        const=True,
        default=None,
        help="正式 full pytest 收集改用分片模式；未传时仍兼容 APS_FULL_TEST_DEBT_SHARDED",
    )
    parser.add_argument(
        "--shard-count",
        type=int,
        default=None,
        help="分片总数；未传时仍兼容 APS_FULL_TEST_DEBT_SHARD_COUNT，默认 3",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        summary = run_check(
            require_clean_worktree_proof=not args.allow_dirty_worktree_proof,
            sharded=args.sharded,
            shard_count=args.shard_count,
        )
    except QualityGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 2
    write_full_test_debt_summary(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
