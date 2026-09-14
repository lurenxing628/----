"""经办人记忆合同：正式采用 / 试排采用表单只预填本机上次填写的合法经办人，坏值或存储不可用时说明原因。"""

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_handler_memory_prefills_only_valid_local_value():
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node") or (str(bundled) if bundled.is_file() else None)
    assert node, "Node is required for pure UI contracts; browser tooling is not needed"
    result = subprocess.run([node, str(ROOT / "tests/workbench/handler_memory_probe.cjs")], cwd=str(ROOT),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
