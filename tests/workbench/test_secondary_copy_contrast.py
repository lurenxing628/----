"""Scoped light ink contract, Chrome109 component transitions and isolated real pages."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from collections import Counter
from pathlib import Path

from tests.workbench.live_environment import REPO, create_root, environment, write_json
from tests.workbench.secondary_copy_assets import PATCH, SOURCE
from tests.workbench.test_live_browser import runtime_tools


def run_live():
    node, browser, modules = runtime_tools()
    root = create_root()
    env = environment(root)
    env.update(WORKBENCH_NODE=node, WORKBENCH_BROWSER=browser, NODE_PATH=modules)
    result = {"root": str(root)}
    print("SECONDARY_COPY_LIVE_ARTIFACTS " + str(root), flush=True)
    server = None
    with (root / "secondary-copy-server.log").open("w") as log:
        try:
            server = subprocess.Popen([sys.executable, "-B", str(REPO / "tests/workbench/secondary_copy_server.py"), "--root", str(root)],
                                      cwd=str(root), env=env, stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 120
            ready = root / "server-ready.json"
            while not ready.exists():
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError((root / "secondary-copy-server.log").read_text()[-5000:])
                time.sleep(.05)
            with (root / "secondary-copy-probe.log").open("w") as output:
                probe = subprocess.run([node, str(REPO / "tests/workbench/secondary_copy_live_probe.cjs"), str(ready)],
                                       cwd=str(root), env=env, stdout=output, stderr=subprocess.STDOUT, timeout=300)
            result["probe_returncode"] = probe.returncode
        except Exception as error:
            result["runner_error"] = str(error)
        finally:
            if server is not None:
                if server.poll() is None:
                    server.terminate()
                    try:
                        server.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=10)
                        result["forced_kill"] = True
                result["server_returncode"] = server.returncode
            for name, key in (("server-final.json", "isolation"), ("secondary-copy-live.json", "probe")):
                if (root / name).is_file():
                    result[key] = json.loads((root / name).read_text())
            write_json(root / "secondary-copy-result.json", result)
    return root, result


class SecondaryCopySourceTest(unittest.TestCase):
    def test_single_semantic_light_rule(self):
        source = (REPO / SOURCE).read_text(encoding="utf-8")
        self.assertEqual(source.count(PATCH), 1)
        self.assertEqual(source.count("--ui-muted:"), 1)
        self.assertIn("<window.WorkbenchControlStyles />", (REPO / "frontend/workbench/app/main.jsx").read_text())


@unittest.skipUnless(os.environ.get("SECONDARY_COPY_RUN_BROWSER") == "1", "Opt-in isolated Chromium109 tests")
class SecondaryCopyBrowserTest(unittest.TestCase):
    def test_component_transitions_and_scope(self):
        node, browser, modules = runtime_tools()
        output = Path(tempfile.mkdtemp(prefix="aps-secondary-copy-components-"))
        print("SECONDARY_COPY_COMPONENT_ARTIFACTS " + str(output), flush=True)
        result = subprocess.run([node, str(REPO / "tests/workbench/secondary_copy_component_probe.cjs"), str(output)],
                                cwd=str(REPO), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                                capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr + "\n" + str(output))
        report = json.loads((output / "secondary_copy-result.json").read_text())
        self.assertEqual(len(report["cases"]), 4)
        self.assertTrue(all(row["passed"] and len(row["states"]) == 6 for row in report["cases"]))
        self.assertEqual(report["source_drift"], [])
        self.assertTrue(report["stopped"])

    def test_real_readonly_pages(self):
        root, result = run_live()
        self.assertNotIn("runner_error", result, str(root) + str(result.get("runner_error", "")))
        self.assertNotIn("forced_kill", result)
        self.assertEqual(result["server_returncode"], 0, str(root))
        self.assertEqual(result["probe_returncode"], 0, str(root / "secondary-copy-probe.log"))
        report = result["probe"]
        self.assertTrue(report["browser"].startswith("109."))
        self.assertEqual(len(report["cases"]), 24)
        self.assertTrue(all(row["passed"] for row in report["cases"]))
        self.assertNotIn("fatal", report)
        for key in ("errors", "external", "writes"):
            self.assertEqual(report[key], [])
        isolation = result["isolation"]
        self.assertTrue(isolation["stopped"] and isolation["assets_unchanged"])
        self.assertEqual(isolation["isolation_violations"], [])
        for value in isolation["sqlite_connections"]:
            if value != ":memory:":
                Path(value).resolve().relative_to(root)
        ready = json.loads((root / "server-ready.json").read_text())
        journal = [json.loads(line) for line in Path(ready["journal"]).read_text().splitlines()]
        self.assertTrue(journal)
        self.assertTrue(all(row["method"] in ("GET", "HEAD") for row in journal))
        transport = [json.loads(line) for line in (root / "secondary-copy-transport.jsonl").read_text().splitlines()]
        self.assertTrue(all(row["method"] == "GET" and row["status"] == [200] for row in transport))
        self.assertEqual(Counter((row["path"], row["body_sha256"]) for row in transport),
                         Counter((row["path"], row["body_sha256"]) for row in report["api"]),
                         "Browser API bytes must match the real outer WSGI responses, including restore-host")
        before = json.loads((root / "business-before.json").read_text())
        after = json.loads((root / "business-after.json").read_text())
        self.assertEqual(set(before), set(after))
        for table in before:
            self.assertEqual(before[table], after[table], "Read-only database changed: " + table)
        self.assertFalse(ready["assets"]["secondary_copy"]["global_build"])
        self.assertEqual(ready["assets"]["secondary_copy"]["target"], {"chrome": "109"})
        print("SECONDARY_COPY_LIVE_VERIFIED " + str(root), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
