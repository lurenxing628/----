from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent


def _expose_followup_tests(filename: str) -> None:
    path = _TESTS_DIR / filename
    spec = importlib.util.spec_from_file_location(f"_scheduler_followup_bridge_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法为 {filename} 构建测试桥接模块")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in vars(module).items():
        if inspect.isfunction(value) and name.startswith("test_"):
            globals()[f"test_{path.stem}__{name[5:]}"] = value
        if inspect.isfunction(value) and getattr(value, "_pytestfixturefunction", None) is not None:
            globals()[name] = value


for _filename in (
    "regression_config_field_spec_contract.py",
    "regression_scheduler_analysis_route_contract.py",
    "regression_sp05_followup_contracts.py",
):
    _expose_followup_tests(_filename)
