"""Host-only contracts for tools.scan_over_defense; these tests do not enter the product gate."""

from __future__ import annotations

import json
import textwrap

from tools import scan_over_defense as scanner

PROD_SAMPLE = '''
import os
from copy import copy


class Holder:
    def __init__(self):
        self._value = 1

    def derive(self):
        derived = Holder()
        derived._value = 2
        return derived

    @classmethod
    def build(cls):
        built = cls.__new__(cls)
        built._value = 3
        return built

    def zz_unused_method(self):
        return self._value


def reflect_examples(obj, settings, name):
    first = getattr(obj, "zz_attr", None)
    second = hasattr(settings, "flag")
    third = getattr(os, "sep")
    fourth = getattr(obj, name)
    return first, second, third, fourth


def overwrite(value, keep):
    """The docstring is skipped before looking at the first statement."""
    value = compute_default()
    return value, keep


def reuse(value):
    value = value + 1
    return value


def read_first(value):
    print(value)
    value = 2
    return value


def compute_default():
    return 0


def smuggle(target, payload):
    target._cache = payload
    target._count += 1
    target._left, target._right = payload
    target.public = payload
    target.__mangled = payload
    os._zz_patch = payload
    cloned = copy(target)
    cloned._cache = None
    return cloned


module_holder = Holder()
module_holder._value = 9


def zz_dead_helper():
    return 1


def zz_only_tested_helper():
    return 2


def zz_tool_used_helper():
    return 3


def zz_frontend_used_helper():
    return 4


def register(func):
    return func


@register
def zz_decorated_hook():
    return 5


def outer():
    def zz_nested_unused():
        return 6
    return 7


def abc():
    return 8


EXAMPLE = Holder().derive()
__all__ = ["reflect_examples", "overwrite", "reuse", "read_first", "smuggle", "outer"]
'''

FRONTEND_COMPONENT = """
// backend helper mentioned by a contract string: zz_frontend_used_helper
export function Comp({ command, adapter }) {
  if (command.phase === 'rejected' && typeof command.reset === 'function') command.reset();
  if (typeof command.reset === "function") command.reset();
  if (typeof adapter.lookup === 'function') adapter.lookup();
}
"""


def _write(root, rel_path, text):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")


def _mini_repo(root):
    _write(root, "core/__init__.py", "")
    _write(root, "core/sample.py", PROD_SAMPLE)
    _write(root, "core/dup_a.py", "def zz_duplicate_name():\n    return 1\n")
    _write(root, "core/dup_b.py", "def zz_duplicate_name():\n    return 2\n")
    _write(root, "tests/test_sample.py", """
        from core.sample import zz_only_tested_helper


        def test_helper():
            assert zz_only_tested_helper() == 2
    """)
    _write(root, "tools/gen_doc.py", """
        from core.sample import zz_tool_used_helper

        print(zz_tool_used_helper())
    """)
    _write(root, "frontend/workbench/app/Comp.jsx", FRONTEND_COMPONENT)
    _write(root, "frontend/workbench/prototype/Proto.jsx", "if (typeof command.reset === 'function') command.reset();\n")


def _by_kind(result):
    grouped = {}
    for entry in result["entries"]:
        grouped.setdefault(entry["kind"], []).append(entry)
    return grouped


def _symbols(grouped, kind):
    return sorted(symbol for entry in grouped.get(kind, []) for symbol in entry["symbols"])


def test_scan_hits_each_signal_and_skips_exemptions(tmp_path):
    _mini_repo(tmp_path)
    result = scanner.scan(str(tmp_path))
    grouped = _by_kind(result)

    assert result["kind_totals"] == {
        "internal_reflect_literal": 2,
        "param_overwritten": 1,
        "zero_ref_func": 2,
        "test_only_func": 1,
        "foreign_private_attr_assign": 4,
        "js_typeof_command_reset": 2,
    }
    assert _symbols(grouped, "internal_reflect_literal") == ["getattr:zz_attr", "hasattr:flag"]
    assert _symbols(grouped, "param_overwritten") == ["overwrite(value)"]
    assert _symbols(grouped, "zero_ref_func") == ["zz_dead_helper", "zz_unused_method"]
    assert _symbols(grouped, "test_only_func") == ["zz_only_tested_helper"]
    assert _symbols(grouped, "foreign_private_attr_assign") == [
        "target._cache", "target._count", "target._left", "target._right",
    ]
    assert [(entry["path"], entry["lines"]) for entry in grouped["js_typeof_command_reset"]] == [
        ("frontend/workbench/app/Comp.jsx", [3, 4]),
    ]
    assert {entry["path"] for entry in grouped["internal_reflect_literal"]} == {"core/sample.py"}


