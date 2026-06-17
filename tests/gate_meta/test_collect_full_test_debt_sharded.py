"""回归测试：tools.collect_full_test_debt 分片收集器——_sort_reports 按 collect-only nodeid 顺序及 setup/call/teardown 阶段排序报告，_worker_payload_errors 拒绝落在 collect-only nodeid 之外的 worker 报告，_run_sharded_pytest 把 worker 子进程意外打印的 stdout 记成 collection_error 而非静默丢弃。"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

from tools import collect_full_test_debt
from tools.collect_full_test_debt import _sort_reports, _worker_payload_errors


def test_sort_reports_uses_collect_only_nodeid_order() -> None:
    reports = [
        {"nodeid": "tests/test_b.py::test_b", "when": "call"},
        {"nodeid": "tests/test_a.py::test_a", "when": "teardown"},
        {"nodeid": "tests/test_a.py::test_a", "when": "setup"},
        {"nodeid": "tests/test_a.py::test_a", "when": "call"},
    ]

    sorted_reports = _sort_reports(
        reports,
        ["tests/test_a.py::test_a", "tests/test_b.py::test_b"],
    )

    assert [(item["nodeid"], item["when"]) for item in sorted_reports] == [
        ("tests/test_a.py::test_a", "setup"),
        ("tests/test_a.py::test_a", "call"),
        ("tests/test_a.py::test_a", "teardown"),
        ("tests/test_b.py::test_b", "call"),
    ]


def test_worker_payload_errors_rejects_reports_outside_collect_only_nodeids() -> None:
    errors = _worker_payload_errors(
        {
            "reports": [
                {"nodeid": "tests/test_known.py::test_ok", "when": "call"},
                {"nodeid": "tests/test_unknown.py::test_bad", "when": "call"},
            ],
        },
        ["tests/test_known.py::test_ok"],
    )

    assert errors == [
        {
            "nodeid": "tests/test_unknown.py::test_bad",
            "outcome": "failed",
            "longrepr": "worker report nodeid is outside collect-only nodeids",
        }
    ]


def test_run_sharded_pytest_records_worker_stdout_as_collection_error(tmp_path, monkeypatch) -> None:
    def fake_collect(pytest_args):
        assert pytest_args[0] == "--collect-only"
        collector = collect_full_test_debt.FullTestDebtCollector()
        collector.collected_nodeids = ["tests/test_public.py::test_ok"]
        collector.exitstatus = 0
        return collector, 0

    class FakePopen:
        def __init__(self, command, cwd=None, stdout=None, stderr=None, text=None, encoding=None, errors=None) -> None:
            payload_path = command[command.index("--worker-payload") + 1]
            with open(payload_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "schema_version": 1,
                        "exitstatus": 0,
                        "collected_nodeids": ["tests/test_public.py::test_ok"],
                        "collection_errors": [],
                        "reports": [{"nodeid": "tests/test_public.py::test_ok", "when": "call"}],
                    },
                    handle,
                    ensure_ascii=False,
                )
            self.returncode = 0

        def communicate(self):
            return "unexpected worker stdout\n", ""

    monkeypatch.setattr(collect_full_test_debt, "_run_pytest_collect", fake_collect)
    monkeypatch.setattr(collect_full_test_debt.subprocess, "Popen", FakePopen)

    collector, exitstatus = collect_full_test_debt._run_sharded_pytest(
        SimpleNamespace(shard_count=1, baseline_kind="after_main_style_isolation"),
        cwd=tmp_path,
    )

    assert exitstatus == 0
    assert collector.collection_errors == [
        {
            "nodeid": "parallel-1",
            "outcome": "failed",
            "longrepr": "unexpected worker stdout\n",
        }
    ]


def test_run_sharded_pytest_finishes_serial_jobs_before_parallel_jobs(tmp_path, monkeypatch) -> None:
    events = []

    def fake_collect(pytest_args):
        assert pytest_args[0] == "--collect-only"
        collector = collect_full_test_debt.FullTestDebtCollector()
        collector.collected_nodeids = [
            "tests/serial/test_case.py::test_serial",
            "tests/parallel/test_case.py::test_parallel",
        ]
        collector.exitstatus = 0
        return collector, 0

    class FakePopen:
        def __init__(self, command, cwd=None, stdout=None, stderr=None, text=None, encoding=None, errors=None) -> None:
            payload_path = command[command.index("--worker-payload") + 1]
            nodeids_path = command[command.index("--worker-nodeids-file") + 1]
            self.nodeids = tuple(
                line.strip() for line in open(nodeids_path, encoding="utf-8").read().splitlines() if line.strip()
            )
            self.job_kind = "serial" if "tests/serial/test_case.py::test_serial" in self.nodeids else "parallel"
            events.append(("start", self.job_kind))
            with open(payload_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "schema_version": 1,
                        "exitstatus": 0,
                        "collected_nodeids": list(self.nodeids),
                        "collection_errors": [],
                        "reports": [{"nodeid": nodeid, "when": "call"} for nodeid in self.nodeids],
                    },
                    handle,
                    ensure_ascii=False,
                )
            self.returncode = 0

        def communicate(self):
            events.append(("finish", self.job_kind))
            return "", ""

    monkeypatch.setattr(collect_full_test_debt, "_run_pytest_collect", fake_collect)
    monkeypatch.setattr(collect_full_test_debt.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(
        collect_full_test_debt,
        "split_nodeids",
        lambda nodeids, shard_count: (
            ["tests/serial/test_case.py::test_serial"],
            [["tests/parallel/test_case.py::test_parallel"]],
        ),
    )

    collector, exitstatus = collect_full_test_debt._run_sharded_pytest(
        SimpleNamespace(shard_count=1, baseline_kind="after_main_style_isolation"),
        cwd=tmp_path,
    )

    assert exitstatus == 0
    assert collector.collection_errors == []
    assert events == [
        ("start", "serial"),
        ("finish", "serial"),
        ("start", "parallel"),
        ("finish", "parallel"),
    ]


def test_build_payload_records_generation_platform_os_name() -> None:
    """_build_payload 必须把生成平台 os.name 落进 payload，让 verify_required_regressions 的平台
    白名单判定名实相符（跨机复用也正确，而非巧合依赖核销机 os.name）。"""
    collector = collect_full_test_debt.FullTestDebtCollector()
    collector.collected_nodeids = ["tests/test_public.py::test_ok"]
    collector.reports = [{"nodeid": "tests/test_public.py::test_ok", "when": "call", "outcome": "passed"}]
    collector.exitstatus = 0

    payload = collect_full_test_debt._build_payload(
        baseline_kind="after_main_style_isolation",
        importable=False,
        pytest_args=["-q"],
        exitstatus=0,
        collector=collector,
        pytest_version="8.0.0",
        generated_at="2026-06-17T00:00:00",
        head_sha="deadbeef",
        required_paths=["tests/test_public.py"],
        collector_argv=["collect_full_test_debt.py", "--", "-q"],
        git_status_short_before=None,
        worktree_clean_before=None,
    )

    assert payload["os_name"] == os.name


def test_worker_mode_payload_records_os_name(tmp_path, monkeypatch) -> None:
    """worker 子进程自身写出的 payload 也带 os_name，字段齐整、不依赖巧合。"""

    def fake_collect(pytest_args):
        collector = collect_full_test_debt.FullTestDebtCollector()
        collector.collected_nodeids = ["tests/test_public.py::test_ok"]
        collector.reports = [{"nodeid": "tests/test_public.py::test_ok", "when": "call", "outcome": "passed"}]
        collector.exitstatus = 0
        return collector, 0

    monkeypatch.setattr(collect_full_test_debt, "_run_pytest_collect", fake_collect)

    nodeids_file = tmp_path / "job.nodeids"
    nodeids_file.write_text("tests/test_public.py::test_ok\n", encoding="utf-8")
    payload_file = tmp_path / "job.json"

    rc = collect_full_test_debt._run_worker_mode(
        SimpleNamespace(worker_nodeids_file=str(nodeids_file), worker_payload=str(payload_file))
    )

    assert rc == 0
    written = json.loads(payload_file.read_text(encoding="utf-8"))
    assert written["os_name"] == os.name
