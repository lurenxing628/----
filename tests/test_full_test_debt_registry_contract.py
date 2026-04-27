from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tools.quality_gate_shared import QUALITY_GATE_SELFTEST_PATH

REPO_ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = REPO_ROOT / "tools" / "collect_full_test_debt.py"
BASELINE_BEGIN = "<!-- APS-FULL-PYTEST-BASELINE:BEGIN -->"
BASELINE_END = "<!-- APS-FULL-PYTEST-BASELINE:END -->"
_ORIGINAL_POPEN = subprocess.Popen


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def _init_clean_git_repo(project: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(project), check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=str(project), check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test Runner",
            "commit",
            "-m",
            "test baseline",
        ],
        cwd=str(project),
        check=True,
        capture_output=True,
        text=True,
    )


def _write_main_style_conftest(project: Path) -> None:
    _write(
        project / "tests" / "conftest.py",
        r'''
        from __future__ import annotations

        import importlib.util
        import re
        import sys
        from pathlib import Path

        import pytest

        _MAIN_DEF_RE = re.compile(r"(?m)^\s*def\s+main\s*\(")
        _TEST_DEF_RE = re.compile(r"(?m)^\s*def\s+test_")


        def _as_path(raw_path):
            raw = getattr(raw_path, "strpath", raw_path)
            return Path(str(raw))


        def _is_main_style_regression(path: Path) -> bool:
            if path.suffix != ".py" or not path.name.startswith("regression_"):
                return False
            text = path.read_text(encoding="utf-8")
            return bool(_MAIN_DEF_RE.search(text)) and not bool(_TEST_DEF_RE.search(text))


        def _node_path(node) -> Path:
            raw = getattr(node, "path", None)
            if raw is not None:
                return Path(str(raw))
            return Path(str(node.fspath))


        def pytest_collect_file(file_path, parent):
            path = _as_path(file_path)
            if not _is_main_style_regression(path):
                return None
            try:
                return RegressionMainFile.from_parent(parent, path=path)
            except TypeError:
                return RegressionMainFile.from_parent(parent, fspath=file_path)


        class RegressionMainFile(pytest.File):
            def collect(self):
                yield RegressionMainItem.from_parent(self, name=_node_path(self).stem)


        class RegressionMainItem(pytest.Item):
            def runtest(self) -> None:
                path = _node_path(self.parent)
                module_name = f"_contract_regression_{path.stem}"
                spec = importlib.util.spec_from_file_location(module_name, str(path))
                if spec is None or spec.loader is None:
                    raise RuntimeError(f"cannot load {path}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                try:
                    spec.loader.exec_module(module)
                    rc = module.main()
                    if isinstance(rc, int) and rc != 0:
                        raise AssertionError(f"{path.name} returned {rc}")
                finally:
                    sys.modules.pop(module_name, None)

            def reportinfo(self):
                path = _node_path(self.parent)
                return path, 0, f"regression-main: {path.name}"
        ''',
    )


def _run_collector(project: Path, *extra_args: str, baseline_kind: str = "raw_before_isolation") -> subprocess.CompletedProcess:
    command = [
        sys.executable,
        str(COLLECTOR),
        "--baseline-kind",
        baseline_kind,
        *extra_args,
        "--",
        "tests",
        "-q",
        "--tb=short",
        "-p",
        "no:cacheprovider",
    ]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with _ORIGINAL_POPEN(
        command,
        cwd=str(project),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    ) as proc:
        stdout, stderr = proc.communicate()
    return subprocess.CompletedProcess(command, int(proc.returncode), stdout, stderr)


def _payload_from_stdout(proc: subprocess.CompletedProcess) -> dict:
    assert proc.stdout.strip().startswith("{")
    assert proc.stdout.strip().endswith("}")
    return dict(json.loads(proc.stdout))


def _payload_from_baseline(path: Path) -> dict:
    baseline_text = path.read_text(encoding="utf-8")
    block = baseline_text.split(BASELINE_BEGIN, 1)[1].split(BASELINE_END, 1)[0].strip()
    if block.startswith("```json"):
        block = block[len("```json") :].strip()
    if block.endswith("```"):
        block = block[: -len("```")].strip()
    return dict(json.loads(block))


