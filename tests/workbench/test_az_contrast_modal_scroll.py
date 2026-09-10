"""AZ Chrome109 contrast and ordinary-wheel regressions; memory-only adapters, no build/DB."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


@unittest.skipUnless(os.environ.get("AZ_RUN_BROWSER") == "1", "Opt-in AZ current-source Chrome109 tests")
class AZContrastModalScrollTest(unittest.TestCase):
    def run_probe(self, kind, count):
        node, browser, modules = runtime_tools()
        root = Path(__file__).resolve().parents[2]
        output = Path(tempfile.mkdtemp(prefix="aps-az-" + kind + "-"))
        result = subprocess.run(
            [node, str(root / ("tests/workbench/az_" + kind + "_probe.cjs")), str(output)],
            cwd=str(root), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
            capture_output=True, text=True, timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr + "\n" + str(output))
        report = json.loads((output / (kind + "-result.json")).read_text(encoding="utf-8"))
        self.assertTrue(report["browser"].startswith("109."))
        self.assertEqual(report["compile"]["target"], {"chrome": "109"})
        self.assertFalse(report["compile"]["global_build"])
        self.assertFalse(report["production_persistence_tested"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["external"], [])
        self.assertEqual(len(report["cases"]), count)
        self.assertTrue(all(row["passed"] for row in report["cases"]))
        if kind == "contrast":
            for row in report["cases"]:
                self.assertEqual(len(row["secondaryCopy"]), 4)
                self.assertTrue(all(sample["ratio"] >= 4.5 for sample in row["secondaryCopy"]))
        self.assertTrue(report["stopped"])
        self.assertTrue(report["screenshots"])
        # Shared collaborators may move after freezing; report drift instead of testing different bytes.
        owned = {"WorkbenchControlStyles.jsx", "BatchControls.jsx", "BatchFiles.jsx"}
        self.assertEqual([row for row in report["source_drift"] if Path(row["path"]).name in owned], [])
        print("AZ_BROWSER_ARTIFACTS " + str(output), flush=True)

    def test_control_contrast(self):
        self.run_probe("contrast", 4)

    def test_batch_modal_scroll(self):
        self.run_probe("modal_scroll", 12)


if __name__ == "__main__":
    unittest.main()
