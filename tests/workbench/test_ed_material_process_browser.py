"""Opt-in ED full-page material/process tests against an isolated real application."""

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from live_environment import REPO, create_root, environment, write_json
from test_live_browser import runtime_tools


def run_probe():
    node, browser, modules = runtime_tools()
    root = create_root()
    env = environment(root)
    env.update(NODE_PATH=modules, WORKBENCH_BROWSER=browser, WORKBENCH_NODE=node, AN_PYTHON=sys.executable)
    outcome = {"root": str(root)}
    print("ED_ARTIFACTS " + str(root), flush=True)
    server = None
    with (root / "server.log").open("w") as log:
        try:
            server = subprocess.Popen([sys.executable, "-B", str(HERE / "ed_material_process_server.py"), "--root", str(root)],
                                      env=env, cwd=str(root), stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 180
            ready = root / "server-ready.json"
            while not ready.exists():
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError((root / "server.log").read_text()[-6000:])
                time.sleep(.05)
            with (root / "ed-probe.log").open("w") as output:
                probe = subprocess.run([node, str(HERE / "ed_material_process_probe.cjs"), str(ready)], env=env,
                                       cwd=str(root), stdout=output, stderr=subprocess.STDOUT, timeout=1800)
            outcome["probe_returncode"] = probe.returncode
        except Exception as error:
            outcome["runner_error"] = str(error)
        finally:
            if server is not None:
                if server.poll() is None:
                    server.terminate()
                    try:
                        server.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=10)
                        outcome["forced_kill"] = True
                outcome["server_returncode"] = server.returncode
            for name, key in (("server-final.json", "isolation"), ("ed-report.json", "probe")):
                if (root / name).is_file():
                    outcome[key] = json.loads((root / name).read_text())
            write_json(root / "ed-result.json", outcome)
    return root, outcome


@unittest.skipUnless(os.environ.get("ED_RUN_BROWSER") == "1", "Opt-in full-page Chrome109 test")
class EDMaterialProcessBrowserTest(unittest.TestCase):
    def test_real_pages(self):
        root, result = run_probe()
        self.assertFalse(result.get("runner_error"), str(root) + str(result.get("runner_error", ""))[-2500:])
        self.assertNotIn("forced_kill", result)
        self.assertEqual(result["server_returncode"], 0, str(root))
        self.assertEqual(result["probe_returncode"], 0, str(root / "ed-probe.log"))
        self.assertTrue(result["isolation"]["stopped"])
        self.assertEqual(result["isolation"]["isolation_violations"], [])
        print("ED_VERIFIED " + str(root), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
