"""Current-source Chrome109 component mocks; no build or database writes."""

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


class ProcessDetailFilesTest(unittest.TestCase):
    def test_file_entry_draft_and_receipt_recovery(self):
        node, browser, modules = runtime_tools()
        output = Path(tempfile.mkdtemp(prefix="aps-process-detail-files-"))
        run = subprocess.run(
            [node, str(HERE / "process_detail_files_probe.cjs"), str(output)],
            cwd=str(HERE.parent.parent),
            env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
            capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr + "\n" + str(output))
        report = json.loads((output / "process-detail-files-result.json").read_text(encoding="utf-8"))
        self.assertEqual(report["scope"], "process-detail-files-component-mock")
        self.assertFalse(report["production_persistence_tested"])
        self.assertFalse(report["compile"]["global_build"])
        self.assertEqual(report["compile"]["target"], {"chrome": "109"})
        self.assertTrue(report["browser"].startswith("109."))
        self.assertEqual(len(report["cases"]), 52)
        self.assertTrue(all(row["passed"] for row in report["cases"]))
        self.assertEqual(len({row["variant"] for row in report["cases"]}), 4)
        self.assertEqual(len(report["screenshots"]), 28)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["external"], [])
        for row in report["sources"]:
            self.assertEqual(hashlib.sha256((HERE.parent.parent / row["path"]).read_bytes()).hexdigest(), row["sha256"], row["path"])
        print("PROCESS_DETAIL_FILES_ARTIFACTS " + str(output), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