def test_cli_refresh_then_fail_on_new_ratchet(tmp_path, capsys):
    _mini_repo(tmp_path)
    root = ["--repo-root", str(tmp_path)]

    assert scanner.main(root + ["--fail-on-new"]) == 2
    assert "基线缺失" in capsys.readouterr().err

    assert scanner.main(root + ["--refresh"]) == 0
    baseline_path = tmp_path / ".codestable" / "checkup" / "over_defense_baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert baseline["rule"] == "over_defense"
    assert sum(entry["count"] for entry in baseline["entries"]) == 12
    capsys.readouterr()

    assert scanner.main(root + ["--fail-on-new", "--quiet-when-clean"]) == 0
    assert capsys.readouterr().out == ""
    assert scanner.main(root + ["--fail-on-new"]) == 0
    assert "相对基线无新增债务" in capsys.readouterr().out

    _write(tmp_path, "core/extra.py", 'def run_extra(obj):\n    return getattr(obj, "late")\n\n\n__all__ = ["run_extra"]\n')
    with (tmp_path / "frontend/workbench/app/Comp.jsx").open("a", encoding="utf-8") as handle:
        handle.write("if (typeof command.reset === 'function') command.reset();\n")
    assert scanner.main(root + ["--fail-on-new"]) == 1
    out = capsys.readouterr().out
    assert "新增债务：core/extra.py kind=internal_reflect_literal count=1" in out
    assert "债务增加：frontend/workbench/app/Comp.jsx kind=js_typeof_command_reset 2 -> 3" in out

    assert scanner.main(root + ["--refresh"]) == 1
    assert "刷新被拒绝" in capsys.readouterr().err
    assert scanner.main(root + ["--refresh", "--allow-growth"]) == 0
    capsys.readouterr()
    assert scanner.main(root + ["--fail-on-new"]) == 0