def test_collect_full_test_debt_records_nodeids_without_parsing_terminal_text(tmp_path: Path) -> None:
    _write_main_style_conftest(tmp_path)
    _write(
        tmp_path / "tests" / "test_sample.py",
        '''
        import pytest


        def test_plain_pass():
            print("NOISY_STDOUT_SHOULD_NOT_LEAK")
            assert True


        def test_plain_fail():
            assert False, "plain failure"


        @pytest.mark.parametrize("value", [1, 2])
        def test_param(value):
            assert value == 1


        @pytest.fixture
        def broken_setup():
            raise RuntimeError("setup boom")


        def test_setup_failure(broken_setup):
            assert True


        @pytest.fixture
        def broken_teardown():
            yield
            raise RuntimeError("teardown boom")


        def test_teardown_failure(broken_teardown):
            assert True
        ''',
    )
    _write(
        tmp_path / "tests" / "regression_x.py",
        '''
        def main():
            return 2
        ''',
    )

    proc = _run_collector(tmp_path)
    payload = _payload_from_stdout(proc)

    assert proc.returncode == payload["exitstatus"]
    assert proc.returncode == 1
    assert "NOISY_STDOUT_SHOULD_NOT_LEAK" not in proc.stdout
    assert payload["schema_version"] == 2
    assert payload["baseline_kind"] == "raw_before_isolation"
    assert payload["importable"] is False
    assert payload["pytest_args"] == ["tests", "-q", "--tb=short", "-p", "no:cacheprovider"]
    assert "tests/test_sample.py::test_param[2]" in payload["collected_nodeids"]
    assert "tests/regression_x.py::regression_x" in payload["collected_nodeids"]
    report_keys = {"nodeid", "when", "outcome", "duration", "longrepr"}
    assert all(report_keys <= set(report) for report in payload["reports"])
    assert any(
        report["nodeid"] == "tests/test_sample.py::test_setup_failure"
        and report["when"] == "setup"
        and report["outcome"] == "failed"
        for report in payload["reports"]
    )
    assert any(
        report["nodeid"] == "tests/test_sample.py::test_teardown_failure"
        and report["when"] == "teardown"
        and report["outcome"] == "failed"
        for report in payload["reports"]
    )
    assert "tests/regression_x.py::regression_x" in payload["classifications"]["main_style_isolation_candidate"]


def test_collect_full_test_debt_records_collection_errors_and_exitstatus(tmp_path: Path) -> None:
    _write(
        tmp_path / "tests" / "test_collect_error.py",
        '''
        raise RuntimeError("collect boom")
        ''',
    )

    proc = _run_collector(tmp_path)
    payload = _payload_from_stdout(proc)

    assert proc.returncode == payload["exitstatus"]
    assert proc.returncode != 0
    assert payload["collection_errors"]
    assert payload["collection_errors"][0]["outcome"] == "failed"
    assert "collect boom" in payload["collection_errors"][0]["longrepr"]


def test_collect_full_test_debt_writes_raw_baseline_machine_block(tmp_path: Path) -> None:
    _write(
        tmp_path / "tests" / "test_run_quality_gate.py",
        '''
        def test_quality_gate_self_failure():
            assert False, "required failure"
        ''',
    )
    baseline_path = tmp_path / "audit" / "baseline.md"

    proc = _run_collector(tmp_path, "--write-baseline", str(baseline_path))
    payload = _payload_from_stdout(proc)
    baseline_payload = _payload_from_baseline(baseline_path)

    assert payload["importable"] is False
    assert baseline_payload["baseline_kind"] == "raw_before_isolation"
    assert baseline_payload["importable"] is False
    assert payload["summary"] == baseline_payload["summary"]
    assert "tests/test_run_quality_gate.py::test_quality_gate_self_failure" in baseline_payload["classifications"][
        "required_or_quality_gate_self_failure"
    ]


