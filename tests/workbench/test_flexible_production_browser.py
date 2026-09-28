"""Actual Chrome109 maintenance flows using the existing isolated resource host."""

import os
import unittest

from tests.workbench.test_cross_module_maintenance_browser import run_probe


@unittest.skipUnless(os.environ.get("FLEXIBLE_PRODUCTION_RUN_BROWSER") == "1", "Opt-in Chrome109 flexible production")
class FlexibleProductionBrowserTest(unittest.TestCase):
    def test_real_calendar_controls_and_default_persistence(self):
        root, result = run_probe("flexible_production_probe.cjs", "flexible-production-browser.json", "flexible_production_server.py")
        self.assertNotIn("runner_error", result, str(root))
        self.assertEqual(result["probe_returncode"], 0, str(root / "flexible-production-browser.json"))
        self.assertEqual(result["server_returncode"], 0, str(root))
        self.assertTrue(result["isolation"]["stopped"])
        self.assertEqual(result["isolation"]["isolation_violations"], [])
        self.assertEqual(result["probe"]["failed"], 0)
        print("FLEXIBLE_PRODUCTION_VERIFIED " + str(root), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
