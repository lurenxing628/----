from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_scheduler_graph_modules_do_not_import_networkx_during_module_import() -> None:
    code = r'''
import importlib
import json
import sys

sys.modules.pop("networkx", None)
modules = [
    "core.services.scheduler.graph",
    "core.services.scheduler.graph.nx_runtime",
    "core.services.scheduler.graph.types",
    "core.services.scheduler.graph.id_policy",
    "core.services.scheduler.graph.input_adapter",
    "core.services.scheduler.graph.precedence_builder",
    "core.services.scheduler.graph.validators",
    "core.services.scheduler.graph.metrics",
    "core.services.scheduler.graph.ready_queue",
    "core.services.scheduler.graph.scoring",
    "core.services.scheduler.graph.resource_matching",
    "core.services.scheduler.graph.exporter",
    "core.services.scheduler.graph.analysis_service",
]
for module_name in modules:
    importlib.import_module(module_name)
print(json.dumps({"networkx_loaded": "networkx" in sys.modules}, sort_keys=True))
'''
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout.splitlines()[-1])
    assert payload == {"networkx_loaded": False}
