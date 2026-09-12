"""Run current shipped Gantt modules in Node; inputs are JS assertions and DTOs.

The paired CJS harness uses shipped React.createElement, not an HTML serializer.
It observes actual component props and visible text children, not browser layout
pixels. Closed diagnostic details retain their nodes but contribute only their
summary to text(); styles() reads the shipped manifest-declared Gantt CSS.
"""

import json
import subprocess
from pathlib import Path

from tests._support.paths import REPO_ROOT

HARNESS = Path(__file__).with_name("gantt_current_runtime.cjs")


def run_current_js(program, data=None):
    """Execute one explicit assertion program against private shipped assets."""
    completed = subprocess.run(
        ["node", str(HARNESS)],
        input=json.dumps({"root": str(REPO_ROOT), "program": program, "data": data}),
        text=True, capture_output=True, check=False, cwd=str(REPO_ROOT), timeout=40,
    )
    if completed.returncode:
        raise AssertionError("Current Gantt Node contract failed:\n" + completed.stdout + completed.stderr)
    return json.loads(completed.stdout)
