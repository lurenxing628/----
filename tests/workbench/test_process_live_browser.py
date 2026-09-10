"""Actual Chromium 109 and Flask process reads/previews, all business tables unchanged."""

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
    node, browser, modules = runtime_tools()
    check_assets()
    root = create_root()
    env = environment(root)
    env.update({"NODE_PATH": modules, "WORKBENCH_BROWSER": browser})
    result = {"root": str(root)}
    print("WB_PROCESS_ARTIFACTS " + str(root), flush=True)
    with (root / "server-output.log").open("w") as out, (root / "server-errors.log").open("w") as err:
        server = subprocess.Popen([sys.executable, "-B", str(HERE / "process_live_server.py"), "--root", str(root)],
                                  cwd=str(root), env=env, stdout=out, stderr=err)
        try:
            until = time.monotonic() + 60
            ready = root / "server-ready.json"
            while not ready.exists():
                if server.poll() is not None or time.monotonic() >= until:
                    raise RuntimeError("Process fixture startup failed: " + (root / "server-errors.log").read_text()[-7000:])
                time.sleep(.05)
            with (root / "probe-output.log").open("w") as po, (root / "probe-errors.log").open("w") as pe:
                probe = subprocess.run([node, str(HERE / "process_live_probe.cjs"), str(ready)], env=env,
                                       cwd=str(root), stdout=po, stderr=pe, timeout=480)
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
    for file, key in (("server-final.json", "isolation"), ("process-probe-results.json", "probe")):
        if (root / file).exists():
            result[key] = json.loads((root / file).read_text())
    write_json(root / "process-run-result.json", result)
    return root, result


class WorkbenchProcessBrowserTest(unittest.TestCase):
    def test_real_process_reads_and_route_previews(self):
        root, result = run_probe()
        self.assertNotIn("runner_error", result, str(root))
        self.assertNotIn("forced_kill", result)
        self.assertEqual(result["server_returncode"], 0, str(root))
        self.assertEqual(result["probe_returncode"], 0, str(root / "probe-errors.log"))
        self.assertTrue(result["isolation"]["stopped"])
        self.assertTrue(result["isolation"]["backups_and_templates_unchanged"])
        self.assertEqual(result["isolation"]["isolation_violations"], [])
        self.assertEqual(json.loads((root / "business-before.json").read_text()), json.loads((root / "business-after.json").read_text()))
        for db in result["isolation"]["sqlite_connections"]:
            if db != ":memory:":
                Path(db).resolve().relative_to(root)
        self.assertEqual(result["probe"]["summary"]["cases"], 24)
        self.assertEqual(result["probe"]["summary"]["failed"], 0)
        journal = [json.loads(row) for row in (root / "server-requests.jsonl").read_text().splitlines()]
        self.assertTrue(any(row["method"] == "POST" for row in journal))
        self.assertTrue(all(row["method"] in ("GET", "HEAD") or row["method"] == "POST" and row["path"].endswith("/route-preview") for row in journal))
        print("WB_PROCESS_VERIFIED " + json.dumps({"root": str(root), **result["probe"]["summary"]}), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
