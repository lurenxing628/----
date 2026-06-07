"""回归测试：core.services.scheduler.graph 全部子模块（nx_runtime/types/id_policy/input_adapter/precedence_builder/validators/metrics/ready_queue/scoring/resource_matching/exporter/analysis_service）在被 import 时都不得加载 networkx——在剔除 networkx 的子进程里逐个导入后，sys.modules 中仍不应出现 networkx，保证其为惰性运行时依赖。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests._support.paths import REPO_ROOT


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
