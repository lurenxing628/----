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
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 2

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.full_test_debt_shards import split_nodeids  # noqa: E402
from tools.quality_gate_shared import (  # noqa: E402
    FORMAL_FULL_TEST_PYTEST_ARGS,
    QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL,
    is_teardown_failure_report,
    is_terminal_pytest_report,
    iter_quality_gate_required_tests,
    quality_gate_required_test_nodeid_matches,
)

CURRENT_PAYLOAD_REL = QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL.replace("\\", "/")
FORMAL_FULL_TEST_PYTEST_OPTIONS = ["-q", "--tb=short", "-ra", "-p", "no:cacheprovider"]


def _progress(message: str) -> None:
    print(f"[collect-full-test-debt] {message}", file=sys.stderr, flush=True)


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


def _git_toplevel(cwd: Path) -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if int(completed.returncode) != 0:
        raise RuntimeError(str(completed.stderr or completed.stdout or "git rev-parse --show-toplevel failed").strip())
    return Path(str(completed.stdout or "").strip()).resolve()


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve())) == os.path.normcase(str(right.resolve()))


def _path_within_root(path: Path, root: Path) -> bool:
    path_text = os.path.normcase(str(path.resolve()))
    root_text = os.path.normcase(str(root.resolve()))
    try:
        common = os.path.commonpath([path_text, root_text])
    except ValueError:
        return False
    return common == root_text


def _resolve_repo_root(raw_repo_root: str) -> Path:
    repo_root = Path(str(raw_repo_root)).resolve()
    git_toplevel = _git_toplevel(repo_root)
    if not _same_path(repo_root, git_toplevel):
        raise RuntimeError(f"--repo-root 必须指向 Git 仓库根目录：repo_root={repo_root}；git_toplevel={git_toplevel}")
    return repo_root


def _resolve_payload_path(raw_path: str, *, repo_root: Path) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = repo_root / path
    resolved = path.resolve()
    if not _path_within_root(resolved, repo_root):
        raise RuntimeError(f"current payload 必须写在 Git 仓库内：path={resolved}；repo_root={repo_root}")
    return resolved