def test_collect_full_test_debt_keeps_required_failures_out_of_candidate_debt(tmp_path: Path) -> None:
    required_nodeid = f"{QUALITY_GATE_SELFTEST_PATH}::test_quality_gate_self_failure"
    regular_nodeid = "tests/test_regular_failure.py::test_regular_failure"
    _write(
        tmp_path / QUALITY_GATE_SELFTEST_PATH,
        '''
        def test_quality_gate_self_failure():
            assert False, "required failure"
        ''',
    )
    _write(
        tmp_path / "tests" / "test_regular_failure.py",
        '''
        def test_regular_failure():
            assert False, "regular failure"
        ''',
    )

    proc = _run_collector(tmp_path, baseline_kind="after_main_style_isolation")
    payload = _payload_from_stdout(proc)

    assert proc.returncode == payload["exitstatus"]
    assert payload["baseline_kind"] == "after_main_style_isolation"
    assert payload["importable"] is False
    assert required_nodeid in payload["classifications"]["required_or_quality_gate_self_failure"]
    assert required_nodeid not in payload["classifications"]["candidate_test_debt"]
    assert required_nodeid not in payload["classifications"]["main_style_isolation_candidate"]
    assert regular_nodeid in payload["classifications"]["candidate_test_debt"]


def test_collect_full_test_debt_after_isolation_does_not_hide_real_regression_failures(tmp_path: Path) -> None:
    _write_main_style_conftest(tmp_path)
    _write(
        tmp_path / "tests" / "regression_real_failure.py",
        '''
        def main():
            return 2
        ''',
    )
    _write(
        tmp_path / "tests" / "test_pollution_signature.py",
        '''
        def test_pollution_signature_failure():
            raise RuntimeError("AttributeError: __enter__ from subprocess.py Popen")
        ''',
    )

    proc = _run_collector(tmp_path, baseline_kind="after_main_style_isolation")
    payload = _payload_from_stdout(proc)

    assert proc.returncode == payload["exitstatus"]
    assert payload["baseline_kind"] == "after_main_style_isolation"
    assert payload["importable"] is False
    assert "tests/regression_real_failure.py::regression_real_failure" in payload["classifications"]["candidate_test_debt"]
    assert (
        "tests/regression_real_failure.py::regression_real_failure"
        not in payload["classifications"]["main_style_isolation_candidate"]
    )
    assert "tests/test_pollution_signature.py::test_pollution_signature_failure" in payload["classifications"][
        "main_style_isolation_candidate"
    ]


def test_collect_full_test_debt_writes_importable_debt_baseline(tmp_path: Path) -> None:
    baseline_path = tmp_path / "audit" / "debt_baseline.md"
    debt_nodeid = "tests/test_debt_candidate.py::test_debt_candidate"
    _write(
        tmp_path / "tests" / "test_debt_candidate.py",
        '''
        def test_debt_candidate():
            assert False, "known debt"
        ''',
    )
    _init_clean_git_repo(tmp_path)

    proc = _run_collector(
        tmp_path,
        "--importable-debt-baseline",
        "--write-baseline",
        str(baseline_path),
        baseline_kind="after_main_style_isolation",
    )
    payload = _payload_from_stdout(proc)
    baseline_payload = _payload_from_baseline(baseline_path)
    baseline_text = baseline_path.read_text(encoding="utf-8")

    assert proc.returncode == 0
    assert payload["schema_version"] == 2
    assert payload["exitstatus"] == 1
    assert payload["baseline_kind"] == "after_main_style_isolation"
    assert payload["importable"] is True
    assert payload["worktree_clean_before"] is True
    assert payload["git_status_short_before"] == []
    assert "--importable-debt-baseline" in payload["collector_argv"]
    assert debt_nodeid in payload["classifications"]["candidate_test_debt"]
    assert payload["summary"]["classification_counts"] == {
        "candidate_test_debt": 1,
        "main_style_isolation_candidate": 0,
        "required_or_quality_gate_self_failure": 0,
    }
    assert payload["summary"] == baseline_payload["summary"]
    assert payload["classifications"] == baseline_payload["classifications"]
    assert baseline_payload["importable"] is True
    assert "Full pytest P0 debt baseline" in baseline_text
    assert "可作为任务 5 导入测试债务台账的正式输入" in baseline_text
    assert "不允许导入债务台账" not in baseline_text


