"""Find the build-host Node runtime without requiring a browser."""

import os
import shutil
from pathlib import Path


def node_runtime():
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node") or (str(bundled) if bundled.is_file() else None)
    if not node:
        raise RuntimeError("Set WORKBENCH_NODE to an installed Node runtime")
    return node