def _relative_to_cwd(path: Path, cwd: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(cwd.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


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

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: Any, call: Any) -> Generator[Any, Any, None]:
        outcome = yield
        report = outcome.get_result()
        marker = item.get_closest_marker("xfail")
        xfail_marker_present = marker is not None
        xfail_marker_reason = ""
        xfail_marker_strict = False
        xfail_marker_run = False
        if marker is not None:
            marker_reason = marker.kwargs.get("reason")
            marker_strict = marker.kwargs.get("strict")
            marker_run = marker.kwargs.get("run", True)
            if marker_reason is not None:
                xfail_marker_reason = str(marker_reason)
            if marker_strict is not None:
                xfail_marker_strict = bool(marker_strict)
            xfail_marker_run = bool(marker_run)
        wasxfail = getattr(report, "wasxfail", None)
        wasxfail_reason = ""
        if wasxfail is not None:
            wasxfail_reason = str(wasxfail)
        strict_xpass = (
            str(report.when) == "call"
            and marker is not None
            and xfail_marker_strict
            and str(report.outcome) == "failed"
            and not wasxfail_reason
            and getattr(call, "excinfo", None) is None
        )
        self.reports.append(
            {
                "nodeid": str(report.nodeid),
                "when": str(report.when),
                "outcome": str(report.outcome),
                "duration": float(getattr(report, "duration", 0.0) or 0.0),
                "longrepr": _longrepr_text(report),
                "xfail_marker_present": xfail_marker_present,
                "xfail_marker_reason": xfail_marker_reason,
                "xfail_marker_strict": xfail_marker_strict,
                "xfail_marker_run": xfail_marker_run,
                "wasxfail_reason": wasxfail_reason,
                "strict_xpass": strict_xpass,
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


def _failed_report_texts(reports: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, List[str]] = {}
    for report in reports:
        if report.get("outcome") != "failed":
            continue
        nodeid = str(report.get("nodeid") or "")
        out.setdefault(nodeid, []).append(str(report.get("longrepr") or ""))
    return {nodeid: "\n".join(parts) for nodeid, parts in out.items()}


def _classify_failures(
    reports: Sequence[Dict[str, Any]],
    required_paths: Sequence[str],
    baseline_kind: str,
) -> Dict[str, List[str]]:
    failed_texts = _failed_report_texts(reports)
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
) -> Dict[str, Any]:
    classifications = _classify_failures(collector.reports, required_paths, baseline_kind)
    summary = _summarize(collector.collected_nodeids, collector.reports, collector.collection_errors, classifications)
    return {
        "schema_version": SCHEMA_VERSION,
        "baseline_kind": baseline_kind,
        "importable": False,
        "importable_blockers": [],
        "generated_at": generated_at,
        "head_sha": head_sha,
        "collector_argv": list(collector_argv),
        "git_status_short_before": list(git_status_short_before) if git_status_short_before is not None else None,
        "worktree_clean_before": worktree_clean_before,
        "python_executable": sys.executable,
        "python_version": sys.version.splitlines()[0],
        "os_name": os.name,
        "pytest_version": pytest_version,
        "pytest_args": list(pytest_args),
        "exitstatus": int(exitstatus),
        "collected_nodeids": list(collector.collected_nodeids),
        "collection_errors": list(collector.collection_errors),
        "reports": list(collector.reports),
        "summary": summary,
        "classifications": classifications,
    }


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    raw_args = list(argv if argv is not None else sys.argv[1:])
    if "--" not in raw_args:
        raise SystemExit(
            "用法：collect_full_test_debt.py [--baseline-kind raw_before_isolation|after_main_style_isolation] "
            "-- <pytest args>"
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
    parser.add_argument("--current-payload-path", default=CURRENT_PAYLOAD_REL)
    parser.add_argument("--no-current-payload", action="store_true")
    parser.add_argument("--repo-root", default=str(Path.cwd()))
    parser.add_argument("--sharded", action="store_true")
    parser.add_argument("--shard-count", type=int, default=3)
    parser.add_argument("--worker-payload")
    parser.add_argument("--worker-nodeids-file")
    parsed = parser.parse_args(own_args)
    try:
        parsed.repo_root = _resolve_repo_root(str(parsed.repo_root))
    except RuntimeError as exc:
        parser.error(str(exc))
    try:
        parsed.current_payload_path = str(
            _resolve_payload_path(parsed.current_payload_path or CURRENT_PAYLOAD_REL, repo_root=parsed.repo_root)
        )
    except RuntimeError as exc:
        parser.error(str(exc))
    if not pytest_args:
        parser.error("必须在 -- 后提供 pytest 参数")
    if parsed.sharded and pytest_args != FORMAL_FULL_TEST_PYTEST_ARGS:
        parser.error("--sharded 目前只支持正式 full pytest 参数：" + " ".join(FORMAL_FULL_TEST_PYTEST_ARGS))
    if int(parsed.shard_count) < 1:
        parser.error("--shard-count 必须大于等于 1")
    if bool(parsed.worker_payload) != bool(parsed.worker_nodeids_file):
        parser.error("--worker-payload 和 --worker-nodeids-file 必须一起提供")
    parsed.pytest_args = pytest_args
    parsed.collector_argv = raw_args
    return parsed


def _write_worker_payload(path: Path, payload: Dict[str, Any]) -> None:
    _write_json_atomically(path, payload)


def _read_nodeids_file(path: Path) -> List[str]:
    with open(path, encoding="utf-8") as handle:
        return [line.strip() for line in handle.read().splitlines() if line.strip()]


def _run_pytest_collect(pytest_args: Sequence[str]) -> Tuple[FullTestDebtCollector, int]:
    collector = FullTestDebtCollector()
    pytest_stdout = io.StringIO()
    pytest_stderr = io.StringIO()
    with contextlib.redirect_stderr(pytest_stderr):
        with contextlib.redirect_stdout(pytest_stdout):
            exitstatus = int(pytest.main(list(pytest_args), plugins=[collector]))
    if exitstatus == 0 and collector.exitstatus not in (None, 0):
        exitstatus = int(collector.exitstatus)
    collector.exitstatus = exitstatus
    return collector, exitstatus


def _run_worker_mode(args: argparse.Namespace) -> int:
    nodeids = _read_nodeids_file(Path(str(args.worker_nodeids_file)))
    collector, exitstatus = _run_pytest_collect([*nodeids, *FORMAL_FULL_TEST_PYTEST_OPTIONS])
    _write_worker_payload(
        Path(str(args.worker_payload)),
        {
            "schema_version": 1,
            "exitstatus": int(exitstatus),
            "os_name": os.name,
            "collected_nodeids": list(collector.collected_nodeids),
            "collection_errors": list(collector.collection_errors),
            "reports": list(collector.reports),
        },
    )
    return int(exitstatus)


def _write_nodeids_file(path: Path, nodeids: Sequence[str]) -> None:
    path.write_text("\n".join(str(item) for item in nodeids) + ("\n" if nodeids else ""), encoding="utf-8")


def _worker_payload_path(work_dir: Path, label: str) -> Path:
    return work_dir / f"{label}.json"


def _worker_nodeids_path(work_dir: Path, label: str) -> Path:
    return work_dir / f"{label}.nodeids"


def _merge_exitstatus(collect_exitstatus: int, worker_payloads: Sequence[Mapping[str, Any]]) -> int:
    if int(collect_exitstatus) != 0:
        return int(collect_exitstatus)
    worker_exitstatuses = [int(payload.get("exitstatus") or 0) for payload in worker_payloads]
    for status in worker_exitstatuses:
        if status not in (0, 1):
            return status
    if any(status == 1 for status in worker_exitstatuses):
        return 1
    return 0


def _sort_reports(reports: Sequence[Dict[str, Any]], collected_nodeids: Sequence[str]) -> List[Dict[str, Any]]:
    nodeid_order = {str(nodeid): index for index, nodeid in enumerate(collected_nodeids)}
    when_order = {"setup": 0, "call": 1, "teardown": 2}
    indexed = list(enumerate(reports))
    indexed.sort(
        key=lambda item: (
            nodeid_order.get(str(item[1].get("nodeid") or ""), len(nodeid_order)),
            when_order.get(str(item[1].get("when") or ""), 99),
            item[0],
        )
    )
    return [dict(report) for _, report in indexed]


def _missing_terminal_report_errors(
    collected_nodeids: Sequence[str],
    reports: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    terminal_nodeids = {
        str(report.get("nodeid") or "")
        for report in reports
        if is_terminal_pytest_report(str(report.get("when") or ""), str(report.get("outcome") or ""))
    }
    return [
        {
            "nodeid": str(nodeid),
            "outcome": "failed",
            "longrepr": "collected nodeid is missing terminal pytest report",
        }
        for nodeid in collected_nodeids
        if str(nodeid) not in terminal_nodeids
    ]


def _teardown_failed_nodeids(reports: Sequence[Mapping[str, Any]]) -> List[str]:
    return sorted(
        {
            str(report.get("nodeid") or "")
            for report in reports
            if is_teardown_failure_report(str(report.get("when") or ""), str(report.get("outcome") or ""))
            and str(report.get("nodeid") or "")
        }
    )


def _worker_payload_errors(
    payload: Mapping[str, Any],
    collected_nodeids: Sequence[str],
    *,
    planned_nodeids: Sequence[str],
    label: str,
) -> List[Dict[str, Any]]:
    collected = {str(nodeid) for nodeid in collected_nodeids}
    errors: List[Dict[str, Any]] = []
    planned_list = [str(nodeid) for nodeid in planned_nodeids]
    worker_collected = [str(nodeid) for nodeid in list(payload.get("collected_nodeids") or [])]
    if worker_collected != planned_list:
        planned_set = set(planned_list)
        worker_set = set(worker_collected)
        missing = [nodeid for nodeid in planned_list if nodeid not in worker_set]
        extra = [nodeid for nodeid in worker_collected if nodeid not in planned_set]
        for nodeid in missing:
            errors.append(
                {
                    "nodeid": nodeid,
                    "outcome": "failed",
                    "longrepr": f"worker {label} did not collect planned nodeid",
                }
            )
        for nodeid in extra:
            errors.append(
                {
                    "nodeid": nodeid,
                    "outcome": "failed",
                    "longrepr": f"worker {label} collected unexpected nodeid outside shard plan",
                }
            )
        if not missing and not extra:
            errors.append(
                {
                    "nodeid": label,
                    "outcome": "failed",
                    "longrepr": f"worker {label} collected_nodeids order or duplicate mismatch with planned job_nodeids",
                }
            )
    allowed_for_worker = set(planned_list)
    for report in list(payload.get("reports") or []):
        nodeid = str(report.get("nodeid") or "")
        if nodeid and nodeid not in collected:
            errors.append(
                {
                    "nodeid": nodeid,
                    "outcome": "failed",
                    "longrepr": "worker report nodeid is outside collect-only nodeids",
                }
            )
        elif nodeid and nodeid not in allowed_for_worker:
            errors.append(
                {
                    "nodeid": nodeid,
                    "outcome": "failed",
                    "longrepr": f"worker {label} report nodeid is outside planned shard nodeids",
                }
            )
    return errors


def _run_sharded_pytest(args: argparse.Namespace, *, cwd: Path) -> Tuple[FullTestDebtCollector, int]:
    collect_args = ["--collect-only", *FORMAL_FULL_TEST_PYTEST_ARGS]
    _progress("sharded 模式：先 collect-only 建立完整 nodeid 清单")
    collect_collector, collect_exitstatus = _run_pytest_collect(collect_args)
    collector = FullTestDebtCollector()
    collector.collected_nodeids = list(collect_collector.collected_nodeids)
    collector.collection_errors = list(collect_collector.collection_errors)
    if int(collect_exitstatus) != 0:
        collector.exitstatus = int(collect_exitstatus)
        return collector, int(collect_exitstatus)

    serial_nodeids, parallel_shards = split_nodeids(collector.collected_nodeids, int(args.shard_count))
    serial_jobs: List[Tuple[str, Sequence[str]]] = []
    parallel_jobs: List[Tuple[str, Sequence[str]]] = []
    if serial_nodeids:
        serial_jobs.append(("serial", serial_nodeids))
    for index, shard_nodeids in enumerate(parallel_shards, start=1):
        if shard_nodeids:
            parallel_jobs.append((f"parallel-{index}", shard_nodeids))
    worker_runs: List[Tuple[str, List[str], Dict[str, Any]]] = []
    worker_output_errors: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="aps_full_test_debt_shards_") as tmp_dir:
        work_dir = Path(tmp_dir)

        def _start_jobs(jobs: Sequence[Tuple[str, Sequence[str]]]):
            processes = []
            for label, job_nodeids in jobs:
                planned_list = [str(item) for item in job_nodeids]
                payload_path = _worker_payload_path(work_dir, label)
                nodeids_path = _worker_nodeids_path(work_dir, label)
                _write_nodeids_file(nodeids_path, planned_list)
                command = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--baseline-kind",
                    str(args.baseline_kind),
                    "--repo-root",
                    str(cwd),
                    "--worker-payload",
                    str(payload_path),
                    "--worker-nodeids-file",
                    str(nodeids_path),
                    "--",
                    *FORMAL_FULL_TEST_PYTEST_ARGS,
                ]
                _progress(f"sharded 模式：启动分片 {label}，{len(planned_list)} 个 nodeid")
                processes.append(
                    (
                        label,
                        planned_list,
                        payload_path,
                        subprocess.Popen(
                            command,
                            cwd=str(cwd),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                        ),
                    )
                )
            return processes

        def _collect_processes(processes) -> None:
            for label, planned_list, payload_path, process in processes:
                stdout, stderr = process.communicate()
                returncode = int(process.returncode or 0)
                if stdout or stderr:
                    worker_output_errors.append(
                        {
                            "nodeid": label,
                            "outcome": "failed",
                            "longrepr": str(stderr or stdout),
                        }
                    )
                if payload_path.exists():
                    with open(payload_path, encoding="utf-8") as handle:
                        payload = json.load(handle)
                    if isinstance(payload, dict):
                        if returncode != int(payload.get("exitstatus") or 0):
                            payload["exitstatus"] = returncode
                        payload["reports"] = [
                            dict(report) for report in list(payload.get("reports") or []) if isinstance(report, dict)
                        ]
                        payload["collection_errors"] = [
                            dict(error)
                            for error in list(payload.get("collection_errors") or [])
                            if isinstance(error, dict)
                        ]
                        worker_runs.append((label, planned_list, payload))
                        continue
                worker_runs.append(
                    (
                        label,
                        planned_list,
                        {
                            "schema_version": 1,
                            "exitstatus": returncode,
                            "collected_nodeids": [],
                            "collection_errors": [
                                {"nodeid": label, "outcome": "failed", "longrepr": "worker did not write payload"}
                            ],
                            "reports": [],
                        },
                    )
                )

        _collect_processes(_start_jobs(serial_jobs))
        _collect_processes(_start_jobs(parallel_jobs))

    worker_payloads = [payload for _label, _planned, payload in worker_runs]
    reports: List[Dict[str, Any]] = []
    collection_errors = [*list(collector.collection_errors), *worker_output_errors]
    for label, planned_list, payload in worker_runs:
        reports.extend(payload["reports"])
        collection_errors.extend(
            _worker_payload_errors(
                payload,
                collector.collected_nodeids,
                planned_nodeids=planned_list,
                label=label,
            )
        )
        collection_errors.extend(payload["collection_errors"])
    existing_error_nodeids = {str(item.get("nodeid") or "") for item in collection_errors}
    for error in _missing_terminal_report_errors(collector.collected_nodeids, reports):
        if str(error.get("nodeid") or "") not in existing_error_nodeids:
            collection_errors.append(error)
    collector.reports = _sort_reports(reports, collector.collected_nodeids)
    collector.collection_errors = sorted(collection_errors, key=lambda item: str(item.get("nodeid") or ""))
    merged_exitstatus = _merge_exitstatus(collect_exitstatus, worker_payloads)
    if (collector.collection_errors or _teardown_failed_nodeids(collector.reports)) and merged_exitstatus == 0:
        merged_exitstatus = 1
    collector.exitstatus = merged_exitstatus
    return collector, int(collector.exitstatus)


def _write_json_atomically(path: Path, payload: Dict[str, Any]) -> None:
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
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        tmp_path.replace(path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def _first_line(text: str) -> str:
    return next((line.strip() for line in str(text or "").splitlines() if line.strip()), "")


def _render_failure_preview(payload: Dict[str, Any], *, limit: int = 10) -> str:
    lines = ["full test debt 收集发现失败分类："]
    classifications = dict(payload.get("classifications") or {})
    for key in [
        "required_or_quality_gate_self_failure",
        "main_style_isolation_candidate",
        "candidate_test_debt",
    ]:
        nodeids = [str(nodeid) for nodeid in list(classifications.get(key) or [])]
        if not nodeids:
            continue
        lines.append(f"- {key}（{len(nodeids)} 个）：")
        for nodeid in nodeids[:limit]:
            lines.append(f"  - {nodeid}")
        if len(nodeids) > limit:
            lines.append(f"  - ... 另外 {len(nodeids) - limit} 个未显示")
    collection_errors = list(payload.get("collection_errors") or [])
    if collection_errors:
        lines.append(f"- collection_errors（{len(collection_errors)} 个）：")
        for item in collection_errors[:limit]:
            if isinstance(item, dict):
                nodeid = str(item.get("nodeid") or "<unknown>")
                detail = _first_line(str(item.get("longrepr") or ""))
                lines.append(f"  - {nodeid}" + (f"：{detail}" if detail else ""))
            else:
                lines.append(f"  - {item}")
        if len(collection_errors) > limit:
            lines.append(f"  - ... 另外 {len(collection_errors) - limit} 个未显示")
    blockers = [str(item) for item in list(payload.get("importable_blockers") or [])]
    if blockers:
        lines.append("- importable_blockers：" + ", ".join(blockers[:limit]))
    lines.append(f"完整 JSON 已写入：{CURRENT_PAYLOAD_REL}")
    return "\n".join(lines)


def _payload_has_failure_preview(payload: Dict[str, Any]) -> bool:
    classifications = dict(payload.get("classifications") or {})
    return any(list(classifications.get(key) or []) for key in classifications) or bool(
        payload.get("collection_errors") or payload.get("importable_blockers")
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    import pytest

    cwd = Path(str(args.repo_root)).resolve()
    os.chdir(cwd)
    if args.worker_payload:
        return _run_worker_mode(args)
    current_payload_path = Path(str(args.current_payload_path))
    current_status_path = _relative_to_cwd(current_payload_path, cwd)
    git_status_short_before: Optional[List[str]] = None
    worktree_clean_before: Optional[bool] = None
    should_record_worktree = str(args.baseline_kind) == "after_main_style_isolation"
    if should_record_worktree:
        try:
            git_status_short_before = _git_status_short(cwd)
        except RuntimeError as exc:
            print(f"dirty_before_baseline: {exc}", file=sys.stderr, flush=True)
            return 2
        worktree_clean_before = not git_status_short_before

    def write_current_payload(payload_to_write: Dict[str, Any]) -> None:
        if bool(args.no_current_payload):
            _progress("跳过 current payload 写入：--no-current-payload")
            return
        _progress(f"正在写入 current payload：{current_status_path}")
        _write_json_atomically(current_payload_path, payload_to_write)
        _progress(f"已写入 current payload：{current_status_path}")

    logging.raiseExceptions = False
    generated_at = _now_iso()
    head_sha = _git_head_sha(cwd)
    required_paths = iter_quality_gate_required_tests()

    if args.sharded:
        _progress(f"开始执行 sharded pytest 并收集 full-test-debt 结果：shard_count={int(args.shard_count)}")
        collector, exitstatus = _run_sharded_pytest(args, cwd=cwd)
    else:
        _progress("开始执行 pytest 并收集 full-test-debt 结果")
        collector, exitstatus = _run_pytest_collect(list(args.pytest_args))
        existing_error_nodeids = {str(item.get("nodeid") or "") for item in collector.collection_errors}
        for error in _missing_terminal_report_errors(collector.collected_nodeids, collector.reports):
            if str(error.get("nodeid") or "") not in existing_error_nodeids:
                collector.collection_errors.append(error)
        if (collector.collection_errors or _teardown_failed_nodeids(collector.reports)) and exitstatus == 0:
            exitstatus = 1
            collector.exitstatus = 1

    _progress(f"pytest 执行完成：exitstatus={exitstatus}；开始分类失败与构建 payload")
    payload = _build_payload(
        baseline_kind=str(args.baseline_kind),
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
    if _payload_has_failure_preview(payload):
        print(_render_failure_preview(payload), file=sys.stderr, flush=True)
    write_current_payload(payload)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    sys.stdout.flush()
    return int(exitstatus)


if __name__ == "__main__":
    raise SystemExit(main())