def test_collect_full_test_debt_importable_requires_after_isolation_and_output_file(tmp_path: Path) -> None:
    baseline_path = tmp_path / "audit" / "debt_baseline.md"
    _write(
        tmp_path / "tests" / "test_debt_candidate.py",
        '''
        def test_debt_candidate():
            assert False, "known debt"
        ''',
    )

    raw_proc = _run_collector(
        tmp_path,
        "--importable-debt-baseline",
        "--write-baseline",
        str(baseline_path),
        baseline_kind="raw_before_isolation",
    )
    no_file_proc = _run_collector(
        tmp_path,
        "--importable-debt-baseline",
        baseline_kind="after_main_style_isolation",
    )

    assert raw_proc.returncode == 2
    assert no_file_proc.returncode == 2
    assert "after_main_style_isolation" in raw_proc.stderr
    assert "--write-baseline" in no_file_proc.stderr
    assert not baseline_path.exists()


def test_collect_full_test_debt_importable_requires_clean_worktree(tmp_path: Path) -> None:
    baseline_path = tmp_path / "audit" / "debt_baseline.md"
    _write(
        tmp_path / "tests" / "test_debt_candidate.py",
        '''
        def test_debt_candidate():
            assert False, "known debt"
        ''',
    )
    _init_clean_git_repo(tmp_path)
    _write(tmp_path / "dirty.txt", "not committed")

    proc = _run_collector(
        tmp_path,
        "--importable-debt-baseline",
        "--write-baseline",
        str(baseline_path),
        baseline_kind="after_main_style_isolation",
    )

    assert proc.returncode == 2
    assert "dirty_before_baseline" in proc.stderr
    assert not baseline_path.exists()
    assert not proc.stdout.strip()


def test_collect_full_test_debt_importable_rejects_blocked_classifications(tmp_path: Path) -> None:
    required_path = tmp_path / "required" / "baseline.md"
    pollution_path = tmp_path / "pollution" / "baseline.md"
    collection_error_path = tmp_path / "collection_error" / "baseline.md"

    required_project = tmp_path / "required"
    _write(
        required_project / QUALITY_GATE_SELFTEST_PATH,
        '''
        def test_quality_gate_self_failure():
            assert False, "required failure"
        ''',
    )
    _write(required_path, "STALE IMPORTABLE BASELINE")
    _init_clean_git_repo(required_project)
    required_proc = _run_collector(
        required_project,
        "--importable-debt-baseline",
        "--write-baseline",
        str(required_path),
        baseline_kind="after_main_style_isolation",
    )

    pollution_project = tmp_path / "pollution"
    _write(
        pollution_project / "tests" / "test_pollution_signature.py",
        '''
        def test_pollution_signature_failure():
            raise RuntimeError("AttributeError: __enter__ from subprocess.py Popen")
        ''',
    )
    _write(pollution_path, "STALE IMPORTABLE BASELINE")
    _init_clean_git_repo(pollution_project)
    pollution_proc = _run_collector(
        pollution_project,
        "--importable-debt-baseline",
        "--write-baseline",
        str(pollution_path),
        baseline_kind="after_main_style_isolation",
    )

    collection_error_project = tmp_path / "collection_error"
    _write(
        collection_error_project / "tests" / "test_collect_error.py",
        '''
        raise RuntimeError("collect boom")
        ''',
    )
    _write(collection_error_path, "STALE IMPORTABLE BASELINE")
    _init_clean_git_repo(collection_error_project)
    collection_error_proc = _run_collector(
        collection_error_project,
        "--importable-debt-baseline",
        "--write-baseline",
        str(collection_error_path),
        baseline_kind="after_main_style_isolation",
    )

    assert required_proc.returncode == 2
    assert pollution_proc.returncode == 2
    assert collection_error_proc.returncode == 2
    assert "required_or_quality_gate_self_failure" in required_proc.stderr
    assert "main_style_isolation_candidate" in pollution_proc.stderr
    assert "collection_error_count" in collection_error_proc.stderr
    assert _payload_from_stdout(required_proc)["importable"] is False
    assert _payload_from_stdout(pollution_proc)["importable"] is False
    assert _payload_from_stdout(collection_error_proc)["importable"] is False
    assert "required_or_quality_gate_self_failure" in _payload_from_stdout(required_proc)["importable_blockers"]
    assert "main_style_isolation_candidate" in _payload_from_stdout(pollution_proc)["importable_blockers"]
    assert "collection_error_count" in _payload_from_stdout(collection_error_proc)["importable_blockers"]
    assert not required_path.exists()
    assert not pollution_path.exists()
    assert not collection_error_path.exists()


