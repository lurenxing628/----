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
    "web.routes.scheduler_excel_calendar",
    "web.routes.scheduler_ops",
    "web.routes.scheduler_run",
    "web.routes.scheduler_week_plan",
)


@pytest.mark.parametrize("module_name", LEGACY_SCHEDULER_WRAPPERS)
def test_legacy_scheduler_wrapper_remains_safe_when_registered_before_app_import(module_name: str) -> None:
    probe = """
import importlib
import json
import sys
from flask import Flask

target = sys.argv[1]
route_mod = importlib.import_module(target)
app = Flask(__name__)
app.register_blueprint(route_mod.bp, url_prefix="/scheduler")
app_mod = importlib.import_module("app")
created = app_mod.create_app()
print(json.dumps({
    "module": route_mod.__name__,
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
    assert payload["module"].startswith("web.routes.domains.scheduler.scheduler_")
    assert "scheduler" in payload["registered_blueprints"]
