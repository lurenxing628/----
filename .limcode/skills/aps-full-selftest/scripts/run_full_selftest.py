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
from typing import List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.quality_gate_shared import QUALITY_GATE_MANIFEST_REL, iter_non_regression_guard_tests

TIMEOUT_EXIT_CODE = 124  # 与常见 CI 约定一致：超时 = 124


@dataclass
class StepResult:
    name: str
    cmd: List[str]
    exit_code: int
    duration_s: float
    evidence_paths: List[str]
    log_path: str
    # Phase10 等特殊情况：即使 exit_code=0，也可能通过报告判定为 FAIL
    effective_pass: bool
    note: str = ""


def _explicit_guard_tests() -> List[str]:
    return list(iter_non_regression_guard_tests())


def _find_repo_root() -> Path:
    """
    优先从本脚本位置向上找（.limcode/skills/...），找到包含 app.py + schema.sql 的目录即 repo root。
    """
    candidates: List[Path] = []
    try:
        candidates.append(Path(__file__).resolve())
    except Exception:
        pass
    try:
        candidates.append(Path.cwd().resolve())
    except Exception:
        pass

    for base in candidates:
        p = base if base.is_dir() else base.parent
        for _ in range(10):
            if (p / "app.py").exists() and (p / "schema.sql").exists():
                return p
            if p.parent == p:
                break
            p = p.parent
    raise RuntimeError("未找到仓库根目录（要求存在 app.py 与 schema.sql）")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_text(path: Path, text: str) -> None:
    _ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def _git_head_sha(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
    )
    if int(proc.returncode) != 0:
        return "unknown"
    return str(proc.stdout or "").strip() or "unknown"


def _git_status_lines(repo_root: Path) -> List[str]:
    proc = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
    )
    if int(proc.returncode) != 0:
        return ["<git status --short failed>"]
    return [str(line).rstrip() for line in str(proc.stdout or "").splitlines() if str(line).strip()]


def _git_rev_parse_path(repo_root: Path, *args: str, fallback: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
    )
    raw_value = str(proc.stdout or "").strip()
    if int(proc.returncode) == 0 and raw_value:
        path_text = raw_value
        if not os.path.isabs(path_text):
            path_text = str(repo_root / path_text)
        return os.path.realpath(path_text)
    return os.path.realpath(str(fallback))


def _repo_identity(repo_root: Path) -> tuple[str, str]:
    return (
        _git_rev_parse_path(repo_root, "--show-toplevel", fallback=repo_root),
        _git_rev_parse_path(repo_root, "--git-common-dir", fallback=repo_root / ".git"),
    )


