from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools import quality_gate_shared  # noqa: E402
from tools.long_gate_manifest import ENTRY_REQUIRED_REGRESSIONS  # noqa: E402
from tools.long_gate_schema import stable_json_hash  # noqa: E402

CURRENT_FULL_TEST_DEBT_REL = quality_gate_shared.QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL.replace("\\", "/")
REQUIRED_REGRESSIONS_REL = quality_gate_shared.QUALITY_GATE_REQUIRED_REGRESSIONS_REL.replace("\\", "/")
REQUIRED_REGRESSIONS_PROOF_SCHEMA_VERSION = 3
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


def verify_required_regressions_from_payload(
    payload: Mapping[str, Any],
    *,
    required_tests: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    _validate_clean_full_test_debt_payload(payload)
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

    bad_reports: List[str] = []
    xfail_reports: List[str] = []
    for nodeid in required_nodeids:
        for report in reports_by_nodeid[nodeid]:
            when = str(report.get("when") or "")
            outcome = str(report.get("outcome") or "")
            if outcome != "passed":
                bad_reports.append(f"{nodeid} [{when or '-'}:{outcome or '-'}]")
            if _report_has_xfail_signal(report):
                xfail_reports.append(f"{nodeid} [{when or '-'}]")
    if bad_reports:
        raise RequiredRegressionProofError("required nodeid 存在非通过 reports：" + ", ".join(bad_reports[:20]))
    if xfail_reports:
        raise RequiredRegressionProofError("required nodeid 存在 xfail 信号：" + ", ".join(xfail_reports[:20]))

    return {
        "required_target_paths": required_paths,
        "required_nodeids": required_nodeids,
        "required_nodeid_count_by_path": {path: len(nodeids_by_path[path]) for path in required_paths},
        "collected_count": len(collected_nodeids),
        "report_count": len(reports),
    }


def _git_head_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RequiredRegressionProofError("无法读取当前 HEAD SHA")
    return str(completed.stdout or "").strip()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _parse_args_json(value: str) -> List[str]:
    if not str(value or "").strip():
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise argparse.ArgumentTypeError("--args-json 必须是 JSON 列表")
    return [str(item) for item in parsed]


def _default_command_plan_entry() -> Tuple[int, Dict[str, Any], List[Dict[str, Any]]]:
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    for index, command in enumerate(command_plan, start=1):
        if str(command.get("display") or "") == DEFAULT_COMMAND:
            return index, dict(command), command_plan
    return 0, {
        "display": DEFAULT_COMMAND,
        "args": shlex.split(DEFAULT_COMMAND),
        "capture_output": True,
        "output_policy": "normalized",
    }, command_plan


def _build_proof_payload(
    *,
    verification: Mapping[str, Any],
    source_payload: Mapping[str, Any],
    source_payload_rel: str,
    output_line: str,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    default_index, default_entry, command_plan = _default_command_plan_entry()
    command_args = list(args.args_json or [])
    if not command_args:
        command_args = shlex.split(str(args.command or "")) if str(args.command or "").strip() else list(default_entry["args"])
    display = str(args.display or args.command or default_entry["display"])
    command = {
        "display": display,
        "args": command_args,
        "capture_output": bool(default_entry.get("capture_output", True)),
        "output_policy": str(default_entry.get("output_policy") or "normalized"),
        "env_overlay": dict(default_entry.get("env_overlay") or {}),
    }
    command_hash = str(args.command_hash or "")
    if not command_hash:
        command_hash = quality_gate_shared.build_quality_gate_command_receipt(
            command,
            returncode=0,
            stdout=output_line,
            stderr="",
        )["command_hash"]

    stdout_log_path = str(args.stdout_log_path or "evidence/QualityGate/long_gate/logs/required_regressions.stdout.log")
    stderr_log_path = str(args.stderr_log_path or "evidence/QualityGate/long_gate/logs/required_regressions.stderr.log")
    stdout_sha256 = str(args.stdout_sha256 or _sha256_text(output_line))
    stderr_sha256 = str(args.stderr_sha256 or _sha256_text(""))
    required_target_paths = list(verification["required_target_paths"])
    required_nodeids = list(verification["required_nodeids"])
    return {
        "schema_version": REQUIRED_REGRESSIONS_PROOF_SCHEMA_VERSION,
        "status": "passed",
        "entry_id": str(args.entry_id or ENTRY_REQUIRED_REGRESSIONS),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "head_sha": _git_head_sha(),
        "run_id": str(args.run_id or ""),
        "quality_gate_plan_hash": str(args.quality_gate_plan_hash or quality_gate_shared.hash_quality_gate_commands(command_plan)),
        "command_index": int(args.command_index if args.command_index is not None else default_index),
        "display": display,
        "args": command_args,
        "command_hash": command_hash,
        "capture_output": bool(command["capture_output"]),
        "output_policy": str(command["output_policy"]),
        "required_target_count": len(required_target_paths),
        "test_count": len(required_target_paths),
        "required_target_paths": required_target_paths,
        "required_target_hash": stable_json_hash(required_target_paths),
        "verified_required_nodeid_count": len(required_nodeids),
        "verified_required_nodeids_hash": stable_json_hash(required_nodeids),
        "required_nodeid_count_by_path": dict(verification["required_nodeid_count_by_path"]),
        "source_payload_path": source_payload_rel,
        "source_payload_head_sha": str(source_payload.get("head_sha") or ""),
        "source_payload_generated_at": str(source_payload.get("generated_at") or ""),
        "source_payload_collected_count": int(verification["collected_count"]),
        "source_payload_report_count": int(verification["report_count"]),
        "verification_method": "full_test_debt_payload_required_coverage",
        "fingerprint_schema_version": int(args.fingerprint_schema_version or 0),
        "fingerprint_hash": str(args.fingerprint_hash or ""),
        "returncode": 0,
        "pytest_exit_code": 0,
        "execution_mode": str(args.execution_mode or "verified_from_full_test_debt"),
        "duration_s": float(args.duration_s or 0.0),
        "stdout_log_path": stdout_log_path.replace("\\", "/"),
        "stderr_log_path": stderr_log_path.replace("\\", "/"),
        "stdout_sha256": stdout_sha256,
        "stderr_sha256": stderr_sha256,
        "timed_out": False,
        "interrupted": False,
        "partial_write": False,
        "does_not_claim": "clean_worktree_proof",
        "logs": {
            "stdout": {
                "path": stdout_log_path.replace("\\", "/"),
                "sha256": stdout_sha256,
                "bytes": len(output_line.encode("utf-8")),
            },
            "stderr": {
                "path": stderr_log_path.replace("\\", "/"),
                "sha256": stderr_sha256,
                "bytes": 0,
            },
        },
    }


def _write_json(path: str, payload: Mapping[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temp_path, path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify required regressions from current full-test-debt payload without rerunning pytest.",
    )
    parser.add_argument("--payload", default=CURRENT_FULL_TEST_DEBT_REL)
    parser.add_argument("--output", default=REQUIRED_REGRESSIONS_REL)
    parser.add_argument("--command", default=DEFAULT_COMMAND)
    parser.add_argument("--display", default="")
    parser.add_argument("--args-json", type=_parse_args_json, default=None)
    parser.add_argument("--entry-id", default=ENTRY_REQUIRED_REGRESSIONS)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--command-index", type=int, default=None)
    parser.add_argument("--quality-gate-plan-hash", default="")
    parser.add_argument("--command-hash", default="")
    parser.add_argument("--fingerprint-hash", default="")
    parser.add_argument("--fingerprint-schema-version", type=int, default=0)
    parser.add_argument("--execution-mode", default="verified_from_full_test_debt")
    parser.add_argument("--duration-s", type=float, default=0.0)
    parser.add_argument("--stdout-log-path", default="")
    parser.add_argument("--stderr-log-path", default="")
    parser.add_argument("--stdout-sha256", default="")
    parser.add_argument("--stderr-sha256", default="")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    payload_path = _abs_repo_path(str(args.payload))
    output_path = _abs_repo_path(str(args.output))
    source_payload_rel = _repo_rel_path(str(args.payload))
    try:
        source_payload = _load_json_object(payload_path)
        verification = verify_required_regressions_from_payload(source_payload)
        output_rel = _repo_rel_path(str(args.output))
        output_line = (
            "required_regressions verified "
            f"targets={len(verification['required_target_paths'])} "
            f"nodeids={len(verification['required_nodeids'])} "
            f"output={output_rel}\n"
        )
        proof = _build_proof_payload(
            verification=verification,
            source_payload=source_payload,
            source_payload_rel=source_payload_rel,
            output_line=output_line,
            args=args,
        )
        _write_json(output_path, proof)
    except (OSError, ValueError, RequiredRegressionProofError) as exc:
        print(f"required_regressions verification failed: {exc}", file=sys.stderr, flush=True)
        return 1
    print(output_line, end="", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
