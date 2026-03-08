from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

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


def _find_repo_root() -> Path:
    """
    优先从本脚本位置向上找（.cursor/skills/...），找到包含 app.py + schema.sql 的目录即 repo root。
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


def _build_steps(repo_root: Path, *, complex_repeat: int) -> List[tuple[str, List[str], List[str]]]:
    """
    返回 (step_name, cmd, evidence_paths[])。
    cmd 中的脚本路径使用 repo 内相对路径（runner 以 repo_root 为 cwd）。
    """
    py = sys.executable or "python"

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
    reg_files = sorted((repo_root / "tests").glob("regression_*.py"), key=lambda p: p.name)
    for p in reg_files:
        steps.append((p.name, [py, f"tests/{p.name}"], []))

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
                note = "exit_code!=0"

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
    lines.append("")

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

