"""回归测试：tools.collect_full_test_debt 分片收集器——_sort_reports 按 collect-only nodeid 顺序及 setup/call/teardown 阶段排序报告，_worker_payload_errors 拒绝落在 collect-only nodeid 之外的 worker 报告，_run_sharded_pytest 把 worker 子进程意外打印的 stdout 记成 collection_error 而非静默丢弃。"""

from __future__ import annotations

import json
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
