"""Opt-in Chromium 109 component regression; never builds static or opens a DB."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


@unittest.skipUnless(os.environ.get("AY_RUN_MODAL_FOCUS") == "1", "Set AY_RUN_MODAL_FOCUS=1 for the isolated Chrome 109 harness")
class ModalFocusBrowserTest(unittest.TestCase):
    def test_nested_resource_modal_focus_contract(self):
        bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node"
        node = os.environ.get("WORKBENCH_NODE", str(bundled / "bin/node"))
        browser = os.environ.get("WORKBENCH_BROWSER", "/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium")
        self.assertTrue(Path(node).is_file(), "Set WORKBENCH_NODE to installed Node")
        self.assertTrue(Path(browser).is_file(), "Set WORKBENCH_BROWSER to actual Chromium 109")
        output = Path(tempfile.mkdtemp(prefix="aps-modal-focus-"))
        env = dict(os.environ, WORKBENCH_BROWSER=browser)
        env["NODE_PATH"] = os.pathsep.join(filter(None, [env.get("NODE_PATH"), str(bundled / "node_modules")]))
        for name in ("AY_SMOKE", "AY_BASELINE", "AY_UNSUSPENDED"):
            env.pop(name, None)
        print("AY_MODAL_FOCUS_ARTIFACTS " + str(output), flush=True)
        completed = subprocess.run([node, str(HERE / "modal_focus_probe.cjs"), str(output)],
                                   cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=300)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr + "\n" + str(output))
        result = json.loads((output / "modal-focus-result.json").read_text(encoding="utf-8"))
        self.assertTrue(result["passed"])
        self.assertFalse(result["global_build"])
        self.assertFalse(result["database_access"])
        self.assertTrue(result["browser"].startswith("109."))
        self.assertTrue(result["react_version"].startswith("18."))
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["external"], [])
        self.assertEqual({row["variant"] for row in result["cases"]}, {"1920-light", "1920-dark", "1392-light", "1392-dark"})
        self.assertGreaterEqual(len(result["cases"]), 64)
        self.assertTrue(all(row["passed"] for row in result["cases"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
