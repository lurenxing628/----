from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

LEGACY_SCHEDULER_WRAPPERS = (
    "web.routes.scheduler_analysis",
    "web.routes.scheduler_batch_detail",
    "web.routes.scheduler_batches",
    "web.routes.scheduler_config",
    "web.routes.scheduler_excel_batches",
    "web.routes.scheduler_excel_calendar",
    "web.routes.scheduler_ops",
    "web.routes.scheduler_run",
    "web.routes.scheduler_week_plan",
)


@pytest.mark.parametrize("module_name", LEGACY_SCHEDULER_WRAPPERS)
def test_legacy_scheduler_wrapper_import_stays_passive_before_app_import(module_name: str) -> None:
    probe = """
import importlib
import json
import sys

target = sys.argv[1]
scheduler_root = importlib.import_module("web.routes.scheduler")
calls = []
original_register = scheduler_root.register_scheduler_routes

def _wrapped_register():
    calls.append("called")
    return original_register()

scheduler_root.register_scheduler_routes = _wrapped_register
route_mod = importlib.import_module(target)
calls_after_wrapper = len(calls)
app_mod = importlib.import_module("app")
created = app_mod.create_app()
print(json.dumps({
    "module": route_mod.__name__,
    "register_calls_after_app": len(calls),
    "register_calls_after_wrapper": calls_after_wrapper,
    "registered_blueprints": sorted(created.blueprints),
}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", probe, module_name],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, (module_name, completed.stdout, completed.stderr)
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    if module_name == "web.routes.scheduler_excel_batches":
        assert payload["module"] == module_name
    else:
        assert payload["module"].startswith("web.routes.domains.scheduler.scheduler_")
    assert payload["register_calls_after_wrapper"] == 0
    assert payload["register_calls_after_app"] >= 1
    assert "scheduler" in payload["registered_blueprints"]


def test_scheduler_root_bp_direct_registration_requires_explicit_route_registration() -> None:
    probe = """
import importlib
import json
from flask import Flask

scheduler_root = importlib.import_module("web.routes.scheduler")
app = Flask(__name__)
scheduler_root.register_scheduler_routes()
app.register_blueprint(scheduler_root.bp, url_prefix="/scheduler")
routes_before_wrapper = sorted(str(rule) for rule in app.url_map.iter_rules() if str(rule).startswith("/scheduler"))
importlib.import_module("web.routes.scheduler_run")
routes_after_wrapper = sorted(str(rule) for rule in app.url_map.iter_rules() if str(rule).startswith("/scheduler"))
scheduler_root.register_scheduler_routes()
routes_after_second_register = sorted(str(rule) for rule in app.url_map.iter_rules() if str(rule).startswith("/scheduler"))
print(json.dumps({
    "route_count": len(routes_before_wrapper),
    "has_root": "/scheduler/" in routes_before_wrapper,
    "has_run": "/scheduler/run" in routes_before_wrapper,
    "has_config": "/scheduler/config" in routes_before_wrapper,
    "stable_after_wrapper": routes_after_wrapper == routes_before_wrapper,
    "stable_after_second_register": routes_after_second_register == routes_before_wrapper,
}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, (completed.stdout, completed.stderr)
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert payload["route_count"] >= 40
    assert payload["has_root"] is True
    assert payload["has_run"] is True
    assert payload["has_config"] is True
    assert payload["stable_after_wrapper"] is True
    assert payload["stable_after_second_register"] is True