def test_collect_full_test_debt_importable_rejects_bad_pytest_invocation(tmp_path: Path) -> None:
    baseline_path = tmp_path / "audit" / "debt_baseline.md"
    _write(tmp_path / "README.md", "clean repo")
    _write(baseline_path, "STALE IMPORTABLE BASELINE")
    _init_clean_git_repo(tmp_path)
    command = [
        sys.executable,
        str(COLLECTOR),
        "--baseline-kind",
        "after_main_style_isolation",
        "--importable-debt-baseline",
        "--write-baseline",
        str(baseline_path),
        "--",
        "tests/does_not_exist.py",
        "-q",
        "--tb=short",
        "-p",
        "no:cacheprovider",
    ]

    with _ORIGINAL_POPEN(
        command,
        cwd=str(tmp_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    ) as proc:
        stdout, stderr = proc.communicate()
    payload = dict(json.loads(stdout))

    assert proc.returncode == 2
    assert payload["exitstatus"] not in {0, 1}
    assert payload["importable"] is False
    assert "pytest_exitstatus" in payload["importable_blockers"]
    assert "pytest_exitstatus" in stderr
    assert not baseline_path.exists()


def _valid_test_debt_entry(nodeid: str = "tests/test_sample.py::test_debt") -> dict:
    return {
        "debt_id": "test-debt:sample",
        "nodeid": nodeid,
        "mode": "xfail",
        "reason": "旧测试合同尚未更新",
        "domain": "personnel.operator_machine",
        "style": "stale_patch_target",
        "root": {
            "module": "core.services.personnel.operator_machine_normalizers",
            "function": "normalize_skill_level_optional",
        },
        "owner": "personnel.operator_machine",
        "exit_condition": "该 nodeid 定向 pytest 普通通过，并从正式 full pytest 债务基线移除。",
        "last_verified_at": "2026-04-27T08:00:00+08:00",
        "debt_family": "operator_machine_normalization_contract_drift",
    }


def _ledger_with_test_debt(*entries: dict, max_registered_xfail: int = 1) -> dict:
    from tools.quality_gate_shared import LEDGER_IDENTITY_STRATEGY, LEDGER_SCHEMA_VERSION, STARTUP_SCOPE_PATTERNS

    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "identity_strategy": LEDGER_IDENTITY_STRATEGY,
        "updated_at": "2026-04-27T08:00:00+08:00",
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {"scope": list(STARTUP_SCOPE_PATTERNS), "entries": []},
        "test_debt": {
            "ratchet": {"max_registered_xfail": max_registered_xfail},
            "entries": list(entries),
        },
        "accepted_risks": [],
    }


def _run_pytest(project: Path, *args: str) -> subprocess.CompletedProcess:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *args,
        "-p",
        "no:cacheprovider",
    ]
    with _ORIGINAL_POPEN(
        command,
        cwd=str(project),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    ) as proc:
        stdout, stderr = proc.communicate()
    return subprocess.CompletedProcess(command, int(proc.returncode), stdout, stderr)


