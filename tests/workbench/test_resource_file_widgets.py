"""Chromium 109 component mocks; does not claim Flask or database integration."""

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


class ResourceFileWidgetsTest(unittest.TestCase):
    def test_resource_file_components(self):
        node, browser, modules = runtime_tools()
        output = Path(tempfile.mkdtemp(prefix="aps-resource-file-widgets-"))
        env = dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser)
        print("RESOURCE_FILE_COMPONENT_ARTIFACTS " + str(output), flush=True)
        result = subprocess.run([node, str(HERE / "resource_file_widgets_probe.cjs"), str(output)],
                                cwd=str(HERE.parent.parent), env=env, capture_output=True,
                                text=True, timeout=900)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr + "\n" + str(output))
        report = json.loads((output / "resource-file-result.json").read_text(encoding="utf-8"))
        self.assertEqual(report["data_source"], "mock")
        self.assertFalse(report["production_persistence_tested"])
        self.assertTrue(report["browser"].startswith("109."))
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["external"], [])
        self.assertGreaterEqual(len(report["cases"]), 200)
        self.assertTrue(all(row["passed"] for row in report["cases"]))
        self.assertEqual(len({row["variant"] for row in report["cases"]}), 4)
        print(result.stdout, flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
