"""EL delta-only remark regression; no frontend build or product database writes."""

import json
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_el_material_draft_delta_and_clear_contracts():
    node, _, _ = runtime_tools()
    result = subprocess.run([node, str(Path(__file__).with_name("el_material_contracts.cjs"))],
                            text=True, capture_output=True, check=True)
    report = json.loads(result.stdout)
    assert report == {"checks": 22, "passed": True}


def test_el_material_snapshot_bound_paging_and_explicit_failures():
    node, _, _ = runtime_tools()
    result = subprocess.run([node, str(Path(__file__).with_name("el_material_paging.cjs"))],
                            text=True, capture_output=True, check=True)
    report = json.loads(result.stdout)
    assert report == {"checks": 21, "passed": True, "scope": "extracted-private-reader-unit-not-browser"}