def _write_debt_aware_conftest(project: Path, entries_by_nodeid: dict) -> None:
    entries_json = json.dumps(entries_by_nodeid, ensure_ascii=False)
    _write(
        project / "conftest.py",
        f'''
        import importlib.util
        import json
        from pathlib import Path

        REPO_ROOT = Path({str(REPO_ROOT)!r})
        spec = importlib.util.spec_from_file_location(
            "_repo_tests_conftest_under_test",
            REPO_ROOT / "tests" / "conftest.py",
        )
        repo_conftest = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(repo_conftest)

        _ENTRIES_BY_NODEID = json.loads({entries_json!r})


        def _fake_active_xfail_entries_by_nodeid():
            return dict(_ENTRIES_BY_NODEID)


        repo_conftest.active_xfail_entries_by_nodeid = _fake_active_xfail_entries_by_nodeid
        pytest_collection_modifyitems = repo_conftest.pytest_collection_modifyitems
        ''',
    )


def _write_broken_debt_conftest(project: Path) -> None:
    _write(
        project / "conftest.py",
        f'''
        import importlib.util
        from pathlib import Path

        REPO_ROOT = Path({str(REPO_ROOT)!r})
        spec = importlib.util.spec_from_file_location(
            "_repo_tests_conftest_under_test",
            REPO_ROOT / "tests" / "conftest.py",
        )
        repo_conftest = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(repo_conftest)


        def _broken_active_xfail_entries_by_nodeid():
            raise RuntimeError("broken debt ledger")


        repo_conftest.active_xfail_entries_by_nodeid = _broken_active_xfail_entries_by_nodeid
        pytest_collection_modifyitems = repo_conftest.pytest_collection_modifyitems
        ''',
    )


def test_test_debt_registry_requires_nodeid_owner_root_and_exit_condition() -> None:
    from tools.quality_gate_ledger import validate_ledger
    from tools.quality_gate_shared import LEDGER_SCHEMA_VERSION, QualityGateError
    from tools.test_debt_registry import active_xfail_nodeids

    assert LEDGER_SCHEMA_VERSION == 2
    entry = _valid_test_debt_entry()
    validate_ledger(_ledger_with_test_debt(entry))
    assert active_xfail_nodeids(_ledger_with_test_debt(entry)) == {entry["nodeid"]}

    for field_name in [
        "debt_id",
        "nodeid",
        "mode",
        "reason",
        "domain",
        "style",
        "owner",
        "exit_condition",
        "last_verified_at",
        "debt_family",
    ]:
        broken = copy.deepcopy(entry)
        broken[field_name] = ""
        with pytest.raises(QualityGateError, match=field_name):
            validate_ledger(_ledger_with_test_debt(broken))

    broken_root = copy.deepcopy(entry)
    broken_root["root"] = {"module": "core.services.personnel.operator_machine_normalizers"}
    with pytest.raises(QualityGateError, match="root.function"):
        validate_ledger(_ledger_with_test_debt(broken_root))

    broken_untriaged = copy.deepcopy(entry)
    broken_untriaged["style"] = "untriaged"
    with pytest.raises(QualityGateError, match="untriaged"):
        validate_ledger(_ledger_with_test_debt(broken_untriaged))

    broken_mode = copy.deepcopy(entry)
    broken_mode["mode"] = "skip"
    with pytest.raises(QualityGateError, match="mode"):
        validate_ledger(_ledger_with_test_debt(broken_mode))


def test_test_debt_registry_rejects_duplicates_and_negative_ratchet() -> None:
    from tools.quality_gate_ledger import validate_ledger
    from tools.quality_gate_shared import QualityGateError

    first = _valid_test_debt_entry("tests/test_sample.py::test_one")
    second = _valid_test_debt_entry("tests/test_sample.py::test_two")
    second["debt_id"] = "test-debt:sample-two"

    duplicate_nodeid = copy.deepcopy(second)
    duplicate_nodeid["nodeid"] = first["nodeid"]
    with pytest.raises(QualityGateError, match="nodeid"):
        validate_ledger(_ledger_with_test_debt(first, duplicate_nodeid, max_registered_xfail=2))

    duplicate_debt_id = copy.deepcopy(second)
    duplicate_debt_id["debt_id"] = first["debt_id"]
    with pytest.raises(QualityGateError, match="debt_id"):
        validate_ledger(_ledger_with_test_debt(first, duplicate_debt_id, max_registered_xfail=2))

    with pytest.raises(QualityGateError, match="max_registered_xfail"):
        validate_ledger(_ledger_with_test_debt(first, max_registered_xfail=-1))

    fixed_entry = copy.deepcopy(first)
    fixed_entry["mode"] = "fixed"
    validate_ledger(_ledger_with_test_debt(fixed_entry, max_registered_xfail=0))


