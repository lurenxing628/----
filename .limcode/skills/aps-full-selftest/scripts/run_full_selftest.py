from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.quality_gate_shared import QUALITY_GATE_MANIFEST_REL, QUALITY_GATE_PROOF_SCHEMA_VERSION

TIMEOUT_EXIT_CODE = 124


@dataclass
class StepResult:
    name: str
    cmd: List[str]
    exit_code: int
    duration_s: float
    evidence_paths: List[str]
    log_path: str
    effective_pass: bool
    note: str = ""


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git_head_sha(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo_root), capture_output=True,
        text=True, errors="replace", timeout=30,
    )
    return str(proc.stdout or "").strip() if proc.returncode == 0 else "unknown"


def _git_status_lines(repo_root: Path) -> List[str]:
    proc = subprocess.run(
        ["git", "status", "--short"], cwd=str(repo_root), capture_output=True,
        text=True, errors="replace", timeout=30,
    )
    if proc.returncode != 0:
        return ["<git status --short failed>"]
    return [line.rstrip() for line in str(proc.stdout or "").splitlines() if line.strip()]


def _manifest_failure_details(manifest: object) -> str:
    if not isinstance(manifest, dict):
        return ""
    details = []
    for field in ("failure_kind", "failure_message"):
        value = str(manifest.get(field) or "").strip()
        if value:
            details.append(f"{field}={value}")
    return "; ".join(details)


def _verify_bound_manifest(manifest: object, *, head_sha: str) -> Optional[str]:
    if not isinstance(manifest, dict):
        return "UNBOUND: quality gate manifest 顶层不是对象"
    if manifest.get("schema_version") != QUALITY_GATE_PROOF_SCHEMA_VERSION:
        return f"UNBOUND: quality gate schema_version={manifest.get('schema_version')!r}"
    if manifest.get("status") != "passed":
        return f"UNBOUND: quality gate status={manifest.get('status') or 'unknown'}"
    if str(manifest.get("head_sha") or "").strip() != head_sha:
        return "UNBOUND: quality gate head_sha 不匹配"
    if (
        bool(manifest.get("is_dirty_before"))
        or bool(manifest.get("is_dirty_after"))
        or bool(manifest.get("tracked_drift_detected"))
    ):
        return "UNBOUND: quality gate 工作区干净证明未通过"
    return None


def _read_manifest(manifest_path: Path) -> Tuple[Optional[object], Optional[str]]:
    if not manifest_path.is_file():
        return None, "UNBOUND: quality gate manifest 缺失"
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"UNBOUND: quality gate manifest 读取失败：{exc}"


def _quality_gate_binding_status(
    repo_root: Path,
    head_sha: str,
    git_status_lines: Sequence[str],
) -> StepResult:
    manifest_rel = Path(QUALITY_GATE_MANIFEST_REL).as_posix()
    log_rel = "evidence/FullSelfTest/logs/00_quality_gate_binding.log.txt"
    log_path = repo_root / log_rel
    if not head_sha or head_sha == "unknown":
        note = "UNBOUND: 无法解析当前 Git HEAD"
        _write_text(log_path, note + "\n")
        return StepResult("quality_gate_binding", [], 1, 0.0, [manifest_rel], log_rel, False, note)
    if git_status_lines:
        note = "UNBOUND: 工作区不干净，不能绑定完整质量门禁"
        _write_text(log_path, "\n".join([note, *git_status_lines]) + "\n")
        return StepResult("quality_gate_binding", [], 1, 0.0, [manifest_rel], log_rel, False, note)

    cmd = [
        _project_python(repo_root),
        "scripts/run_quality_gate.py",
        "--require-clean-worktree",
        "--long-gate-cache",
        "--no-resume",
    ]
    exit_code, duration_s, output, _timed_out = _run_cmd(cmd=cmd, cwd=repo_root, timeout_s=None)
    manifest, read_error = _read_manifest(repo_root / manifest_rel)
    if exit_code != 0:
        note = f"UNBOUND: 完整质量门禁执行失败（exit={exit_code}）"
        extra = _manifest_failure_details(manifest)
        if extra:
            note = f"{note}; {extra}"
        _write_text(log_path, f"[COMMAND] {' '.join(cmd)}\n{output}\n[BINDING] {note}\n")
        return StepResult("quality_gate_binding", cmd, exit_code, duration_s, [manifest_rel], log_rel, False, note)

    error = read_error or _verify_bound_manifest(manifest, head_sha=head_sha)
    if error is None and _git_status_lines(repo_root):
        error = "UNBOUND: 完整质量门禁运行后工作区不干净"
    if error is not None:
        _write_text(log_path, f"[COMMAND] {' '.join(cmd)}\n{output}\n[BINDING] {error}\n")
        return StepResult("quality_gate_binding", cmd, 1, duration_s, [manifest_rel], log_rel, False, error)

    _write_text(log_path, f"[COMMAND] {' '.join(cmd)}\n{output}\n[BINDING] BOUND\n")
    return StepResult("quality_gate_binding", cmd, 0, duration_s, [manifest_rel], log_rel, True, "BOUND")


