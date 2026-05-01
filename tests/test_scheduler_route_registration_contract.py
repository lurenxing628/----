from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_probe(source: str, *args: str) -> dict[str, object]:
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

importlib.import_module("web.routes.scheduler_run")
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