def test_sort_ledger_preserves_test_debt_and_active_xfail_reads_ledger() -> None:
    from tools.quality_gate_ledger import sort_ledger
    from tools.test_debt_registry import active_xfail_entries_by_nodeid, active_xfail_nodeids

    fixed = _valid_test_debt_entry("tests/test_sample.py::test_fixed")
    fixed["debt_id"] = "test-debt:sample-fixed"
    fixed["mode"] = "fixed"
    active = _valid_test_debt_entry("tests/test_sample.py::test_active")
    active["debt_id"] = "test-debt:sample-active"
    ledger = _ledger_with_test_debt(fixed, active, max_registered_xfail=1)

    sorted_ledger = sort_ledger(ledger)

    assert sorted_ledger["test_debt"]["ratchet"] == {"max_registered_xfail": 1}
    assert [entry["nodeid"] for entry in sorted_ledger["test_debt"]["entries"]] == [
        "tests/test_sample.py::test_active",
        "tests/test_sample.py::test_fixed",
    ]
    assert active_xfail_nodeids(sorted_ledger) == {"tests/test_sample.py::test_active"}
    assert active_xfail_entries_by_nodeid(sorted_ledger) == {"tests/test_sample.py::test_active": active}


def test_pytest_collection_marks_registered_exact_nodeids_xfail(tmp_path: Path) -> None:
    entries = {
        "test_debt_aware.py::test_plain_failure": _valid_test_debt_entry("test_debt_aware.py::test_plain_failure"),
        "test_debt_aware.py::test_param[bad]": _valid_test_debt_entry("test_debt_aware.py::test_param[bad]"),
        "test_debt_aware.py::test_fixture_param[dirty]": _valid_test_debt_entry(
            "test_debt_aware.py::test_fixture_param[dirty]"
        ),
    }
    _write_debt_aware_conftest(tmp_path, entries)
    _write(
        tmp_path / "test_debt_aware.py",
        '''
        import pytest


        def test_plain_failure():
            assert False


        @pytest.mark.parametrize("value", ["good", "bad"])
        def test_param(value):
            assert value == "good"


        @pytest.fixture(params=["clean", "dirty"])
        def sample(request):
            return request.param


        def test_fixture_param(sample):
            assert sample == "clean"
        ''',
    )

    proc = _run_pytest(tmp_path, "test_debt_aware.py", "-rx")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "2 passed" in proc.stdout
    assert "3 xfailed" in proc.stdout
    assert "test-debt:sample" in proc.stdout


def test_pytest_collection_keeps_unregistered_failures_failed(tmp_path: Path) -> None:
    _write_debt_aware_conftest(tmp_path, {})
    _write(
        tmp_path / "test_unregistered.py",
        '''
        def test_new_failure():
            assert False
        ''',
    )

    proc = _run_pytest(tmp_path, "test_unregistered.py")

    assert proc.returncode == 1
    assert "FAILED test_unregistered.py::test_new_failure" in proc.stdout


def test_pytest_collection_does_not_require_uncollected_registered_nodeids(tmp_path: Path) -> None:
    entries = {
        "test_not_collected.py::test_registered_failure": _valid_test_debt_entry(
            "test_not_collected.py::test_registered_failure"
        )
    }
    _write_debt_aware_conftest(tmp_path, entries)
    _write(
        tmp_path / "test_directed.py",
        '''
        def test_directed_passes():
            assert True
        ''',
    )

    proc = _run_pytest(tmp_path, "test_directed.py::test_directed_passes")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "1 passed" in proc.stdout
    assert "xfailed" not in proc.stdout