def _project_python(repo_root: Path) -> str:
    relative_path = Path(".venv/Scripts/python.exe") if os.name == "nt" else Path(".venv/bin/python")
    return str(repo_root / relative_path)


def _build_steps(repo_root: Path, *, fail_fast: bool) -> List[Tuple[str, List[str], List[str]]]:
    command = [_project_python(repo_root), "-m", "pytest", "tests", "-q", "--tb=short"]
    if fail_fast:
        command.append("-x")
    return [("pytest_tests", command, [])]


def _run_cmd(*, cmd: Sequence[str], cwd: Path, timeout_s: Optional[int]) -> Tuple[int, float, str, bool]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            list(cmd), cwd=str(cwd), capture_output=True, text=True,
            errors="replace", timeout=timeout_s if timeout_s and timeout_s > 0 else None,
        )
        output = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
        return int(proc.returncode), time.monotonic() - started, output, False
    except subprocess.TimeoutExpired as exc:
        output = f"[TIMEOUT] pytest 超时（>{timeout_s}s）"
        for part in (exc.stdout, exc.stderr):
            if part:
                output += "\n" + (part.decode("utf-8", errors="replace") if isinstance(part, bytes) else part)
        return TIMEOUT_EXIT_CODE, time.monotonic() - started, output, True
    except OSError as exc:
        return 127, time.monotonic() - started, f"[ENV_EXEC_ERROR] {exc}", False


def _classify_failure_note(exit_code: int, output: str) -> str:
    if exit_code == 5:
        return "PYTEST_NO_TESTS_COLLECTED"
    if "[ENV_EXEC_ERROR]" in output:
        return "ENV_EXEC_ERROR"
    if "No module named pytest" in output or "ModuleNotFoundError: No module named 'pytest'" in output:
        return "ENV_PYTEST_MISSING"
    if "ModuleNotFoundError: No module named 'core'" in output:
        return "ENV_IMPORT_PATH"
    if "ImportError" in output or "ModuleNotFoundError" in output:
        return "ENV_IMPORT_ERROR"
    return "exit_code!=0"


def _report_header_lines(
    *,
    repo_root: Path,
    fail_fast: bool,
    step_timeout_s: Optional[int],
    head_sha: str,
    git_status_lines: Sequence[str],
    quality_gate_manifest_rel: str,
) -> List[str]:
    lines = [
        "# APS 全量自测汇总报告（不打包）", "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- runner Python：{sys.version.splitlines()[0].strip()}",
        f"- runner Python 可执行：`{sys.executable}`",
        f"- 测试 Python 可执行：`{_project_python(repo_root)}`",
        f"- 仓库根目录：`{repo_root.as_posix()}`",
        f"- fail_fast：{str(bool(fail_fast)).lower()}",
        f"- step_timeout_s：{step_timeout_s if step_timeout_s else 'none'}",
        f"- head_sha：`{head_sha or 'unknown'}`",
        "- git status --short：",
    ]
    lines.extend(f"  - `{line}`" for line in git_status_lines)
    if not git_status_lines:
        lines.append("  - `(clean)`")
    lines.extend([f"- quality_gate_manifest：`{quality_gate_manifest_rel}`", ""])
    return lines


