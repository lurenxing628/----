"""Current-source navigation in Chromium 109; mock adapters, no product build/DB."""

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


class ResourceNavigationContextTest(unittest.TestCase):
    def test_exact_context_pending_and_key_remount(self):
        node, browser, modules = runtime_tools()
        output = Path(tempfile.mkdtemp(prefix="aps-resource-navigation-z-"))
        print("RESOURCE_NAVIGATION_ARTIFACTS " + str(output), flush=True)
        run = subprocess.run(
            [node, str(HERE / "resource_navigation_context_probe.cjs"), str(output)],
            cwd=str(HERE.parent.parent),
            env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
            capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr + "\n" + str(output))
        report = json.loads((output / "navigation-result.json").read_text(encoding="utf-8"))
        self.assertEqual(report["scope"], "resource-navigation-current-source-component-mock")
        self.assertEqual(report["compile"]["target"], {"chrome": "109"})
        self.assertFalse(report["compile"]["global_build"])
        self.assertFalse(report["production_persistence_tested"])
        self.assertTrue(report["browser"].startswith("109."))
        self.assertGreaterEqual(len(report["cases"]), 72)
        self.assertTrue(all(row["passed"] for row in report["cases"]))
        self.assertEqual(len({row["variant"] for row in report["cases"]}), 4)
        self.assertGreaterEqual(len(report["screenshots"]), 16)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["external"], [])
        for row in report["sources"]:
            self.assertEqual(hashlib.sha256((HERE.parent.parent / row["path"]).read_bytes()).hexdigest(), row["sha256"], row["path"])
        print(run.stdout, flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
