"""required 回归核销器（P2 已塌缩证明捆绑层）。

真实语义：full gate 的全量 pytest（full_test_debt）容忍 debt ledger 登记的失败，
本工具从其 payload 核销「required 测试必须全部被收集、全部通过、无 xfail 信号、
无 collection error、且组覆盖完整（required ⊄ debt）」——这层门禁语义不可丢。

历史上本工具还写「父证明 + 8 组子证明」喂给长门禁缓存跳跑（~400 行证明机器，
schema v4 + 组级 proof bundle）。P2 治理将缓存复用退化为纯指纹判定（组 scope
并集指纹由 long_gate_manifest/fingerprint 维护），证明捆绑系统整体退役：
本工具塌缩为纯核销 CLI——读 payload → 核销 → 打印摘要，不再写任何文件；
required_regressions.json 成功凭证由 run_quality_gate 统一落盘。

payload 由 test_debt_registry.validate_full_test_proof 统一准入：机器契约（终态报告、
teardown 等）之上要求 exitstatus == 0、collected_nodeids 非空、三类分类与
collection_errors 全空。本工具只在其上核销 required 回归自身的业务规则（os_name、
required 文件覆盖、非通过与 xfail 信号拒绝、group 覆盖）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools import quality_gate_shared  # noqa: E402
from tools.test_debt_registry import validate_full_test_proof  # noqa: E402
from tools.test_registry import (  # noqa: E402
    iter_required_tests,
    validate_test_registry,
)

CURRENT_FULL_TEST_DEBT_REL = quality_gate_shared.QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL.replace("\\", "/")
DEFAULT_COMMAND = "python tools/verify_required_regressions_from_full_test_debt.py"


class RequiredRegressionProofError(ValueError):
    pass


def _repo_rel_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    if os.path.isabs(normalized):
        real_path = os.path.realpath(normalized)
        real_root = os.path.realpath(REPO_ROOT)
        if real_path == real_root or real_path.startswith(real_root + os.sep):
            return os.path.relpath(real_path, real_root).replace("\\", "/")
        return normalized
    return normalized


def _abs_repo_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    if os.path.isabs(normalized):
        return normalized
    return os.path.join(REPO_ROOT, normalized.replace("/", os.sep))


def _load_json_object(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RequiredRegressionProofError(f"{_repo_rel_path(path)} 顶层必须是 JSON 对象")
    return payload


def _nodeid_path(nodeid: str) -> str:
    return nodeid.split("::", 1)[0]


def _required_nodeids_by_path(collected_nodeids: Sequence[str], required_paths: Sequence[str]) -> Dict[str, List[str]]:
    required_set = set(required_paths)
    rows: Dict[str, List[str]] = {path: [] for path in required_paths}
    for nodeid in collected_nodeids:
        node_path = _nodeid_path(nodeid)
        if node_path in required_set:
            rows[node_path].append(nodeid)
    return rows


def _group_rows_for_required_paths(
    required_paths: Sequence[str],
    *,
    required_groups: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    try:
        return validate_test_registry(
            REPO_ROOT,
            required_paths=required_paths,
            groups=required_groups,
        )
    except ValueError as exc:
        raise RequiredRegressionProofError(str(exc)) from exc


def verify_required_regressions_from_payload(
    payload: Dict[str, Any],
    *,
    required_tests: Optional[Sequence[str]] = None,
    required_groups: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    validate_full_test_proof(payload)
    payload_os_name = payload.get("os_name")
    if not isinstance(payload_os_name, str) or not payload_os_name:
        raise RequiredRegressionProofError("full-test-debt payload 缺少 os_name")
    required_paths = (
        iter_required_tests(required_tests)
        if required_tests is not None
        else quality_gate_shared.iter_quality_gate_required_tests()
    )
    if not required_paths:
        raise RequiredRegressionProofError("required tests 列表为空")

    collected_nodeids = payload["collected_nodeids"]
    reports = payload["reports"]

    nodeids_by_path = _required_nodeids_by_path(collected_nodeids, required_paths)
    missing_paths = [path for path in required_paths if not nodeids_by_path[path]]
    if missing_paths:
        raise RequiredRegressionProofError("required 文件没有被 full-test-debt 覆盖：" + ", ".join(missing_paths))

    required_nodeids = sorted({nodeid for nodeids in nodeids_by_path.values() for nodeid in nodeids})
    required_nodeid_set = set(required_nodeids)
    reports_by_nodeid: Dict[str, List[Dict[str, Any]]] = {nodeid: [] for nodeid in required_nodeids}
    for report in reports:
        nodeid = report["nodeid"]
        if nodeid in required_nodeid_set:
            reports_by_nodeid[nodeid].append(report)

    allowed_skipped_platforms = quality_gate_shared.REQUIRED_REGRESSION_ALLOWED_SKIPPED_PLATFORMS
    bad_reports: List[str] = []
    xfail_reports: List[str] = []
    for nodeid in required_nodeids:
        for report in reports_by_nodeid[nodeid]:
            when = report["when"]
            outcome = report["outcome"]
            # 仅白名单内 nodeid 在对应平台的 skipped 视为可接受；
            # 其余非 passed（failed/error，或未登记/非平台合法的 skipped）一律视为非通过，守卫不放水。
            if outcome == "passed":
                pass
            elif outcome == "skipped" and payload_os_name in allowed_skipped_platforms.get(nodeid, set()):
                pass
            else:
                bad_reports.append(f"{nodeid} [{when}:{outcome}]")
            if quality_gate_shared.is_xfail_signal_report(report):
                xfail_reports.append(f"{nodeid} [{when}]")
    if bad_reports:
        raise RequiredRegressionProofError("required nodeid 存在非通过 reports：" + ", ".join(bad_reports[:20]))
    if xfail_reports:
        raise RequiredRegressionProofError("required nodeid 存在 xfail 信号：" + ", ".join(xfail_reports[:20]))

    group_coverage = _group_rows_for_required_paths(
        required_paths,
        required_groups=required_groups,
    )

    return {
        "required_target_paths": required_paths,
        "required_nodeids": required_nodeids,
        "required_reports": {nodeid: reports_by_nodeid[nodeid] for nodeid in required_nodeids},
        "required_nodeid_count_by_path": {path: len(nodeids_by_path[path]) for path in required_paths},
        "group_coverage": group_coverage,
        "collected_count": len(collected_nodeids),
        "report_count": len(reports),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify required regressions from current full-test-debt payload without rerunning pytest.",
    )
    parser.add_argument("--payload", default=CURRENT_FULL_TEST_DEBT_REL)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    payload_path = _abs_repo_path(str(args.payload))
    try:
        source_payload = _load_json_object(payload_path)
        verification = verify_required_regressions_from_payload(source_payload)
        output_line = (
            "required_regressions verified "
            f"targets={len(verification['required_target_paths'])} "
            f"nodeids={len(verification['required_nodeids'])}\n"
        )
    except (OSError, ValueError, RequiredRegressionProofError, quality_gate_shared.QualityGateError) as exc:
        print(f"required_regressions verification failed: {exc}", file=sys.stderr, flush=True)
        return 1
    print(output_line, end="", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
