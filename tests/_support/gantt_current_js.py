"""Run current shipped Gantt modules in Node; inputs are JS assertions and DTOs.

The paired CJS harness uses shipped React.createElement, not an HTML serializer.
It observes actual component props and visible text children, not browser layout
pixels. Closed diagnostic details retain their nodes but contribute only their
summary to text(); styles() reads the shipped manifest-declared Gantt CSS.
h.render() is one first paint without effects; h.mount() keeps hook state per
component instance (tests/_support/hook_host.cjs) and settle() commits effects and
awaits answers; h.serve() replaces only the network answers. Programs may await.
"""

import json
from pathlib import Path

from tests._support.node_runtime_support import run_node
from tests._support.paths import REPO_ROOT

HARNESS = Path(__file__).with_name("gantt_current_runtime.cjs")


def run_current_js(program, data=None):
    """Execute one explicit assertion program against private shipped assets."""
    completed = run_node(
        [HARNESS],
        input=json.dumps({"root": str(REPO_ROOT), "program": program, "data": data}),
        cwd=REPO_ROOT,
        timeout=40,
        label="Current Gantt Node contract",
    )
    return json.loads(completed.stdout)
