"""Opt-in EI /workbench interactions with factory/routes/temp SQLite and Chrome109."""

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from live_environment import create_root, environment, sha256, write_json
from reports_review_browser_oracle import verify
from test_live_browser import runtime_tools


def run_probe():
    node, browser, modules = runtime_tools()
    root = create_root()
    env = environment(root)
    env.update(NODE_PATH=modules, WORKBENCH_BROWSER=browser, WORKBENCH_NODE=node)
    result = {"root": str(root)}
    print("EI_ARTIFACTS " + str(root), flush=True)
    server = None
    with (root / "server.log").open("w", encoding="utf-8") as log:
        try:
            server = subprocess.Popen([sys.executable, "-B", str(HERE / "reports_review_browser_server.py"),
                                       "--root", str(root)], env=env, cwd=str(root), stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 240
            ready = root / "server-ready.json"
            while not ready.exists():
                if server.poll() is not None or time.monotonic() > deadline:
                    lines = (root / "server.log").read_text(encoding="utf-8").splitlines()
                    raise RuntimeError("\n".join(line for line in lines if not line.startswith("WB_RUN_"))[-7000:])
                time.sleep(.05)
            with (root / "ei-probe.log").open("w", encoding="utf-8") as output:
                probe = subprocess.run([node, str(HERE / "reports_review_browser_probe.cjs"), str(ready)],
                                       env=env, cwd=str(root), stdout=output, stderr=subprocess.STDOUT, timeout=1200)
            result["probe_returncode"] = probe.returncode
        except Exception as error:
            result["runner_error"] = str(error)
        finally:
            if server is not None:
                if server.poll() is None:
                    server.terminate()
                    try:
                        server.wait(timeout=40)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=10)
                        result["forced_kill"] = True
                result["server_returncode"] = server.returncode
            for name, key in (("server-final.json", "isolation"), ("ei-browser.json", "browser")):
                if (root / name).is_file():
                    result[key] = json.loads((root / name).read_text(encoding="utf-8"))
            if (root / "business-before.json").exists() and (root / "business-after.json").exists():
                before = json.loads((root / "business-before.json").read_text(encoding="utf-8"))
                after = json.loads((root / "business-after.json").read_text(encoding="utf-8"))
                changed = [name for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)]
                result["sql_preservation"] = {"changed_tables": changed, "all_tables": len(before),
                    "counts": {name: len(rows) for name, rows in before.items()},
                    "before_sha256": sha256((root / "business-before.json").read_bytes()),
                    "after_sha256": sha256((root / "business-after.json").read_bytes())}
            if (root / "ei-sql.jsonl").exists():
                rows = [json.loads(line) for line in (root / "ei-sql.jsonl").read_text(encoding="utf-8").splitlines()]
                result["read_sql"] = {"statements": len(rows), "writes": [row for row in rows if row["sql"].lstrip().split()[0].upper() in
                    ("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER")]}
            write_json(root / "ei-result.json", result)
    return root, result


@unittest.skipUnless(os.environ.get("EI_RUN_BROWSER") == "1", "Opt-in real main-page Chrome109 test")
class ReportsReviewBrowserTest(unittest.TestCase):
    def test_main_pages(self):
        root, result = run_probe()
        self.assertFalse(result.get("runner_error"), str(root) + str(result.get("runner_error", "")))
        self.assertNotIn("forced_kill", result)
        self.assertEqual(result["server_returncode"], 0, str(root / "server.log"))
        self.assertEqual(result["probe_returncode"], 0, str(root / "ei-probe.log"))
        self.assertTrue(result["isolation"]["stopped"] and result["isolation"]["assets_unchanged"])
        self.assertEqual(result["isolation"]["isolation_violations"], [])
        self.assertEqual(result["sql_preservation"]["changed_tables"], [])
        self.assertEqual(result["read_sql"]["writes"], [])
        self.assertTrue(result["browser"]["browser"].startswith("109."))
        self.assertEqual(result["browser"]["errors"], [])
        self.assertEqual(result["browser"]["external"], [])
        self.assertEqual(result["browser"]["console_errors"], [])
        self.assertEqual(result["browser"]["http_errors"], [])
        self.assertEqual(result["browser"]["summary"]["cases"], 44)
        self.assertEqual(result["browser"]["summary"]["failed"], 0)
        verify(root)
        print("EI_VERIFIED " + str(root), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