def _tracked_regression_files(repo_root: Path) -> List[Path]:
    proc = subprocess.run(
        ["git", "ls-files", "--", "tests/regression_*.py"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
    )
    if int(proc.returncode) != 0:
        return []
    tracked: List[Path] = []
    seen = set()
    for raw_line in str(proc.stdout or "").splitlines():
        rel_path = str(raw_line or "").strip()
        if not rel_path or rel_path in seen:
            continue
        seen.add(rel_path)
        tracked.append((repo_root / rel_path).resolve())
    tracked.sort(key=lambda path: path.name)
    return tracked


def _quality_gate_binding_status(
    repo_root: Path,
    head_sha: str,
    git_status_lines: Sequence[str],
) -> tuple[bool, str, str]:
    manifest_rel = Path(QUALITY_GATE_MANIFEST_REL).as_posix()
    manifest_path = repo_root / Path(manifest_rel)
    if not manifest_path.exists():
        return False, "UNBOUND: quality gate manifest 缺失", manifest_rel
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"UNBOUND: quality gate manifest 读取失败：{exc}", manifest_rel
    if not isinstance(manifest, dict):
        return False, "UNBOUND: quality gate manifest 非法", manifest_rel
    manifest_checkout_root = os.path.realpath(str(manifest.get("checkout_root_realpath") or "").strip())
    manifest_git_common_dir = os.path.realpath(str(manifest.get("git_common_dir_realpath") or "").strip())
    if not manifest_checkout_root or not manifest_git_common_dir:
        return False, "UNBOUND: quality gate checkout identity missing", manifest_rel
    current_checkout_root, current_git_common_dir = _repo_identity(repo_root)
    if manifest_checkout_root != current_checkout_root:
        return False, "UNBOUND: quality gate checkout root mismatch", manifest_rel
    if manifest_git_common_dir != current_git_common_dir:
        return False, "UNBOUND: quality gate git common dir mismatch", manifest_rel
    if str(manifest.get("status") or "").strip().lower() != "passed":
        return False, f"UNBOUND: quality gate status={manifest.get('status') or 'unknown'}", manifest_rel
    if str(manifest.get("head_sha") or "").strip() != str(head_sha or "").strip():
        return False, "UNBOUND: quality gate head_sha 不匹配", manifest_rel
    if "git_status_short_before" not in manifest or "git_status_short_after" not in manifest:
        return False, "UNBOUND: quality gate worktree proof missing", manifest_rel
    manifest_git_status_before = [
        str(line).rstrip() for line in list(manifest.get("git_status_short_before") or []) if str(line).strip()
    ]
    manifest_git_status_after = [
        str(line).rstrip() for line in list(manifest.get("git_status_short_after") or []) if str(line).strip()
    ]
    current_git_status = [str(line).rstrip() for line in list(git_status_lines or []) if str(line).strip()]
    if bool(manifest.get("is_dirty_before")) or manifest_git_status_before:
        return False, "UNBOUND: quality gate started dirty", manifest_rel
    if bool(manifest.get("tracked_drift_detected")):
        return False, "UNBOUND: quality gate tracked drift detected", manifest_rel
    if bool(manifest.get("is_dirty_after")) or manifest_git_status_after:
        return False, "UNBOUND: quality gate finished dirty", manifest_rel
    if manifest_git_status_after != current_git_status:
        return False, "UNBOUND: quality gate git status --short 不匹配", manifest_rel
    return True, "BOUND", manifest_rel


def _report_header_lines(
    *,
    repo_root: Path,
    fail_fast: bool,
    complex_repeat: int,
    step_timeout_s: Optional[int],
    head_sha: str,
    git_status_lines: Sequence[str],
    quality_gate_manifest_rel: str,
) -> List[str]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: List[str] = []
    lines.append("# APS 全量自测汇总报告（不打包）")
    lines.append("")
    lines.append(f"- 生成时间：{now}")
    lines.append(f"- Python：{sys.version.splitlines()[0]}")
    lines.append(f"- Python 可执行：`{(sys.executable or '').strip()}`")
    lines.append(f"- 仓库根目录：`{repo_root.as_posix()}`")
    lines.append(f"- fail_fast：{str(bool(fail_fast)).lower()}")
    lines.append(f"- complex_repeat：{int(complex_repeat)}")
    lines.append(f"- step_timeout_s：{int(step_timeout_s) if step_timeout_s else 'none'}")
    lines.append(f"- head_sha：`{str(head_sha or 'unknown').strip() or 'unknown'}`")
    lines.append("- git status --short：")
    for line in list(git_status_lines or ()):
        lines.append(f"  - `{line}`")
    if not list(git_status_lines or ()):
        lines.append("  - `(clean)`")
    lines.append(f"- quality_gate_manifest：`{quality_gate_manifest_rel}`")
    lines.append("")
    return lines


def _run_cmd(*, cmd: Sequence[str], cwd: Path, timeout_s: Optional[int]) -> tuple[int, float, str, bool]:
    t0 = time.time()
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=(int(timeout_s) if timeout_s and int(timeout_s) > 0 else None),
        )
        dt = time.time() - t0
        out = ""
        if proc.stdout:
            out += proc.stdout
        if proc.stderr:
            if out:
                out += "\n"
            out += proc.stderr
        return int(proc.returncode), float(dt), out, False
    except subprocess.TimeoutExpired as e:
        dt = time.time() - t0
        out = f"[TIMEOUT] step 超时（>{int(timeout_s)}s）".strip()
        stdout = getattr(e, "stdout", None)
        stderr = getattr(e, "stderr", None)
        if stdout:
            out += "\n" + str(stdout)
        if stderr:
            out += "\n" + str(stderr)
        return TIMEOUT_EXIT_CODE, float(dt), out.strip(), True


def _phase10_report_indicates_fail(repo_root: Path) -> tuple[bool, str]:
    """
    smoke_phase10 的脚本内部会把 PASS/FAIL 写到报告里，但不一定用非 0 退出码表示失败。
    因此这里以报告内容兜底判断。
    """
    report = repo_root / "evidence" / "Phase10" / "smoke_phase10_report.md"
    if not report.exists():
        # Phase10 脚本不可靠的退出码使得“报告缺失”也应被视为失败（无法判定 PASS）。
        return True, f"Phase10 报告不存在：{report.as_posix()}"
    try:
        txt = report.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return True, f"Phase10 报告读取失败：{e}"
    if "- FAIL：" in txt:
        return True, f"Phase10 报告包含 FAIL：{report.as_posix()}"
    return False, f"Phase10 报告显示 PASS：{report.as_posix()}"


