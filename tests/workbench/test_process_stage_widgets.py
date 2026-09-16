"""Current sources and Chromium 109. Adapters are mocks, not persistence evidence."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_live_browser import runtime_tools


class ProcessStageWidgetsTest(unittest.TestCase):
    def test_stage_controls_receipts_and_drafts(self):
        node, browser, modules = runtime_tools()
        output = Path(tempfile.mkdtemp(prefix="aps-process-stage-widgets-"))
        result = subprocess.run(
            [node, str(HERE / "process_stage_widgets_probe.cjs"), str(output)],
            cwd=str(HERE.parent.parent),
            env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
            capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr + "\n" + str(output))
        report = json.loads((output / "process-stage-result.json").read_text(encoding="utf-8"))
        self.assertEqual(report["scope"], "process-stage-component-mock")
        self.assertFalse(report["production_persistence_tested"])
        self.assertFalse(report["compile"]["global_build"])
        self.assertEqual(report["compile"]["target"], {"chrome": "109"})
        self.assertTrue(report["browser"].startswith("109."))
        self.assertTrue(all(row["passed"] for row in report["cases"]))
        self.assertEqual(len(report["cases"]), 92)
        self.assertEqual(len({row["variant"] for row in report["cases"]}), 4)
        self.assertEqual(len(report["screenshots"]), 24)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["external"], [])
        for row in report["sources"]:
            self.assertEqual(hashlib.sha256((HERE.parent.parent / row["path"]).read_bytes()).hexdigest(), row["sha256"], row["path"])
        print("PROCESS_STAGE_WIDGETS_ARTIFACTS " + str(output), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
