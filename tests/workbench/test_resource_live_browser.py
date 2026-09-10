"""Run directly: real Chromium 109 controls backed by a guarded temporary database."""

import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from live_environment import check_assets, create_root, environment, write_json
from test_live_browser import runtime_tools


def run_probe():
    tools = runtime_tools()
    check_assets()
    root = create_root()
    env = environment(root)
    env.update({"NODE_PATH": tools[2], "WORKBENCH_BROWSER": tools[1]})
    print("WB_RESOURCE_ARTIFACTS " + str(root), flush=True)
    result = {"root": str(root)}
    with (root / "server-output.log").open("w") as out, (root / "server-errors.log").open("w") as err:
        server = subprocess.Popen([sys.executable, "-B", str(HERE / "resource_live_server.py"), "--root", str(root)],
                                  cwd=str(root), env=env, stdout=out, stderr=err)
        try:
            until = time.monotonic() + 60
            ready = root / "server-ready.json"
            while not ready.exists():
                if server.poll() is not None or time.monotonic() >= until:
                    raise RuntimeError("Resource fixture startup failed: " + (root / "server-errors.log").read_text()[-7000:])
                time.sleep(.05)
            with (root / "probe-output.log").open("w") as probe_out, (root / "probe-errors.log").open("w") as probe_err:
                probe = subprocess.run([tools[0], str(HERE / "resource_live_probe.cjs"), str(ready)],
                                       env=env, cwd=str(root), stdout=probe_out, stderr=probe_err, timeout=900)
            result["probe_returncode"] = probe.returncode
        except Exception as error:
            result["runner_error"] = str(error)
        finally:
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
                    result["forced_kill"] = True
            result["server_returncode"] = server.returncode
    for name, key in (("server-final.json", "isolation"), ("resource-probe-results.json", "probe")):
        if (root / name).exists():
            result[key] = json.loads((root / name).read_text())
    write_json(root / "resource-run-result.json", result)
    return root, result


class WorkbenchResourceBrowserTest(unittest.TestCase):
    def test_resources_through_real_browser_controls(self):
        root, result = run_probe()
        self.assertNotIn("runner_error", result, str(root))
        self.assertNotIn("forced_kill", result)
        self.assertEqual(result["server_returncode"], 0, str(root))
        self.assertEqual(result["probe_returncode"], 0, str(root / "resource-probe-results.json"))
        self.assertTrue(result["isolation"]["stopped"])
        self.assertTrue(result["isolation"]["backups_and_templates_unchanged"])
        self.assertEqual(result["isolation"]["isolation_violations"], [])
        for db in result["isolation"]["sqlite_connections"]:
            if db != ":memory:":
                Path(db).resolve().relative_to(root)
        before = json.loads((root / "business-before.json").read_text())
        after = json.loads((root / "business-after.json").read_text())
        for table in before:
            if table != "WorkbenchCommandReceipts":
                self.assertEqual(before[table], after[table], "Unexpected retained data change: " + table)
        receipts = after["WorkbenchCommandReceipts"]
        self.assertEqual(len(receipts), len({item["request_key"] for item in receipts}))
        committed = {item["request_key"] for item in result["probe"]["commands"] if item.get("receipt_ref")}
        self.assertEqual(committed, {item["request_key"] for item in receipts})
        self.assertGreaterEqual(result["probe"]["summary"]["cases"], 224)
        print("WB_RESOURCE_VERIFIED " + json.dumps({"root": str(root), **result["probe"]["summary"]}), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
