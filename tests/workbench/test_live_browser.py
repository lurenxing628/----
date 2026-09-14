"""Real isolated Flask + Chromium 109 read-loop. Run directly to avoid unrelated fixtures."""

import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from live_environment import check_assets, create_root, environment, write_json


def runtime_tools():
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node"
    node = os.environ.get("WORKBENCH_NODE") or (str(bundled / "bin/node") if (bundled / "bin/node").is_file() else shutil.which("node"))
    browser = os.environ.get("WORKBENCH_BROWSER") or "/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
    if not node or not Path(browser).is_file():
        raise RuntimeError("Set WORKBENCH_NODE and WORKBENCH_BROWSER to installed Node and Chromium 109")
    module_paths = [value for value in [os.environ.get("NODE_PATH"), str(bundled / "node_modules")] if value]
    return node, browser, os.pathsep.join(module_paths)


def run_probe(probe="live_browser_probe.cjs"):
    tools = runtime_tools()
    check_assets()
    root = create_root()
    env = environment(root)
    env.update({"WORKBENCH_NODE": tools[0], "WORKBENCH_BROWSER": tools[1], "NODE_PATH": tools[2]})
    stdout = (root / "server-output.log").open("w", encoding="utf-8")
    stderr = (root / "server-errors.log").open("w", encoding="utf-8")
    server = None
    outcome = {"root": str(root)}
    print("WB_LIVE_ARTIFACTS " + str(root), flush=True)
    try:
        server = subprocess.Popen([sys.executable, "-B", str(HERE / "live_server.py"), "--root", str(root)],
                                  cwd=str(root), env=env, stdout=stdout, stderr=stderr)
        deadline = time.monotonic() + 60
        ready_file = root / "server-ready.json"
        while not ready_file.exists():
            if server.poll() is not None:
                stderr.flush()
                raise RuntimeError("Isolated Flask startup failed: " + (root / "server-errors.log").read_text(encoding="utf-8")[-7000:])
            if time.monotonic() >= deadline:
                raise TimeoutError("Isolated Flask did not start in 60 seconds")
            time.sleep(0.05)
        outcome["ready"] = json.loads(ready_file.read_text(encoding="utf-8"))
        with (root / "probe-output.log").open("w", encoding="utf-8") as probe_stdout, (root / "probe-errors.log").open("w", encoding="utf-8") as probe_stderr:
            result = subprocess.run([tools[0], str(HERE / probe), str(ready_file)],
                                    cwd=str(root), env=env, stdout=probe_stdout, stderr=probe_stderr, timeout=300)
        outcome["probe_returncode"] = result.returncode
    except Exception as error:
        outcome["runner_error"] = str(error)
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=20)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
                outcome["forced_server_kill"] = True
        outcome["server_returncode"] = server.returncode if server is not None else None
        stdout.close()
        stderr.close()
        for name, key in [("server-final.json", "isolation"), ("probe-results.json", "probe"), ("managed-runtime.json", "runtime")]:
            if (root / name).is_file():
                outcome[key] = json.loads((root / name).read_text(encoding="utf-8"))
        write_json(root / "run-result.json", outcome)
    return root, outcome


class WorkbenchLiveBrowserTest(unittest.TestCase):
    def test_real_isolated_system_read_loop(self):
        root, result = run_probe()
        self.assertNotIn("runner_error", result, result.get("runner_error", "") + "\nArtifacts: " + str(root))
        self.assertNotIn("forced_server_kill", result)
        self.assertEqual(result["server_returncode"], 0, str(root / "server-errors.log"))
        self.assertEqual(result["probe_returncode"], 0, str(root / "probe-results.json"))
        isolation = result["isolation"]
        self.assertTrue(isolation["stopped"])
        self.assertTrue(result["runtime"]["runtime_stopped"])
        self.assertTrue(result["runtime"]["gate_stopped"])
        self.assertTrue(result["runtime"]["locks_released"])
        self.assertTrue(isolation["database_unchanged"], "Read-loop changed the real fixture database")
        self.assertTrue(isolation["backups_and_templates_unchanged"])
        self.assertEqual(isolation["isolation_violations"], [])
        self.assertTrue(isolation["sqlite_connections"])
        for value in isolation["sqlite_connections"]:
            if value != ":memory:":
                Path(value).resolve().relative_to(root)
        report = result["probe"]
        for key in ("page_errors", "console_errors", "external_requests", "failed_requests", "http_errors"):
            self.assertEqual(report[key], [], "Including events delivered while closing browser contexts: " + key)
        self.assertEqual(report["summary"]["cases"], 60)
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertEqual(len(report["first_render"]), 4)
        self.assertTrue(all(row["checks"] == 8 and row["style"] == "available" and row["before_theme_action"] for row in report["first_render"]))
        journal = [json.loads(line) for line in (root / "server-requests.jsonl").read_text(encoding="utf-8").splitlines()]
        real_refs = {row["snapshot_ref"] for row in journal if row.get("source") == "production"}
        browser_refs = {row["snapshot_ref"] for row in report["api_responses"]}
        self.assertTrue(browser_refs)
        self.assertTrue(browser_refs.issubset(real_refs), "Every successful browser payload came from this real Flask instance")
        self.assertTrue(all(row["method"] in ("GET", "HEAD") or
                            row["method"] == "POST" and row["path"] == "/api/workbench/v1/entities/batch/query" for row in journal))
        self.assertTrue(all(row["database_unchanged"] for row in journal), "Every GET or read-only query POST must retain the fixture database")
        print("WB_LIVE_VERIFIED " + json.dumps({"root": str(root), "build_id": report["assets"]["build_id"],
                                               **report["summary"]}), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
