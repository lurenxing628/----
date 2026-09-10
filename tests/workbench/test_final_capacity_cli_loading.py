"""The optional capacity CLI loads its managed executor only after valid arguments."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts/workbench/verify_final_capacity.py"


@pytest.mark.parametrize("arguments,code", [(["--help"], 0), (["--output", "unused", "--batches", "0"], 2)])
def test_help_and_invalid_arguments_do_not_import_test_executor(arguments, code):
    probe = """
import json, runpy, sys
sys.argv = [sys.argv[1]] + json.loads(sys.argv[2])
path = sys.argv[0]
try:
    runpy.run_path(path, run_name='__main__')
except SystemExit as exc:
    code = exc.code
else:
    raise AssertionError('CLI did not exit')
assert 'tests.workbench.final_capacity_probe' not in sys.modules
assert 'web.bootstrap.factory' not in sys.modules
print('CLI_LOADING_RESULT ' + json.dumps({'code': code}))
"""
    result = subprocess.run([sys.executable, "-B", "-c", probe, str(CLI), json.dumps(arguments)],
                            cwd=str(ROOT), text=True, capture_output=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    line = next(value for value in result.stdout.splitlines() if value.startswith("CLI_LOADING_RESULT "))
    assert json.loads(line.split(" ", 1)[1]) == {"code": code}


def test_valid_cli_delegates_exact_arguments_without_changing_thresholds(tmp_path):
    probe = """
import json, runpy, sys, types
from pathlib import Path
path, output, assets = sys.argv[1:]
calls = []
executor = types.ModuleType('tests.workbench.final_capacity_probe')
def run_managed(destination, **kwargs):
    calls.append({'output': str(destination), **{key: str(value) if isinstance(value, Path) else value for key, value in kwargs.items()}})
    return {'root': str(destination), 'complete': True, 'formal_capacity_passed': False}
executor.run_managed = run_managed
sys.modules['tests.workbench.final_capacity_probe'] = executor
sys.argv = [path, '--output', output, '--batches', '2', '--operations', '3', '--asset-root', assets]
try:
    runpy.run_path(path, run_name='__main__')
except SystemExit as exc:
    assert exc.code == 0
else:
    raise AssertionError('CLI did not exit')
print('CLI_DELEGATION_RESULT ' + json.dumps(calls))
"""
    output, assets = tmp_path / "output", tmp_path / "assets"
    result = subprocess.run([sys.executable, "-B", "-c", probe, str(CLI), str(output), str(assets)],
                            cwd=str(ROOT), text=True, capture_output=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    line = next(value for value in result.stdout.splitlines() if value.startswith("CLI_DELEGATION_RESULT "))
    assert json.loads(line.split(" ", 1)[1]) == [{"output": str(output), "batches": 2, "operations": 3,
        "exclusive_window": None, "profile": False, "asset_root": str(assets)}]
    assert not output.exists()
