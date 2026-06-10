"""契约测试：scheduler 路由的注册时机与导入副作用——import web.routes.scheduler 不会注册整张路由图、显式 register_scheduler_routes 才一次性挂载且二次调用稳定、旧 leaf 模块只加载自身不拉起 registrar，以及真实 create_app 工厂确把 run/gantt/analysis/resource-dispatch 路由挂上 url_map。"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict

from tests._support.paths import REPO_ROOT


def _run_probe(source: str, *args: str) -> Dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-c", source, *args],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, (completed.stdout, completed.stderr)
    output_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    return json.loads(output_lines[-1])


# ===========================================================================
# 模块加载层契约（子进程探针隔离 import 副作用）
# 迁入自: tests/schedule/route_view/test_scheduler_route_registration_contract.py（原 A 文件，本目标文件原身）
# ===========================================================================


def test_import_scheduler_root_does_not_register_full_scheduler_graph() -> None:
    payload = _run_probe(
        """
import importlib
import json
import sys

importlib.import_module("web.routes.scheduler")
registrar = importlib.import_module("web.routes.domains.scheduler.scheduler_route_registrar")
print(json.dumps({
    "registered": bool(getattr(registrar, "_REGISTERED")),
    "loaded_analysis": "web.routes.domains.scheduler.scheduler_analysis" in sys.modules,
    "loaded_run": "web.routes.domains.scheduler.scheduler_run" in sys.modules,
}, sort_keys=True))
"""
    )

    assert payload["registered"] is False
    assert payload["loaded_analysis"] is False
    assert payload["loaded_run"] is False


def test_explicit_scheduler_registration_imports_route_graph_once() -> None:
    payload = _run_probe(
        """
import importlib
import json
import sys

scheduler_root = importlib.import_module("web.routes.scheduler")
scheduler_root.register_scheduler_routes()
registrar = importlib.import_module("web.routes.domains.scheduler.scheduler_route_registrar")
loaded_before = sorted(
    name for name in sys.modules
    if name.startswith("web.routes.domains.scheduler.scheduler_")
)
scheduler_root.register_scheduler_routes()
loaded_after = sorted(
    name for name in sys.modules
    if name.startswith("web.routes.domains.scheduler.scheduler_")
)
print(json.dumps({
    "registered": bool(getattr(registrar, "_REGISTERED")),
    "loaded_analysis": "web.routes.domains.scheduler.scheduler_analysis" in sys.modules,
    "loaded_run": "web.routes.domains.scheduler.scheduler_run" in sys.modules,
    "stable_after_second_register": loaded_after == loaded_before,
}, sort_keys=True))
"""
    )

    assert payload["registered"] is True
    assert payload["loaded_analysis"] is True
    assert payload["loaded_run"] is True
    assert payload["stable_after_second_register"] is True


def test_legacy_leaf_import_loads_only_requested_leaf() -> None:
    payload = _run_probe(
        """
import importlib
import json
import sys

importlib.import_module("web.routes.domains.scheduler.scheduler_run")
print(json.dumps({
    "loaded_root": "web.routes.scheduler" in sys.modules,
    "loaded_registrar": "web.routes.domains.scheduler.scheduler_route_registrar" in sys.modules,
    "loaded_analysis": "web.routes.domains.scheduler.scheduler_analysis" in sys.modules,
    "loaded_run": "web.routes.domains.scheduler.scheduler_run" in sys.modules,
}, sort_keys=True))
"""
    )

    assert payload["loaded_root"] is False
    assert payload["loaded_registrar"] is False
    assert payload["loaded_analysis"] is False
    assert payload["loaded_run"] is True


# ===========================================================================
# 应用工厂层契约（真实 create_app 后 scheduler 路由确已挂上 url_map）
# 迁入自: tests/test_scheduler_routes_still_registered_by_factory.py（原 B 文件，已 rm 删）
# 复用 conftest db_env fixture（五件套 env + ensure_schema 建库）替原 _load_app_factory 私有 helper；
# 保留 sys.modules.pop("app", None) + importlib.import_module("app").create_app()（需 app 对象取 url_map）。
# ===========================================================================


def test_scheduler_routes_are_registered_by_factory(db_env) -> None:
    sys.modules.pop("app", None)
    app = importlib.import_module("app").create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/scheduler/run" in rules
    assert "/scheduler/gantt" in rules
    assert "/scheduler/analysis" in rules
    assert "/scheduler/resource-dispatch" in rules
