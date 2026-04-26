from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = REPO_ROOT / "tools" / "collect_full_test_debt.py"
BASELINE_BEGIN = "<!-- APS-FULL-PYTEST-BASELINE:BEGIN -->"
BASELINE_END = "<!-- APS-FULL-PYTEST-BASELINE:END -->"
_ORIGINAL_POPEN = subprocess.Popen


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


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


def _payload_from_stdout(proc: subprocess.CompletedProcess) -> dict:
    assert proc.stdout.strip().startswith("{")
    assert proc.stdout.strip().endswith("}")
    return dict(json.loads(proc.stdout))


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
    assert payload["schema_version"] == 1
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
    baseline_text = baseline_path.read_text(encoding="utf-8")
    block = baseline_text.split(BASELINE_BEGIN, 1)[1].split(BASELINE_END, 1)[0].strip()
    if block.startswith("```json"):
        block = block[len("```json") :].strip()
    if block.endswith("```"):
        block = block[: -len("```")].strip()
    baseline_payload = json.loads(block)

    assert payload["importable"] is False
    assert baseline_payload["baseline_kind"] == "raw_before_isolation"
    assert baseline_payload["importable"] is False
    assert payload["summary"] == baseline_payload["summary"]
    assert "tests/test_run_quality_gate.py::test_quality_gate_self_failure" in baseline_payload["classifications"][
        "required_or_quality_gate_self_failure"
    ]


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
