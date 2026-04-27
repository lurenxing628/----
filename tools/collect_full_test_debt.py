from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_BEGIN = "<!-- APS-FULL-PYTEST-BASELINE:BEGIN -->"
BASELINE_END = "<!-- APS-FULL-PYTEST-BASELINE:END -->"
SCHEMA_VERSION = 2

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.quality_gate_shared import (  # noqa: E402
    iter_quality_gate_required_tests,
    quality_gate_required_test_nodeid_matches,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _git_head_sha(cwd: Optional[Path] = None) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(cwd or Path.cwd()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if int(completed.returncode) != 0:
        return ""
    return str(completed.stdout or "").strip()


def _git_status_short(cwd: Path) -> List[str]:
    completed = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if int(completed.returncode) != 0:
        raise RuntimeError(str(completed.stderr or completed.stdout or "git status failed").strip())
    return [line for line in str(completed.stdout or "").splitlines() if line.strip()]


def _status_path(line: str) -> str:
    text = str(line or "")[3:].strip()
    if " -> " in text:
        text = text.rsplit(" -> ", 1)[1].strip()
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    return text.replace("\\", "/")


def _relative_to_cwd(path: Path, cwd: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(cwd.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _unexpected_status_lines(lines: Sequence[str], *, allowed_paths: Sequence[str]) -> List[str]:
    allowed = {path.replace("\\", "/") for path in allowed_paths}
    return [line for line in lines if _status_path(line) not in allowed]


def _remove_existing_file(path: Optional[Path]) -> None:
    if path is None:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _longrepr_text(report: Any) -> str:
    text = getattr(report, "longreprtext", None)
    if text is not None:
        return str(text)
    longrepr = getattr(report, "longrepr", None)
    if longrepr is None:
        return ""
    return str(longrepr)


def _report_nodeid(report: Any) -> str:
    nodeid = str(getattr(report, "nodeid", "") or "").strip()
    if nodeid:
        return nodeid
    fspath = str(getattr(report, "fspath", "") or "").strip()
    return fspath.replace(os.sep, "/")


class FullTestDebtCollector:
    def __init__(self) -> None:
        self.collected_nodeids: List[str] = []
        self.collection_errors: List[Dict[str, Any]] = []
        self.reports: List[Dict[str, Any]] = []
        self.exitstatus: Optional[int] = None

    def pytest_collection_modifyitems(self, session: Any, config: Any, items: Sequence[Any]) -> None:
        self.collected_nodeids = [str(item.nodeid) for item in items]

    def pytest_collectreport(self, report: Any) -> None:
        if str(getattr(report, "outcome", "") or "") != "failed":
            return
        self.collection_errors.append(
            {
                "nodeid": _report_nodeid(report),
                "outcome": str(getattr(report, "outcome", "") or ""),
                "longrepr": _longrepr_text(report),
            }
        )

    def pytest_runtest_logreport(self, report: Any) -> None:
        self.reports.append(
            {
                "nodeid": str(report.nodeid),
                "when": str(report.when),
                "outcome": str(report.outcome),
                "duration": float(getattr(report, "duration", 0.0) or 0.0),
                "longrepr": _longrepr_text(report),
            }
        )

    def pytest_sessionfinish(self, session: Any, exitstatus: Any) -> None:
        self.exitstatus = int(exitstatus)


def _nodeid_path(nodeid: str) -> str:
    return str(nodeid or "").split("::", 1)[0]


def _is_main_style_nodeid(nodeid: str) -> bool:
    path = _nodeid_path(nodeid)
    name = os.path.basename(path)
    return name.startswith("regression_") and name.endswith(".py")


def _belongs_to_required_tests(nodeid: str, required_paths: Iterable[str]) -> bool:
    return quality_gate_required_test_nodeid_matches(nodeid, tuple(required_paths))


def _has_main_style_pollution_signature(text: str) -> bool:
    haystack = str(text or "")
    if "_DummyProc" in haystack:
        return True
    if "AttributeError: __enter__" in haystack:
        return True
    return "subprocess.py" in haystack and "Popen" in haystack


def _failed_report_texts(reports: Sequence[Dict[str, Any]], collection_errors: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, List[str]] = {}
    for report in reports:
        if report.get("outcome") != "failed":
            continue
        nodeid = str(report.get("nodeid") or "")
        out.setdefault(nodeid, []).append(str(report.get("longrepr") or ""))
    for error in collection_errors:
        nodeid = str(error.get("nodeid") or "")
        out.setdefault(nodeid, []).append(str(error.get("longrepr") or ""))
    return {nodeid: "\n".join(parts) for nodeid, parts in out.items()}


def _classify_failures(
    reports: Sequence[Dict[str, Any]],
    collection_errors: Sequence[Dict[str, Any]],
    required_paths: Sequence[str],
    baseline_kind: str,
) -> Dict[str, List[str]]:
    failed_texts = _failed_report_texts(reports, collection_errors)
    classifications = {
        "required_or_quality_gate_self_failure": [],
        "main_style_isolation_candidate": [],
        "candidate_test_debt": [],
    }
    for nodeid in sorted(failed_texts):
        text = failed_texts[nodeid]
        if _belongs_to_required_tests(nodeid, required_paths):
            classifications["required_or_quality_gate_self_failure"].append(nodeid)
        elif _has_main_style_pollution_signature(text) or (
            baseline_kind == "raw_before_isolation" and _is_main_style_nodeid(nodeid)
        ):
            classifications["main_style_isolation_candidate"].append(nodeid)
        else:
            classifications["candidate_test_debt"].append(nodeid)
    return classifications


def _summarize(
    collected_nodeids: Sequence[str],
    reports: Sequence[Dict[str, Any]],
    collection_errors: Sequence[Dict[str, Any]],
    classifications: Dict[str, List[str]],
) -> Dict[str, Any]:
    outcome_counts: Dict[str, int] = {}
    failed_nodeids: Set[str] = set()
    for report in reports:
        outcome = str(report.get("outcome") or "")
        when = str(report.get("when") or "")
        key = f"{when}:{outcome}" if when else outcome
        outcome_counts[key] = int(outcome_counts.get(key, 0)) + 1
        if outcome == "failed":
            failed_nodeids.add(str(report.get("nodeid") or ""))
    failed_nodeids.update(str(error.get("nodeid") or "") for error in collection_errors)
    return {
        "collected_count": len(list(collected_nodeids)),
        "failed_nodeid_count": len([nodeid for nodeid in failed_nodeids if nodeid]),
        "collection_error_count": len(list(collection_errors)),
        "outcome_counts": outcome_counts,
        "classification_counts": {key: len(value) for key, value in classifications.items()},
    }


def _build_payload(
    *,
    baseline_kind: str,
    importable: bool,
    pytest_args: Sequence[str],
    exitstatus: int,
    collector: FullTestDebtCollector,
    pytest_version: str,
    generated_at: str,
    head_sha: str,
    required_paths: Sequence[str],
    collector_argv: Sequence[str],
    git_status_short_before: Optional[Sequence[str]],
    worktree_clean_before: Optional[bool],
    importable_blockers: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    classifications = _classify_failures(collector.reports, collector.collection_errors, required_paths, baseline_kind)
    summary = _summarize(collector.collected_nodeids, collector.reports, collector.collection_errors, classifications)
    return {
        "schema_version": SCHEMA_VERSION,
        "baseline_kind": baseline_kind,
        "importable": importable is True,
        "importable_blockers": list(importable_blockers or []),
        "generated_at": generated_at,
        "head_sha": head_sha,
        "collector_argv": list(collector_argv),
        "git_status_short_before": list(git_status_short_before) if git_status_short_before is not None else None,
        "worktree_clean_before": worktree_clean_before,
        "python_executable": sys.executable,
        "python_version": sys.version.splitlines()[0],
        "pytest_version": pytest_version,
        "pytest_args": list(pytest_args),
        "exitstatus": int(exitstatus),
        "collected_nodeids": list(collector.collected_nodeids),
        "collection_errors": list(collector.collection_errors),
        "reports": list(collector.reports),
        "summary": summary,
        "classifications": classifications,
    }


def _render_baseline_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("summary") or {})
    counts = dict(summary.get("classification_counts") or {})
    baseline_kind = str(payload.get("baseline_kind") or "")
    importable = bool(payload.get("importable"))
    candidate_count = int(counts.get("candidate_test_debt") or 0)
    title = "Full pytest P0 raw baseline"
    description = "本文件记录 main-style 子进程隔离前的 full pytest 现场，只用于排查和对比。"
    if baseline_kind == "after_main_style_isolation" and importable and candidate_count > 0:
        title = "Full pytest P0 debt baseline"
        description = "本文件记录 main-style 子进程隔离后的正式 full pytest 债务基线，可作为任务 5 导入测试债务台账的正式输入。"
    elif baseline_kind == "after_main_style_isolation" and importable:
        title = "Full pytest P0 current debt proof baseline"
        description = "本文件记录当前 full pytest 债务证明；当前没有未登记 full pytest 失败，不作为任务 5 的导入种子。"
    elif baseline_kind == "after_main_style_isolation":
        title = "Full pytest P0 after isolation baseline"
        description = "本文件记录 main-style 子进程隔离后的 full pytest 对比现场，只用于任务 3 承接，不允许导入债务台账。"
    lines = [
        f"# {title}",
        "",
        description,
        "",
        f"- baseline_kind: `{payload.get('baseline_kind')}`",
        f"- importable: `{str(payload.get('importable')).lower()}`",
        f"- exitstatus: `{payload.get('exitstatus')}`",
        f"- collected_count: `{summary.get('collected_count')}`",
        f"- failed_nodeid_count: `{summary.get('failed_nodeid_count')}`",
        "",
        BASELINE_BEGIN,
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        BASELINE_END,
        "",
    ]
    return "\n".join(lines)


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    raw_args = list(argv if argv is not None else sys.argv[1:])
    if "--" not in raw_args:
        raise SystemExit(
            "用法：collect_full_test_debt.py [--baseline-kind raw_before_isolation|after_main_style_isolation] "
            "[--write-baseline PATH] -- <pytest args>"
        )
    separator = raw_args.index("--")
    own_args = raw_args[:separator]
    pytest_args = raw_args[separator + 1 :]
    parser = argparse.ArgumentParser(description="Collect full pytest debt facts as structured JSON")
    parser.add_argument(
        "--baseline-kind",
        default="raw_before_isolation",
        choices=["raw_before_isolation", "after_main_style_isolation"],
    )
    parser.add_argument("--write-baseline")
    parser.add_argument("--importable-debt-baseline", action="store_true")
    parsed = parser.parse_args(own_args)
    if not pytest_args:
        parser.error("必须在 -- 后提供 pytest 参数")
    if parsed.importable_debt_baseline and parsed.baseline_kind != "after_main_style_isolation":
        parser.error("--importable-debt-baseline 只能和 --baseline-kind after_main_style_isolation 一起使用")
    if parsed.importable_debt_baseline and not parsed.write_baseline:
        parser.error("--importable-debt-baseline 必须同时提供 --write-baseline")
    parsed.pytest_args = pytest_args
    parsed.collector_argv = raw_args
    return parsed


def _importable_baseline_blockers(payload: Dict[str, Any]) -> List[str]:
    summary = dict(payload.get("summary") or {})
    counts = dict(summary.get("classification_counts") or {})
    blockers: List[str] = []
    if int(payload.get("exitstatus") or 0) not in {0, 1}:
        blockers.append("pytest_exitstatus")
    if int(counts.get("required_or_quality_gate_self_failure") or 0) != 0:
        blockers.append("required_or_quality_gate_self_failure")
    if int(counts.get("main_style_isolation_candidate") or 0) != 0:
        blockers.append("main_style_isolation_candidate")
    if int(summary.get("collection_error_count") or 0) != 0:
        blockers.append("collection_error_count")
    return blockers


def _write_baseline_atomically(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(_render_baseline_markdown(payload))
        tmp_path.replace(path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    import pytest

    cwd = Path.cwd()
    baseline_path = Path(str(args.write_baseline)) if args.write_baseline else None
    target_status_path = _relative_to_cwd(baseline_path, cwd) if baseline_path is not None else ""
    git_status_short_before: Optional[List[str]] = None
    worktree_clean_before: Optional[bool] = None
    if args.importable_debt_baseline:
        try:
            git_status_short_before = _git_status_short(cwd)
        except RuntimeError as exc:
            _remove_existing_file(baseline_path)
            sys.stderr.write(f"dirty_before_baseline: {exc}\n")
            return 2
        worktree_clean_before = not git_status_short_before
        if git_status_short_before:
            _remove_existing_file(baseline_path)
            sys.stderr.write("dirty_before_baseline: 正式测试债务基线生成前工作区必须干净：")
            sys.stderr.write(", ".join(git_status_short_before))
            sys.stderr.write("\n")
            return 2

    logging.raiseExceptions = False
    collector = FullTestDebtCollector()
    pytest_stdout = io.StringIO()
    pytest_stderr = io.StringIO()
    generated_at = _now_iso()
    head_sha = _git_head_sha(cwd)
    required_paths = iter_quality_gate_required_tests()

    with contextlib.redirect_stderr(pytest_stderr):
        with contextlib.redirect_stdout(pytest_stdout):
            exitstatus = int(pytest.main(list(args.pytest_args), plugins=[collector]))
        if collector.exitstatus is not None:
            exitstatus = int(collector.exitstatus)

    payload = _build_payload(
        baseline_kind=str(args.baseline_kind),
        importable=bool(args.importable_debt_baseline),
        pytest_args=list(args.pytest_args),
        exitstatus=exitstatus,
        collector=collector,
        pytest_version=str(getattr(pytest, "__version__", "")),
        generated_at=generated_at,
        head_sha=head_sha,
        required_paths=required_paths,
        collector_argv=list(args.collector_argv),
        git_status_short_before=git_status_short_before,
        worktree_clean_before=worktree_clean_before,
    )
    if args.importable_debt_baseline:
        blockers = _importable_baseline_blockers(payload)
        try:
            after_pytest_status = _git_status_short(cwd)
        except RuntimeError:
            after_pytest_status = ["git_status_after_pytest_failed"]
        unexpected_after_pytest = _unexpected_status_lines(after_pytest_status, allowed_paths=[])
        if unexpected_after_pytest:
            blockers.append("worktree_drift_after_pytest")
            payload["git_status_short_after_pytest"] = after_pytest_status
        if blockers:
            payload["importable"] = False
            payload["importable_blockers"] = blockers
            _remove_existing_file(baseline_path)
            sys.stderr.write("正式测试债务基线不能导入，存在禁入分类或收集错误：")
            sys.stderr.write(", ".join(blockers))
            sys.stderr.write("\n")
            sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            sys.stdout.write("\n")
            return 2
    if args.write_baseline:
        _write_baseline_atomically(Path(str(args.write_baseline)), payload)
        if args.importable_debt_baseline:
            after_write_status = _git_status_short(cwd)
            payload["git_status_short_after_write"] = after_write_status
            unexpected_after_write = _unexpected_status_lines(after_write_status, allowed_paths=[target_status_path])
            if unexpected_after_write:
                payload["importable"] = False
                payload["importable_blockers"] = ["worktree_drift_after_write"]
                _remove_existing_file(baseline_path)
                sys.stderr.write("正式测试债务基线写入后出现非 baseline 文件改动：")
                sys.stderr.write(", ".join(unexpected_after_write))
                sys.stderr.write("\n")
                sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
                sys.stdout.write("\n")
                return 2
            _write_baseline_atomically(Path(str(args.write_baseline)), payload)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    if args.importable_debt_baseline:
        return 0
    return int(exitstatus)


if __name__ == "__main__":
    raise SystemExit(main())