def test_cli_json_and_parse_failure(tmp_path, capsys):
    _mini_repo(tmp_path)
    assert scanner.main(["--repo-root", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rule"] == "over_defense"
    assert payload["total"] == 12

    _write(tmp_path, "core/broken.py", "def broken(:\n    pass\n")
    assert scanner.main(["--repo-root", str(tmp_path), "--fail-on-new"]) == 2
    assert "源码解析失败" in capsys.readouterr().err


def _p(top: str, name: str) -> str:
    return f"{top}/{name}"


def test_refresh_rejects_offsetting_new_debt_with_removed_old_debt(tmp_path, capsys):
    from tools import boundary_baseline, scan_private_imports, scan_sql_boundary

    # 1) boundary_baseline.refresh_growth_error：删 2 处旧债、增 1 处新债（总数 2 -> 1 下降），仍必须拒绝
    previous = {(_p("core", "old.py"), "private_symbol"): 2}
    current_new = {(_p("core", "new.py"), "private_symbol"): 1}
    err = boundary_baseline.refresh_growth_error("private_import", current_new, previous)
    assert err is not None and "刷新被拒绝" in err and f"新增：{_p('core', 'new.py')}" in err

    # 同键计数增加（另一键删更多，总数 3 -> 2 下降），仍必须拒绝
    previous_inc = {(_p("core", "a.py"), "private_symbol"): 1, (_p("core", "b.py"), "private_symbol"): 2}
    current_inc = {(_p("core", "a.py"), "private_symbol"): 2}
    err_inc = boundary_baseline.refresh_growth_error("private_import", current_inc, previous_inc)
    assert err_inc is not None and f"增加：{_p('core', 'a.py')} kind=private_symbol 1 -> 2" in err_inc

    # 纯减少（无 new 无 increased）允许刷新
    assert boundary_baseline.refresh_growth_error("private_import", {(_p("core", "a.py"), "private_symbol"): 1}, previous_inc) is None

    # 2) scan_private_imports & scan_sql_boundary CLI 端到端验证：删旧抵新被拒绝
    _write(tmp_path, _p("core", "mod_a.py"), "_secret_a = 1\n_secret_b = 2\n")
    _write(tmp_path, _p("core", "use_old.py"), "from core.mod_a import _secret_a, _secret_b\n")
    assert scan_private_imports.main(["--repo-root", str(tmp_path), "--refresh"]) == 0
    capsys.readouterr()

    # 删掉 use_old.py 的 2 处旧债，但在 use_new.py 新增 1 处新债（总数 2 -> 1）
    (tmp_path / _p("core", "use_old.py")).unlink()
    _write(tmp_path, _p("core", "use_new.py"), "from core.mod_a import _secret_a\n")
    assert scan_private_imports.main(["--repo-root", str(tmp_path), "--refresh"]) == 1
    assert "刷新被拒绝" in capsys.readouterr().err

    _write(tmp_path, _p("core", "sql_old.py"), 'def q(conn):\n    conn.execute("SELECT 1")\n')
    assert scan_sql_boundary.main(["--repo-root", str(tmp_path), "--rule", "sql_boundary", "--refresh"]) == 0
    capsys.readouterr()
    (tmp_path / _p("core", "sql_old.py")).unlink()
    _write(tmp_path, _p("core", "sql_new.py"), 'def q2(conn):\n    conn.execute("SELECT 1")\n')
    assert scan_sql_boundary.main(["--repo-root", str(tmp_path), "--rule", "sql_boundary", "--refresh"]) == 1
    assert "刷新被拒绝" in capsys.readouterr().err


def test_full_test_debt_verifies_shard_nodeids_and_terminal_reports(tmp_path):
    import pytest

    from tools import collect_full_test_debt as collector_mod
    from tools import test_debt_registry as registry
    from tools.quality_gate_shared import FORMAL_FULL_TEST_PYTEST_ARGS, QualityGateError

    assert collector_mod._merge_exitstatus(0, [{"exitstatus": 1}, {"exitstatus": 3}]) == 3
    assert collector_mod._merge_exitstatus(0, [{"exitstatus": 3}, {"exitstatus": 1}]) == 3
    assert collector_mod._merge_exitstatus(0, [{"exitstatus": 0}, {"exitstatus": 1}]) == 1

    suite_dir = tmp_path / "late_sessionfinish_suite"
    _write(
        suite_dir,
        "conftest.py",
        """
        import pytest


        @pytest.hookimpl(trylast=True)
        def pytest_sessionfinish(session, exitstatus):
            pytest.exit("late sessionfinish failure", returncode=3)
        """,
    )
    _write(
        suite_dir,
        "test_sample_debt.py",
        """
        def test_regular_failure():
            assert False
        """,
    )
    late_collector, late_exitstatus = collector_mod._run_pytest_collect(
        [str(suite_dir), "-q", "-p", "no:cacheprovider"]
    )
    assert late_exitstatus == 3
    assert late_collector.exitstatus == 3
    late_payload = collector_mod._build_payload(
        baseline_kind="after_main_style_isolation",
        importable=True,
        pytest_args=list(FORMAL_FULL_TEST_PYTEST_ARGS),
        exitstatus=late_exitstatus,
        collector=late_collector,
        pytest_version="7.4.4",
        generated_at="2026-10-31T00:00:00+08:00",
        head_sha="deadbeef",
        required_paths=[],
        collector_argv=[],
        git_status_short_before=[],
        worktree_clean_before=True,
    )
    assert "pytest_exitstatus" in collector_mod._importable_baseline_blockers(late_payload)

    n1 = _p("tests", "test_a.py::test_1")
    n2 = _p("tests", "test_a.py::test_2")
    n_ok = _p("tests", "test_a.py::test_ok")
    n_inc = _p("tests", "test_a.py::test_incomplete")
    n_skip = _p("tests", "test_a.py::test_setup_skip")

    # 1) 分片计划与 worker 实际收集不一致必须报错
    errs = collector_mod._worker_payload_errors(
        {
            "collected_nodeids": [n1],
            "reports": [],
        },
        [n1, n2],
        planned_nodeids=[n1, n2],
        label="parallel-1",
    )
    assert any(
        item["nodeid"] == n2 and "did not collect planned nodeid" in item["longrepr"]
        for item in errs
    )

    # 2) 只有 setup:passed 而缺少 call 终态报告必须报错
    missing_term = collector_mod._missing_terminal_report_errors(
        [n_ok, n_inc, n_skip],
        [
            {"nodeid": n_ok, "when": "setup", "outcome": "passed"},
            {"nodeid": n_ok, "when": "call", "outcome": "passed"},
            {"nodeid": n_inc, "when": "setup", "outcome": "passed"},
            {"nodeid": n_skip, "when": "setup", "outcome": "skipped"},
        ],
    )
    assert [item["nodeid"] for item in missing_term] == [n_inc]

    # 3) test_debt_registry.validate_current_candidate_payload 核验全集终态与 teardown 失败
    def _make_report(nodeid: str, when: str, outcome: str):
        return {
            "nodeid": nodeid,
            "when": when,
            "outcome": outcome,
            "xfail_marker_present": False,
            "xfail_marker_reason": "",
            "xfail_marker_strict": False,
            "xfail_marker_run": False,
            "wasxfail_reason": "",
            "strict_xpass": False,
        }

    base_payload = {
        "schema_version": 2,
        "baseline_kind": "after_main_style_isolation",
        "importable": False,
        "importable_blockers": [],
        "exitstatus": 0,
        "pytest_args": list(FORMAL_FULL_TEST_PYTEST_ARGS),
        "collected_nodeids": [n1, n2],
        "collection_errors": [],
        "reports": [
            _make_report(n1, "call", "passed"),
            _make_report(n2, "setup", "skipped"),
        ],
        "classifications": {
            "candidate_test_debt": [],
            "main_style_isolation_candidate": [],
            "required_or_quality_gate_self_failure": [],
        },
        "summary": {
            "collected_count": 2,
            "failed_nodeid_count": 0,
            "collection_error_count": 0,
            "outcome_counts": {"call:passed": 1, "setup:skipped": 1},
            "classification_counts": {
                "candidate_test_debt": 0,
                "main_style_isolation_candidate": 0,
                "required_or_quality_gate_self_failure": 0,
            },
        },
    }
    registry.validate_current_candidate_payload(base_payload, expected_nodeids=[])

    # 缺少终态报告（只有 setup:passed）必须拒绝
    incomplete_payload = {
        **base_payload,
        "reports": [
            _make_report(n1, "call", "passed"),
            _make_report(n2, "setup", "passed"),
        ],
    }
    with pytest.raises(QualityGateError, match="终态报告"):
        registry.validate_current_candidate_payload(incomplete_payload, expected_nodeids=[])

    # teardown 失败必须拒绝（注册表核验与 collect_full_test_debt 生成阶段双重阻断）
    teardown_fail_payload = {
        **base_payload,
        "reports": [
            _make_report(n1, "call", "passed"),
            _make_report(n1, "teardown", "failed"),
            _make_report(n2, "setup", "skipped"),
        ],
        "classifications": {
            "candidate_test_debt": [n1],
            "main_style_isolation_candidate": [],
            "required_or_quality_gate_self_failure": [],
        },
        "summary": {
            "collected_count": 2,
            "failed_nodeid_count": 1,
            "collection_error_count": 0,
            "outcome_counts": {"call:passed": 1, "teardown:failed": 1, "setup:skipped": 1},
            "classification_counts": {
                "candidate_test_debt": 1,
                "main_style_isolation_candidate": 0,
                "required_or_quality_gate_self_failure": 0,
            },
        },
    }
    assert "teardown_failure" in collector_mod._importable_baseline_blockers(teardown_fail_payload)
    with pytest.raises(QualityGateError, match="teardown 失败"):
        registry.validate_current_candidate_payload(teardown_fail_payload, expected_nodeids=[n1])
    with pytest.raises(QualityGateError, match="teardown 失败"):
        registry.validate_importable_baseline({**teardown_fail_payload, "importable": True})
