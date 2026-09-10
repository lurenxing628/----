"""Opt-in AN integrated UI probe; fresh root, frozen assets, real application only."""

import hashlib
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from live_environment import REPO, check_assets, create_root, environment, write_json
from migrated_process_batch_oracle import preservation, snapshot
from test_live_browser import runtime_tools


def provenance():
    files = [REPO / "app.py", REPO / "schema.sql"]
    for folder in ("core", "data", "web", "tests/workbench"):
        files.extend((REPO / folder).rglob("*.py"))
    files.extend(HERE.glob("migrated_process_batch*.cjs"))
    files.extend(HERE.glob("migrated_process_batch*.mjs"))
    return {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(REPO), text=True).strip(),
            "git_status": subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=str(REPO), text=True),
            "sha256": {str(file.relative_to(REPO)): hashlib.sha256(file.read_bytes()).hexdigest()
                       for file in sorted(set(files))}}


def run_probe():
    node, browser, modules = runtime_tools()
    check_assets()
    root = create_root()
    env = environment(root)
    env.update({"NODE_PATH": modules, "WORKBENCH_BROWSER": browser, "AN_PYTHON": sys.executable})
    outcome = {"root": str(root), "source_before": provenance()}
    write_json(root / "an-source-before.json", outcome["source_before"])
    print("AN_ARTIFACTS " + str(root), flush=True)
    server = None
    with (root / "server-output.log").open("w") as output, (root / "server-errors.log").open("w") as errors:
        try:
            server = subprocess.Popen([sys.executable, "-B", str(HERE / "migration_pages_live_server.py"), "--root", str(root)],
                                      cwd=str(root), env=env, stdout=output, stderr=errors)
            deadline = time.monotonic() + 180
            ready = root / "server-ready.json"
            while not ready.exists():
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Fixture startup failed: " + (root / "server-errors.log").read_text()[-5000:])
                time.sleep(.05)
            write_json(root / "an-full-before.json", snapshot(root))
            subprocess.run([node, str(HERE / "migrated_process_batch_files.mjs"), str(root)], env=env, cwd=str(root),
                           check=True, timeout=180, stdout=output, stderr=errors)
            with (root / "an-probe.log").open("w") as log:
                result = subprocess.run([node, str(HERE / "migrated_process_batch_probe.cjs"), str(ready)], env=env,
                                        cwd=str(root), timeout=2400, stdout=log, stderr=subprocess.STDOUT)
            outcome["probe_returncode"] = result.returncode
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
            if (root / "db/aps-live.db").exists():
                write_json(root / "an-full-after.json", snapshot(root))
                if (root / "an-full-before.json").exists():
                    try:
                        outcome["preservation"] = preservation(json.loads((root / "an-full-before.json").read_text()), snapshot(root))
                    except AssertionError as error:
                        outcome["preservation"] = {"passed": False, "error": str(error)}
                    write_json(root / "an-preservation.json", outcome["preservation"])
            outcome["source_after"] = provenance()
            outcome["concurrent_source_changes"] = [name for name, digest in outcome["source_before"]["sha256"].items()
                                                     if outcome["source_after"]["sha256"].get(name) != digest]
            for filename, key in (("server-final.json", "isolation"), ("an-process-batch-report.json", "probe")):
                if (root / filename).exists():
                    outcome[key] = json.loads((root / filename).read_text())
            write_json(root / "an-run-result.json", outcome)
    return root, outcome


@unittest.skipUnless(os.environ.get("AN_RUN_BROWSER") == "1", "Opt-in real Chrome109 fixture")
class MigratedProcessBatchBrowserTest(unittest.TestCase):
    def test_integrated_real_ui(self):
        root, result = run_probe()
        self.assertNotIn("runner_error", result, str(root))
        self.assertNotIn("forced_kill", result)
        self.assertEqual(result["server_returncode"], 0, str(root))
        self.assertEqual(result["probe_returncode"], 0, str(root / "an-probe.log"))
        self.assertTrue(result["isolation"]["stopped"])
        self.assertTrue(result["isolation"]["backups_and_templates_unchanged"])
        self.assertEqual(result["isolation"]["isolation_violations"], [])
        for value in result["isolation"]["sqlite_connections"]:
            if value != ":memory:":
                Path(value).resolve().relative_to(root)
        for key in ("pageerrors", "external"):
            self.assertEqual(result["probe"][key], [], key)
        before = json.loads((root / "an-full-before.json").read_text())["tables"]
        after = json.loads((root / "an-full-after.json").read_text())["tables"]
        for table in ("ExternalGroups", "Schedule", "OperationExecutionEvents", "Materials", "Machines", "Operators", "Suppliers"):
            if table in before:
                self.assertEqual(before[table], after[table], table)
        for table, owner in (("Parts", "part_no"), ("PartOperations", "part_no"), ("Batches", "batch_id"), ("BatchOperations", "batch_id")):
            originals = {row["__oracle_rowid__"]: row for row in before[table]}
            current = {row["__oracle_rowid__"]: row for row in after[table]}
            for key, old in originals.items():
                new = current[key]
                allowed = {"unit_hours"} if table == "PartOperations" and old[owner] == "PROC-001" else set()
                self.assertEqual({k: v for k, v in old.items() if k not in allowed},
                                 {k: v for k, v in new.items() if k not in allowed}, (table, key))
        print("AN_VERIFIED " + str(root) + " " + json.dumps(result["probe"]["summary"]), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
