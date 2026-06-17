"""required 回归核销器（P2 已塌缩证明捆绑层）。

真实语义：full gate 的全量 pytest（full_test_debt）容忍 debt ledger 登记的失败，
本工具从其 payload 核销「required 测试必须全部被收集、全部通过、无 xfail 信号、
无 collection error、且组覆盖完整（required ⊄ debt）」——这层门禁语义不可丢。

历史上本工具还写「父证明 + 8 组子证明」喂给长门禁缓存跳跑（~400 行证明机器，
schema v4 + 组级 proof bundle）。P2 治理将缓存复用退化为纯指纹判定（组 scope
并集指纹由 long_gate_manifest/fingerprint 维护），证明捆绑系统整体退役：
本工具塌缩为纯核销 CLI——读 payload → 核销 → 打印摘要，不再写任何文件；
required_regressions.json 成功凭证由 run_quality_gate 统一落盘。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools import quality_gate_shared, quality_gate_support  # noqa: E402
from tools.long_gate_schema import stable_json_hash  # noqa: E402

CURRENT_FULL_TEST_DEBT_REL = quality_gate_shared.QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL.replace("\\", "/")
BLOCKING_CLASSIFICATION_KEYS = (
    "required_or_quality_gate_self_failure",
    "main_style_isolation_candidate",
    "candidate_test_debt",
)
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


def _as_list(value: Any, *, field_name: str) -> List[Any]:
    if not isinstance(value, list):
        raise RequiredRegressionProofError(f"{field_name} 必须是列表")
    return list(value)


def _nodeid_path(nodeid: str) -> str:
    return str(nodeid or "").split("::", 1)[0].replace("\\", "/")


def _required_nodeids_by_path(collected_nodeids: Iterable[str], required_paths: Sequence[str]) -> Dict[str, List[str]]:
    required_set = {str(path).replace("\\", "/") for path in required_paths}
    rows: Dict[str, List[str]] = {path: [] for path in required_paths}
    for nodeid in collected_nodeids:
        normalized = str(nodeid or "").strip().replace("\\", "/")
        node_path = _nodeid_path(normalized)
        if node_path in required_set:
            rows[node_path].append(normalized)
    return rows


def _report_has_xfail_signal(report: Mapping[str, Any]) -> bool:
    if bool(report.get("xfail_marker_present")):
        return True
    if bool(report.get("strict_xpass")):
        return True
    for key in ("xfail_marker_reason", "wasxfail_reason"):
        if str(report.get(key) or "").strip():
            return True
    return False


def _collection_error_count(payload: Mapping[str, Any]) -> int:
    if "collection_error_count" in payload:
        return int(payload.get("collection_error_count") or 0)
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise RequiredRegressionProofError("full-test-debt payload 缺少 summary")
    return int(summary.get("collection_error_count") or 0)


def _validate_clean_full_test_debt_payload(payload: Mapping[str, Any]) -> None:
    if "exitstatus" not in payload:
        raise RequiredRegressionProofError("full-test-debt payload 缺少 exitstatus")
    if int(payload.get("exitstatus") or 0) != 0:
        raise RequiredRegressionProofError(f"full-test-debt exitstatus 不是 0：{payload.get('exitstatus')!r}")
    if _collection_error_count(payload) != 0:
        raise RequiredRegressionProofError("full-test-debt collection_error_count 不是 0")

    classifications = payload.get("classifications")
    if not isinstance(classifications, dict):
        raise RequiredRegressionProofError("full-test-debt payload 缺少 classifications")
    for key in BLOCKING_CLASSIFICATION_KEYS:
        values = classifications.get(key)
        if not isinstance(values, list):
            raise RequiredRegressionProofError(f"classifications.{key} 必须是列表")
        if values:
            raise RequiredRegressionProofError(f"classifications.{key} 非空")


def _group_rows_for_required_paths(
    required_paths: Sequence[str],
    *,
    required_tests_were_explicit: bool,
    required_groups: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if required_groups is None and required_tests_were_explicit:
        group_rows = [
            {
                "group_id": "custom_required_regressions",
                "label": "Custom required regressions",
                "target_paths": list(required_paths),
                "input_file_scopes": [],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
                "env_keys": [],
            }
        ]
    else:
        group_rows = quality_gate_support.iter_required_regression_groups(required_groups)

    coverage = quality_gate_support.validate_required_regression_group_coverage(
        required_paths,
        groups=group_rows,
    )
    problems: List[str] = []
    if coverage.get("missing"):
        problems.append("missing=" + ", ".join(str(path) for path in list(coverage.get("missing") or [])))
    if coverage.get("unknown"):
        problems.append("unknown=" + ", ".join(str(path) for path in list(coverage.get("unknown") or [])))
    if coverage.get("duplicates"):
        duplicate_paths = [str(row.get("path") or "") for row in list(coverage.get("duplicates") or []) if isinstance(row, dict)]
        problems.append("duplicates=" + ", ".join(duplicate_paths))
    if problems:
        raise RequiredRegressionProofError("required regression group 覆盖不完整：" + "; ".join(problems))
    return group_rows, coverage


def verify_required_regressions_from_payload(
    payload: Mapping[str, Any],
    *,
    required_tests: Optional[Sequence[str]] = None,
    required_groups: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    _validate_clean_full_test_debt_payload(payload)
    required_tests_were_explicit = required_tests is not None
    required_paths = [
        str(path).replace("\\", "/")
        for path in list(required_tests if required_tests is not None else quality_gate_shared.iter_quality_gate_required_tests())
    ]
    if not required_paths:
        raise RequiredRegressionProofError("required tests 列表为空")

    collected_nodeids = [
        str(nodeid).replace("\\", "/")
        for nodeid in _as_list(payload.get("collected_nodeids"), field_name="collected_nodeids")
        if str(nodeid or "").strip()
    ]
    if not collected_nodeids:
        raise RequiredRegressionProofError("full-test-debt payload 没有 collected_nodeids")

    reports = [
        dict(report)
        for report in _as_list(payload.get("reports"), field_name="reports")
        if isinstance(report, dict)
    ]
    if len(reports) != len(_as_list(payload.get("reports"), field_name="reports")):
        raise RequiredRegressionProofError("reports 每一项都必须是对象")

    nodeids_by_path = _required_nodeids_by_path(collected_nodeids, required_paths)
    missing_paths = [path for path in required_paths if not nodeids_by_path.get(path)]
    if missing_paths:
        raise RequiredRegressionProofError("required 文件没有被 full-test-debt 覆盖：" + ", ".join(missing_paths))

    required_nodeids = sorted({nodeid for nodeids in nodeids_by_path.values() for nodeid in nodeids})
    required_nodeid_set = set(required_nodeids)
    reports_by_nodeid: Dict[str, List[Dict[str, Any]]] = {nodeid: [] for nodeid in required_nodeids}
    for report in reports:
        nodeid = str(report.get("nodeid") or "").replace("\\", "/")
        if nodeid in required_nodeid_set:
            reports_by_nodeid[nodeid].append(report)

    missing_report_nodeids = [nodeid for nodeid in required_nodeids if not reports_by_nodeid.get(nodeid)]
    if missing_report_nodeids:
        raise RequiredRegressionProofError("required nodeid 缺少 reports 明细：" + ", ".join(missing_report_nodeids[:20]))

    allowed_skipped_platforms = {
        str(nodeid): {"nt"} for nodeid in quality_gate_shared.REQUIRED_REGRESSION_ALLOWED_SKIPPED_NODEIDS
    }
    payload_os_name = str(payload.get("os_name") or payload.get("platform_os_name") or os.name)
    bad_reports: List[str] = []
    xfail_reports: List[str] = []
    for nodeid in required_nodeids:
        for report in reports_by_nodeid[nodeid]:
            when = str(report.get("when") or "")
            outcome = str(report.get("outcome") or "")
            # 仅白名单内 nodeid 在对应平台的 skipped 视为可接受；
            # 其余非 passed（failed/error，或未登记/非平台合法的 skipped）一律视为非通过，守卫不放水。
            if outcome == "passed":
                pass
            elif outcome == "skipped" and payload_os_name in allowed_skipped_platforms.get(nodeid, set()):
                pass
            else:
                bad_reports.append(f"{nodeid} [{when or '-'}:{outcome or '-'}]")
            if _report_has_xfail_signal(report):
                xfail_reports.append(f"{nodeid} [{when or '-'}]")
    if bad_reports:
        raise RequiredRegressionProofError("required nodeid 存在非通过 reports：" + ", ".join(bad_reports[:20]))
    if xfail_reports:
        raise RequiredRegressionProofError("required nodeid 存在 xfail 信号：" + ", ".join(xfail_reports[:20]))

    _group_rows, group_coverage = _group_rows_for_required_paths(
        required_paths,
        required_tests_were_explicit=required_tests_were_explicit,
        required_groups=required_groups,
    )

    return {
        "required_target_paths": required_paths,
        "required_target_hash": stable_json_hash(required_paths),
        "required_nodeids": required_nodeids,
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
    except (OSError, ValueError, RequiredRegressionProofError) as exc:
        print(f"required_regressions verification failed: {exc}", file=sys.stderr, flush=True)
        return 1
    print(output_line, end="", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