def _classify_failure_note(exit_code: int, output: str) -> str:
    txt = str(output or "")
    if int(exit_code) == 5:
        return "PYTEST_NO_TESTS_COLLECTED"
    if "No module named pytest" in txt or "ModuleNotFoundError: No module named 'pytest'" in txt:
        return "ENV_PYTEST_MISSING"
    if "ModuleNotFoundError: No module named 'core'" in txt:
        return "ENV_IMPORT_PATH"
    if "ImportError" in txt or "ModuleNotFoundError" in txt:
        return "ENV_IMPORT_ERROR"
    return "exit_code!=0"


def _resolve_pytest_python(current_python: str, repo_root: Path) -> str:
    candidates = [str(current_python or "").strip(), "python"]
    tried = set()
    for candidate in candidates:
        if not candidate or candidate in tried:
            continue
        tried.add(candidate)
        try:
            proc = subprocess.run(
                [candidate, "-m", "pytest", "--version"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                errors="replace",
                timeout=30,
            )
        except Exception:
            continue
        if int(proc.returncode) == 0:
            return candidate
    return str(current_python or "python")


def _build_steps(repo_root: Path, *, complex_repeat: int) -> List[tuple[str, List[str], List[str]]]:
    """
    返回 (step_name, cmd, evidence_paths[])。
    cmd 中的脚本路径使用 repo 内相对路径（runner 以 repo_root 为 cwd）。
    """
    py = sys.executable or "python"
    pytest_py = _resolve_pytest_python(py, repo_root)

    steps: List[tuple[str, List[str], List[str]]] = []

    # smoke phases（固定顺序，避免 smoke_phase10 的字典序问题）
    smoke_files = [
        "tests/smoke_phase0_phase1.py",
        "tests/smoke_phase2.py",
        "tests/smoke_phase3.py",
        "tests/smoke_phase4.py",
        "tests/smoke_phase5.py",
        "tests/smoke_phase6.py",
        "tests/smoke_phase7.py",
        "tests/smoke_phase8.py",
        "tests/smoke_phase9.py",
        "tests/smoke_phase10_sgs_auto_assign.py",
    ]
    smoke_evidence = {
        "tests/smoke_phase0_phase1.py": ["evidence/Phase0_Phase1/smoke_test_report.md"],
        "tests/smoke_phase2.py": ["evidence/Phase2/smoke_phase2_report.md"],
        "tests/smoke_phase3.py": ["evidence/Phase3/smoke_phase3_report.md"],
        "tests/smoke_phase4.py": ["evidence/Phase4/smoke_phase4_report.md"],
        "tests/smoke_phase5.py": ["evidence/Phase5/smoke_phase5_report.md"],
        "tests/smoke_phase6.py": ["evidence/Phase6/smoke_phase6_report.md"],
        "tests/smoke_phase7.py": ["evidence/Phase7/smoke_phase7_report.md"],
        "tests/smoke_phase8.py": ["evidence/Phase8/smoke_phase8_report.md"],
        "tests/smoke_phase9.py": ["evidence/Phase9/smoke_phase9_report.md"],
        "tests/smoke_phase10_sgs_auto_assign.py": ["evidence/Phase10/smoke_phase10_report.md"],
    }
    for f in smoke_files:
        steps.append((Path(f).name, [py, f], list(smoke_evidence.get(f, []))))

    # web smoke
    steps.append(
        (
            "smoke_web_phase0_5.py",
            [py, "tests/smoke_web_phase0_5.py"],
            ["evidence/Phase0_to_Phase5/web_smoke_report.md"],
        )
    )
    steps.append(
        (
            "smoke_web_phase0_6.py",
            [py, "tests/smoke_web_phase0_6.py"],
            ["evidence/Phase0_to_Phase6/web_smoke_report.md"],
        )
    )

    # FullE2E
    steps.append(
        (
            "smoke_e2e_excel_to_schedule.py",
            [py, "tests/smoke_e2e_excel_to_schedule.py"],
            ["evidence/FullE2E/excel_to_schedule_report.md"],
        )
    )

    # regressions（自动发现 + 按文件名排序）
    reg_files = _tracked_regression_files(repo_root)
    for p in reg_files:
        steps.append((p.name, [pytest_py, "-m", "pytest", f"tests/{p.name}", "-q", "--tb=short"], []))

    # 显式守卫：不依赖 regression_* 命名，避免关键契约测试脱离 runner。
    for rel_path in _explicit_guard_tests():
        guard_path = repo_root / rel_path
        if not guard_path.is_file():
            continue
        steps.append((guard_path.name, [pytest_py, "-m", "pytest", rel_path, "-q", "--tb=short"], []))

    # complex excel cases
    steps.append(
        (
            "run_complex_excel_cases_e2e.py",
            [
                py,
                "tests/run_complex_excel_cases_e2e.py",
                "--out",
                "evidence/ComplexExcelCases",
                "--repeat",
                str(int(complex_repeat)),
            ],
            [
                "evidence/ComplexExcelCases/complex_cases_report.md",
                "evidence/ComplexExcelCases/complex_cases_summary.json",
            ],
        )
    )

    return steps


def run_full_selftest(
    *,
    repo_root: Path,
    fail_fast: bool,
    complex_repeat: int,
    step_timeout_s: Optional[int],
) -> tuple[bool, List[StepResult], str]:
    out_dir = repo_root / "evidence" / "FullSelfTest"
    logs_dir = out_dir / "logs"
    _ensure_dir(logs_dir)

    steps = _build_steps(repo_root, complex_repeat=int(complex_repeat))
    results: List[StepResult] = []
    overall_pass = True
    head_sha = _git_head_sha(repo_root)
    git_status_lines = _git_status_lines(repo_root)
    quality_gate_binding_ok, quality_gate_binding_note, quality_gate_manifest_rel = _quality_gate_binding_status(
        repo_root,
        head_sha,
        git_status_lines,
    )

    if not quality_gate_binding_ok:
        log_path = logs_dir / "00_quality_gate_binding.log.txt"
        _write_text(log_path, quality_gate_binding_note + "\n")
        results.append(
            StepResult(
                name="quality_gate_binding",
                cmd=[],
                exit_code=1,
                duration_s=0.0,
                evidence_paths=[quality_gate_manifest_rel],
                log_path=str(log_path.relative_to(repo_root).as_posix()),
                effective_pass=False,
                note=quality_gate_binding_note,
            )
        )
        overall_pass = False
        lines = _report_header_lines(
            repo_root=repo_root,
            fail_fast=fail_fast,
            complex_repeat=complex_repeat,
            step_timeout_s=step_timeout_s,
            head_sha=head_sha,
            git_status_lines=git_status_lines,
            quality_gate_manifest_rel=quality_gate_manifest_rel,
        )
        lines.append("## 总结")
        lines.append("")
        lines.append("- 结论：**FAIL**")
        lines.append("- 记录数：1")
        lines.append("")
        lines.append("## 明细")
        lines.append("")
        lines.append("| # | 脚本 | 结果 | exit | 耗时(s) | 证据(evidence) | runner日志 | 备注 |")
        lines.append("|---:|---|---|---:|---:|---|---|---|")
        lines.append(
            f"| 1 | `quality_gate_binding` | FAIL | 1 | 0.00 | {quality_gate_manifest_rel} | {results[0].log_path} | {quality_gate_binding_note} |"
        )
        lines.append("")
        lines.append("## 失败项（按出现顺序）")
        lines.append("")
        lines.append(f"- `quality_gate_binding`（exit=1）：{quality_gate_binding_note}")
        lines.append(f"  - 证据：`{quality_gate_manifest_rel}`")
        lines.append(f"  - runner日志：`{results[0].log_path}`")
        lines.append("")
        lines.append("## 说明")
        lines.append("")
        lines.append("- 本 runner **不会**执行 PyInstaller / dist / validate_dist_exe 等打包流程。")
        lines.append("- 复杂 Excel 用例的重产物目录默认会被 `.gitignore` 忽略，仅保留报告与 summary JSON。")
        lines.append("")
        report_path = out_dir / "full_selftest_report.md"
        _write_text(report_path, "\n".join(lines) + "\n")
        return overall_pass, results, str(report_path.relative_to(repo_root).as_posix())

    for idx, (name, cmd, evidence_paths) in enumerate(steps, start=1):
        safe_stem = f"{idx:02d}_{name}".replace("/", "_").replace("\\", "_")
        log_path = logs_dir / f"{safe_stem}.log.txt"

        rc, dt, output, timed_out = _run_cmd(cmd=cmd, cwd=repo_root, timeout_s=step_timeout_s)
        _write_text(log_path, output)

        effective_pass = (rc == 0)
        note = f"TIMEOUT>{int(step_timeout_s)}s" if timed_out and step_timeout_s else ""

        # Phase10 兜底：读报告判定 FAIL
        if name == "smoke_phase10_sgs_auto_assign.py":
            report_fail, report_note = _phase10_report_indicates_fail(repo_root)
            note = (note + " | " + report_note).strip(" |") if note else report_note
            if report_fail:
                effective_pass = False

        if not effective_pass:
            overall_pass = False
            if not note:
                note = _classify_failure_note(rc, output)

        results.append(
            StepResult(
                name=name,
                cmd=list(cmd),
                exit_code=rc,
                duration_s=dt,
                evidence_paths=list(evidence_paths),
                log_path=str(log_path.relative_to(repo_root).as_posix()),
                effective_pass=effective_pass,
                note=note,
            )
        )

        if fail_fast and not effective_pass:
            break

    # 汇总报告 markdown
    lines = _report_header_lines(
        repo_root=repo_root,
        fail_fast=fail_fast,
        complex_repeat=complex_repeat,
        step_timeout_s=step_timeout_s,
        head_sha=head_sha,
        git_status_lines=git_status_lines,
        quality_gate_manifest_rel=quality_gate_manifest_rel,
    )

    lines.append("## 总结")
    lines.append("")
    lines.append(f"- 结论：**{'PASS' if overall_pass else 'FAIL'}**")
    lines.append(f"- 记录数：{len(results)}")
    lines.append("")

    lines.append("## 明细")
    lines.append("")
    lines.append("| # | 脚本 | 结果 | exit | 耗时(s) | 证据(evidence) | runner日志 | 备注 |")
    lines.append("|---:|---|---|---:|---:|---|---|---|")
    for i, r in enumerate(results, start=1):
        status = "PASS" if r.effective_pass else "FAIL"
        ev = "<br/>".join(r.evidence_paths) if r.evidence_paths else "-"
        note = r.note.replace("|", "\\|") if r.note else "-"
        lines.append(
            f"| {i} | `{r.name}` | {status} | {r.exit_code} | {r.duration_s:.2f} | {ev} | {r.log_path} | {note} |"
        )

    if not overall_pass:
        lines.append("")
        lines.append("## 失败项（按出现顺序）")
        lines.append("")
        for r in results:
            if r.effective_pass:
                continue
            lines.append(f"- `{r.name}`（exit={r.exit_code}）：{r.note or 'FAILED'}")
            if r.evidence_paths:
                for p in r.evidence_paths:
                    lines.append(f"  - 证据：`{p}`")
            lines.append(f"  - runner日志：`{r.log_path}`")

    lines.append("")
    lines.append("## 说明")
    lines.append("")
    lines.append("- 本 runner **不会**执行 PyInstaller / dist / validate_dist_exe 等打包流程。")
    lines.append("- 复杂 Excel 用例的重产物目录默认会被 `.gitignore` 忽略，仅保留报告与 summary JSON。")
    lines.append("")

    report_path = out_dir / "full_selftest_report.md"
    _write_text(report_path, "\n".join(lines) + "\n")

    return overall_pass, results, str(report_path.relative_to(repo_root).as_posix())


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="APS 全量自测 runner（不打包）")
    p.add_argument("--fail-fast", action="store_true", help="遇到第一个失败就停止（默认：继续跑完）")
    p.add_argument("--complex-repeat", type=int, default=1, help="复杂 Excel 用例 repeat 次数（默认 1）")
    p.add_argument("--step-timeout", type=int, default=900, help="每步超时秒数（默认 900；<=0 表示不设超时）")
    args = p.parse_args(list(argv) if argv is not None else None)

    repo_root = _find_repo_root()
    step_timeout_s = int(args.step_timeout)
    if step_timeout_s <= 0:
        step_timeout_s = None
    ok, _results, report_rel = run_full_selftest(
        repo_root=repo_root,
        fail_fast=bool(args.fail_fast),
        complex_repeat=int(args.complex_repeat),
        step_timeout_s=step_timeout_s,
    )

    print(report_rel)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
