"""Short-screen application layout (issue 2026-09-14-wbui-double-scroll-1366, plan B) on a real Flask + Chromium 109 loop.

Below --wb-short-screen-max (820px) the batch and part-process workspaces must keep the window from scrolling: only the
table frame scrolls, the capacity rail collapses to one row of chips, and tall screens keep the previous layout.
"""

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_live_browser import run_probe


class WorkbenchShortScreenLayoutTest(unittest.TestCase):
    def test_short_screens_scroll_only_the_table(self):
        root, result = run_probe("short_screen_layout_probe.cjs")
        self.assertNotIn("runner_error", result, result.get("runner_error", "") + "\nArtifacts: " + str(root))
        self.assertNotIn("forced_server_kill", result)
        self.assertEqual(result.get("probe_returncode"), 0, "Probe failed; see " + str(root / "probe-errors.log"))
        probe = result.get("probe")
        self.assertIsInstance(probe, dict, "Probe wrote no probe-results.json")
        self.assertEqual(probe["errors"], [])
        self.assertEqual(probe["external"], [])
        self.assertEqual(sorted(case["state"] for case in probe["cases"]),
                         sorted(view + "@" + size for size in ("1366x768", "1366x640", "1280x720", "1920x1080") for view in ("batches", "process")))


if __name__ == "__main__":
    unittest.main()