def _write_report(repo_root: Path, lines: List[str], results: Sequence[StepResult], overall_pass: bool) -> str:
    lines.extend([
        "## 总结", "", f"- 结论：**{'PASS' if overall_pass else 'FAIL'}**",
        f"- 记录数：{len(results)}",
        f"- 总执行耗时：{sum(result.duration_s for result in results):.2f}s", "",
        "## 明细", "",
        "| # | 步骤 | 结果 | exit | 耗时(s) | 证据(evidence) | runner日志 | 备注 |",
        "|---:|---|---|---:|---:|---|---|---|",
    ])
    for index, result in enumerate(results, start=1):
        status = "PASS" if result.effective_pass else "FAIL"
        evidence = "<br/>".join(result.evidence_paths) or "-"
        note = result.note.replace("|", "\\|") or "-"
        lines.append(
            f"| {index} | `{result.name}` | {status} | {result.exit_code} | "
            f"{result.duration_s:.2f} | {evidence} | {result.log_path} | {note} |"
        )
    if not overall_pass:
        lines.extend(["", "## 失败项（按出现顺序）", ""])
        for result in results:
            if result.effective_pass:
                continue
            lines.append(f"- `{result.name}`（exit={result.exit_code}）：{result.note}")
            lines.append(f"  - runner日志：`{result.log_path}`")
    lines.extend([
        "", "## 说明", "",
        "- 测试集合以一次 `pytest tests -q` 的实际收集和运行结果为准。",
        "- quality_gate_binding 失败时不运行 pytest；pytest 提前停止或超时不计为全量通过。",
        "- 本报告是运行产物；最终 clean proof 仍以统一质量门禁与干净工作区证据为准。",
        "- 本 runner 不执行 PyInstaller / dist / validate_dist_exe 等打包流程。", "",
    ])
    report_path = repo_root / "evidence/FullSelfTest/logs/full_selftest_report.md"
    _write_text(report_path, "\n".join(lines))
    return report_path.relative_to(repo_root).as_posix()


def run_full_selftest(
    *,
    repo_root: Path,
    fail_fast: bool,
    step_timeout_s: Optional[int],
) -> Tuple[bool, List[StepResult], str]:
    head_sha = _git_head_sha(repo_root)
    git_status_lines = _git_status_lines(repo_root)
    binding_step = _quality_gate_binding_status(repo_root, head_sha, git_status_lines)
    manifest_rel = binding_step.evidence_paths[0]
    lines = _report_header_lines(
        repo_root=repo_root, fail_fast=fail_fast, step_timeout_s=step_timeout_s,
        head_sha=head_sha, git_status_lines=git_status_lines, quality_gate_manifest_rel=manifest_rel,
    )
    results: List[StepResult] = [binding_step]
    if binding_step.effective_pass:
        for index, (name, cmd, evidence_paths) in enumerate(_build_steps(repo_root, fail_fast=fail_fast), start=1):
            log_path = repo_root / f"evidence/FullSelfTest/logs/{index:02d}_{name}.log.txt"
            exit_code, duration_s, output, timed_out = _run_cmd(cmd=cmd, cwd=repo_root, timeout_s=step_timeout_s)
            _write_text(log_path, f"[COMMAND] {' '.join(cmd)}\n{output}")
            note = ""
            if timed_out:
                note = f"TIMEOUT>{step_timeout_s}s"
            elif exit_code != 0:
                note = _classify_failure_note(exit_code, output)
                if fail_fast:
                    note += "；-x 提前停止，未完成全量"
            results.append(StepResult(
                name=name, cmd=cmd, exit_code=exit_code, duration_s=duration_s,
                evidence_paths=evidence_paths, log_path=log_path.relative_to(repo_root).as_posix(),
                effective_pass=exit_code == 0, note=note,
            ))
    overall_pass = all(result.effective_pass for result in results)
    return overall_pass, results, _write_report(repo_root, lines, results, overall_pass)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="APS 全量自测 runner（单次 pytest，不打包）")
    parser.add_argument("--fail-fast", action="store_true", help="pytest 遇到第一个失败即停止（-x）")
    parser.add_argument("--step-timeout", type=int, default=900, help="pytest 超时秒数（默认 900；<=0 不设超时）")
    args = parser.parse_args(list(argv) if argv is not None else None)
    ok, _results, report_rel = run_full_selftest(
        repo_root=REPO_ROOT, fail_fast=bool(args.fail_fast),
        step_timeout_s=int(args.step_timeout) if args.step_timeout > 0 else None,
    )
    print(report_rel)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
