from __future__ import annotations

import pytest

from tools.long_gate_fingerprint import _resolve_node_executable


def resolve_node_binary(environment=None) -> str:
    resolved, _ = _resolve_node_executable(environment)
    return resolved or ""


def node_runtime() -> str:
    node_bin = resolve_node_binary()
    if not node_bin:
        pytest.fail(
            "Node.js runtime is required for Workbench frontend behavioral tests; "
            "install node or set WORKBENCH_NODE=/path/to/node"
        )
    return node_bin
