from __future__ import annotations

import os
import subprocess
from typing import Mapping, Optional, Sequence, Union

import pytest

from scripts.workbench.node_runtime import (
    NodeNotFoundError,
    execute_selected_node,
    format_node_failure,
)
from tools.long_gate_fingerprint import resolve_cached_node_runtime

MISSING_NODE_MESSAGE = (
    "Node.js runtime is required for Workbench frontend behavioral tests; "
    "install node or set WORKBENCH_NODE=/path/to/node"
)


def run_node(
    args: Sequence[Union[str, os.PathLike]],
    *,
    input: Optional[str] = None,
    cwd: Optional[Union[str, os.PathLike]] = None,
    env: Optional[Mapping[str, str]] = None,
    timeout: float = 30,
    label: str = "Node",
) -> subprocess.CompletedProcess:
    try:
        runtime = resolve_cached_node_runtime(env)
    except NodeNotFoundError as exc:
        pytest.fail(f"{MISSING_NODE_MESSAGE} ({exc})")
    completed = execute_selected_node(
        runtime,
        args,
        input_text=input,
        cwd=cwd,
        env=env,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise AssertionError(
            format_node_failure(completed.returncode, completed.stdout, completed.stderr, label)
        )
    return completed
