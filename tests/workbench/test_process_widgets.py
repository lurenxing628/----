"""Current-source component compile and real Chromium 109, with mock adapters only."""

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


class ProcessWidgetsTest(unittest.TestCase):
    def test_read_preview_controls_without_commands(self):
        node, browser, modules = runtime_tools()
        output = Path(tempfile.mkdtemp(prefix="aps-process-widgets-"))
        result = subprocess.run(
            [node, str(HERE / "process_widgets_probe.cjs"), str(output)],
            cwd=str(HERE.parent.parent),
            env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
            capture_output=True, text=True, timeout=240,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr + "\n" + str(output))
        report = json.loads((output / "process-result.json").read_text(encoding="utf-8"))
        self.assertEqual(report["scope"], "process-read-preview-component-mock")
        self.assertFalse(report["production_persistence_tested"])
        self.assertFalse(report["compile"]["global_build"])
        self.assertEqual(report["compile"]["target"], {"chrome": "109"})
        self.assertTrue(report["browser"].startswith("109."))
        self.assertEqual(len(report["cases"]), 60)
        self.assertTrue(all(row["passed"] for row in report["cases"]))
        self.assertEqual(len(report["screenshots"]), 24)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["external"], [])
        self.assertEqual(len({row["variant"] for row in report["cases"]}), 4)
        for row in report["sources"] + report["probes"]:
            current = HERE.parent.parent / row["path"]
            self.assertEqual(hashlib.sha256(current.read_bytes()).hexdigest(), row["sha256"], row["path"])
        print("PROCESS_WIDGETS_ARTIFACTS " + str(output), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
