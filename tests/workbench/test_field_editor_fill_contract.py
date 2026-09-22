"""Field editor quantity shortcuts fill the draft only; the save button is the single write path."""

import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_field_editor_quantity_shortcuts_do_not_write():
    node, _, _ = runtime_tools()
    result = subprocess.run([node, str(Path(__file__).with_name("field_editor_fill_contract.cjs"))],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
