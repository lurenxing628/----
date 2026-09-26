"""Host Chrome 109, current component source, memory records and native PDFs."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_candidate_paper_width_and_header_layering(tmp_path):
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / "candidate-print"
    result = subprocess.run(
        [node, str(Path(__file__).with_suffix(".cjs")), str(output)],
        cwd=str(root), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=120,
    )
    report = json.loads((output / "candidate-print-regressions.json").read_text(encoding="utf-8"))
    assert result.returncode == 0, result.stdout + result.stderr + report.get("failure", "")
    assert report["browser"].startswith("109.")
    assert report["win7_tested"] is False
    assert report["production_persistence_tested"] is False
    assert len(report["cases"]) == 4 and len(report["header"]) == 2
    for row in report["cases"]:
        assert row["after"] == row["before"]
        assert row["before"]["selected"] is not None
        assert hashlib.sha256(Path(row["filename"]).read_bytes()).hexdigest() == row["sha256"]
    for row in report["sources"]:
        assert hashlib.sha256((root / row["path"]).read_bytes()).hexdigest() == row["sha256"]