def test_pytest_collection_strict_xpass_fails_when_registered_debt_is_fixed(tmp_path: Path) -> None:
    entries = {
        "test_xpass.py::test_registered_now_passes": _valid_test_debt_entry(
            "test_xpass.py::test_registered_now_passes"
        )
    }
    _write_debt_aware_conftest(tmp_path, entries)
    _write(
        tmp_path / "test_xpass.py",
        '''
        def test_registered_now_passes():
            assert True
        ''',
    )

    proc = _run_pytest(tmp_path, "test_xpass.py", "-rxX")

    assert proc.returncode == 1
    assert "[XPASS(strict)]" in proc.stdout
    assert "test-debt:sample" in proc.stdout


def test_pytest_collection_propagates_debt_registry_failures(tmp_path: Path) -> None:
    _write_broken_debt_conftest(tmp_path)
    _write(
        tmp_path / "test_sample.py",
        '''
        def test_plain_pass():
            assert True
        ''',
    )

    proc = _run_pytest(tmp_path, "test_sample.py")

    assert proc.returncode != 0
    assert "broken debt ledger" in proc.stdout + proc.stderr


def test_save_ledger_writes_test_debt_snapshot_and_machine_block(monkeypatch) -> None:
    from tools import quality_gate_ledger

    entry = _valid_test_debt_entry()
    ledger = _ledger_with_test_debt(entry)
    writes = {}

    monkeypatch.setattr(quality_gate_ledger, "write_text_file", lambda path, text: writes.update({"path": path, "text": text}))

    quality_gate_ledger.save_ledger(ledger)

    assert writes["path"] == "开发文档/技术债务治理台账.md"
    assert "测试债务登记：1" in writes["text"]
    assert '"test_debt": {' in writes["text"]
    assert entry["nodeid"] in writes["text"]


def test_finalize_ledger_update_preserves_test_debt_and_stable_updated_at(monkeypatch) -> None:
    from tools import quality_gate_ledger

    entry = _valid_test_debt_entry()
    ledger = _ledger_with_test_debt(entry)
    monkeypatch.setattr(quality_gate_ledger, "load_ledger", lambda required=False: copy.deepcopy(ledger))

    finalized = quality_gate_ledger.finalize_ledger_update(copy.deepcopy(ledger))

    assert finalized["updated_at"] == ledger["updated_at"]
    assert finalized["test_debt"] == quality_gate_ledger.sort_ledger(ledger)["test_debt"]


def test_refresh_auto_fields_preserves_test_debt(monkeypatch) -> None:
    from tools import quality_gate_support

    entry = _valid_test_debt_entry()
    ledger = _ledger_with_test_debt(entry)
    refresh_globals = quality_gate_support.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    refreshed = quality_gate_support.refresh_auto_fields(copy.deepcopy(ledger))

    assert refreshed["test_debt"] == ledger["test_debt"]


def test_ordinary_sort_and_save_reject_missing_test_debt(monkeypatch) -> None:
    from tools import quality_gate_ledger
    from tools.quality_gate_shared import LEDGER_IDENTITY_STRATEGY, STARTUP_SCOPE_PATTERNS, QualityGateError

    legacy_shape = {
        "schema_version": 2,
        "identity_strategy": LEDGER_IDENTITY_STRATEGY,
        "updated_at": "2026-04-27T08:00:00+08:00",
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {"scope": list(STARTUP_SCOPE_PATTERNS), "entries": []},
        "accepted_risks": [],
    }
    monkeypatch.setattr(quality_gate_ledger, "write_text_file", lambda _path, _text: None)

    with pytest.raises(QualityGateError, match="test_debt"):
        quality_gate_ledger.sort_ledger(legacy_shape)
    with pytest.raises(QualityGateError, match="test_debt"):
        quality_gate_ledger.save_ledger(legacy_shape)
