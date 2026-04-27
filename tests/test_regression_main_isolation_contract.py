from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_CONFTEST = REPO_ROOT / "tests" / "conftest.py"
RUNNER = REPO_ROOT / "tests" / "main_style_regression_runner.py"
_ORIGINAL_POPEN = subprocess.Popen


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def _write_bridge_conftest(project: Path) -> None:
    _write(
        project / "tests" / "conftest.py",
        f"""
        from __future__ import annotations

        import importlib.util
        import sys
        from pathlib import Path

        real_conftest = Path({str(REAL_CONFTEST)!r})
        spec = importlib.util.spec_from_file_location("_aps_real_tests_conftest", real_conftest)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load real conftest: {{real_conftest}}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        pytest_collect_file = module.pytest_collect_file
        """,
    )


def _run_pytest(project: Path, *args: str, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env_overrides:
        env.update(env_overrides)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *args,
        "--tb=short",
        "-p",
        "no:cacheprovider",
    ]
    with _ORIGINAL_POPEN(
        command,
        cwd=str(project),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    ) as proc:
        stdout, stderr = proc.communicate()
    return subprocess.CompletedProcess(command, int(proc.returncode), stdout, stderr)


def test_main_style_nodeid_and_runner_file_are_not_collected(tmp_path: Path) -> None:
    _write_bridge_conftest(tmp_path)
    _write(
        tmp_path / "tests" / "regression_nodeid_contract.py",
        """
        def main():
            return 0
        """,
    )

    proc = _run_pytest(tmp_path, "--collect-only", "tests")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "tests/regression_nodeid_contract.py::regression_nodeid_contract" in proc.stdout
    assert "tests/main_style_regression_runner.py" not in proc.stdout


def test_main_style_exit_contract_and_failure_output(tmp_path: Path) -> None:
    _write_bridge_conftest(tmp_path)
    _write(
        tmp_path / "tests" / "regression_exit_contract.py",
        f"""
        import os
        import sys

        def main():
            mode = os.environ["REGRESSION_MODE"]
            if mode == "return_zero":
                return 0
            if mode == "return_none":
                return None
            if mode == "return_bool_true":
                return True
            if mode == "return_two":
                print("RETURN_TWO_STDOUT")
                print("RETURN_TWO_STDERR", file=sys.stderr)
                return 2
            if mode == "system_exit_zero":
                raise SystemExit(0)
            if mode == "system_exit_two":
                print("SYSTEM_EXIT_STDOUT")
                print("SYSTEM_EXIT_STDERR", file=sys.stderr)
                raise SystemExit(2)
            if mode == "cwd_and_import":
                if os.getcwd() != {str(REPO_ROOT)!r}:
                    raise RuntimeError(f"cwd mismatch: {{os.getcwd()}}")
                import core

                assert core is not None
                return 0
            raise AssertionError(mode)
        """,
    )

    success_modes = [
        "return_zero",
        "return_none",
        "return_bool_true",
        "system_exit_zero",
        "cwd_and_import",
    ]
    for mode in success_modes:
        proc = _run_pytest(tmp_path, "tests/regression_exit_contract.py", env_overrides={"REGRESSION_MODE": mode})
        assert proc.returncode == 0, proc.stdout + proc.stderr

    return_two = _run_pytest(
        tmp_path,
        "tests/regression_exit_contract.py",
        env_overrides={"REGRESSION_MODE": "return_two"},
    )
    assert return_two.returncode == 1
    combined = return_two.stdout + return_two.stderr
    assert "returncode=2" in combined
    assert "RETURN_TWO_STDOUT" in combined
    assert "RETURN_TWO_STDERR" in combined
    assert "regression_exit_contract.py" in combined

    system_exit_two = _run_pytest(
        tmp_path,
        "tests/regression_exit_contract.py",
        env_overrides={"REGRESSION_MODE": "system_exit_two"},
    )
    assert system_exit_two.returncode == 1
    combined = system_exit_two.stdout + system_exit_two.stderr
    assert "returncode=2" in combined
    assert "SYSTEM_EXIT_STDOUT" in combined
    assert "SYSTEM_EXIT_STDERR" in combined


def test_main_style_subprocess_pollution_is_isolated(tmp_path: Path) -> None:
    _write_bridge_conftest(tmp_path)
    _write(
        tmp_path / "tests" / "regression_pollutes_popen.py",
        """
        import subprocess

        class _DummyProc:
            pass

        def _fake_popen(*args, **kwargs):
            return _DummyProc()

        def main():
            subprocess.Popen = _fake_popen
            return 0
        """,
    )
    _write(
        tmp_path / "tests" / "test_after_pollution.py",
        """
        import subprocess
        import sys

        def test_popen_context_manager_still_works():
            with subprocess.Popen(
                [sys.executable, "-c", "print('clean-popen')"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            ) as proc:
                stdout, stderr = proc.communicate()
            assert proc.returncode == 0, stderr
            assert stdout.strip() == "clean-popen"
        """,
    )

    proc = _run_pytest(tmp_path, "tests/regression_pollutes_popen.py", "tests/test_after_pollution.py")

    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_regression_file_read_failure_breaks_collection(tmp_path: Path) -> None:
    _write_bridge_conftest(tmp_path)
    bad_file = tmp_path / "tests" / "regression_bad_encoding.py"
    bad_file.write_bytes(b"\xff\xfe\x00")

    proc = _run_pytest(tmp_path, "--collect-only", "tests")

    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "regression_bad_encoding.py" in combined
    assert "UnicodeDecodeError" in combined or "codec" in combined


def test_runner_script_exists_and_is_not_main_style_collected() -> None:
    assert RUNNER.exists()

    proc = _run_pytest(REPO_ROOT, "--collect-only", "tests")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "tests/main_style_regression_runner.py::" not in proc.stdout
