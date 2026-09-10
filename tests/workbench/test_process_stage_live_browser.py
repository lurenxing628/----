"""Opt-in Chromium 109 stage writes, after the main task's final build-ready notice."""

import json
import os
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
    if os.environ.get("WORKBENCH_PROCESS_STAGE_BUILD_READY") != "1":
        raise RuntimeError("Wait for the main task's final build-ready notice; no build runs here.")
    node, browser, modules = runtime_tools()
    assets = check_assets()
    scope = os.environ.get("WORKBENCH_PROCESS_STAGE_SCOPE", "all")
    if scope not in ("regular", "large", "all"):
        raise ValueError("WORKBENCH_PROCESS_STAGE_SCOPE must be regular, large or all")
    root = create_root()
    env = environment(root)
    env.update({"NODE_PATH": modules, "WORKBENCH_BROWSER": browser})
    result = {"root": str(root), "assets": assets, "scope": scope}
    print("WB_PROCESS_STAGE_ARTIFACTS " + str(root), flush=True)
    with (root / "server-output.log").open("w") as out, (root / "server-errors.log").open("w") as err:
        server = subprocess.Popen([sys.executable, "-B", str(HERE / "process_stage_live_server.py"), "--root", str(root)],
                                  cwd=str(root), env=env, stdout=out, stderr=err)
        try:
            deadline = time.monotonic() + 600
            ready = root / "server-ready.json"
            while not ready.exists():
                if server.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("Stage fixture startup failed: " + (root / "server-errors.log").read_text()[-7000:])
                time.sleep(.05)
            with (root / "probe-output.log").open("w") as po, (root / "probe-errors.log").open("w") as pe:
                probe = subprocess.run([node, str(HERE / "process_stage_live_probe.cjs"), str(ready)], env=env,
                                       cwd=str(root), stdout=po, stderr=pe, timeout=2400)
            result["probe_returncode"] = probe.returncode
        except Exception as error:
            result["runner_error"] = str(error)
        finally:
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
                    result["forced_kill"] = True
            result["server_returncode"] = server.returncode
    for file, key in (("server-final.json", "isolation"), ("process-stage-probe-results.json", "probe")):
        if (root / file).exists():
            result[key] = json.loads((root / file).read_text())
    schema = root / "db/process-stage-fixture-schema.json"
    if schema.exists():
        result["fixture_schema"] = json.loads(schema.read_text())
    write_json(root / "process-stage-run-result.json", result)
    return root, result


@unittest.skipUnless(os.environ.get("WORKBENCH_PROCESS_STAGE_BUILD_READY") == "1", "Awaiting main task final build ready")
class WorkbenchProcessStageBrowserTest(unittest.TestCase):
    def test_real_stage_workflow_and_scale(self):
        root, result = run_probe()
        self.assertNotIn("runner_error", result, str(root))
        self.assertNotIn("forced_kill", result)
        self.assertEqual(result["server_returncode"], 0, str(root))
        self.assertEqual(result["probe_returncode"], 0, str(root / "probe-errors.log"))
        self.assertTrue(result["isolation"]["stopped"])
        self.assertTrue(result["isolation"]["backups_and_templates_unchanged"])
        self.assertEqual(result["isolation"]["isolation_violations"], [])
        for db in result["isolation"]["sqlite_connections"]:
            if db != ":memory:":
                Path(db).resolve().relative_to(root)
        before = json.loads((root / "business-before.json").read_text())
        after = json.loads((root / "business-after.json").read_text())
        mutable = {"Parts", "PartOperations", "ExternalGroups", "WorkbenchProcessWorkflow", "WorkbenchProcessOperationConfirmations",
                   "WorkbenchCommandReceipts", "WorkbenchEntityRefs", "sqlite_sequence"}
        for table in before:
            if table not in mutable:
                self.assertEqual(before[table], after[table], table)
        for table in ("Parts", "PartOperations", "ExternalGroups"):
            self.assertEqual([row for row in before[table] if not row["part_no"].startswith("STAGE-")],
                             [row for row in after[table] if not row["part_no"].startswith("STAGE-")], table)
        self.assertEqual(len(before["PartOperations"]), len(after["PartOperations"]))
        self.assertEqual(len(before["ExternalGroups"]), len(after["ExternalGroups"]))
        for old, new in zip(before["PartOperations"], after["PartOperations"]):
            changes = {key for key in old if old[key] != new[key]}
            allowed = {"op_type_name", "unit_hours"} if old["part_no"] == "STAGE-2000" else {"unit_hours", "ext_days"}
            self.assertTrue(changes.issubset(allowed), (old["part_no"], old["seq"], changes))
        for old, new in zip(before["ExternalGroups"], after["ExternalGroups"]):
            self.assertEqual({key: value for key, value in old.items() if key != "total_days"},
                             {key: value for key, value in new.items() if key != "total_days"})
        self.assertEqual([{key: value for key, value in row.items() if key != "revision"} for row in before["WorkbenchEntityRefs"]],
                         [{key: value for key, value in row.items() if key != "revision"} for row in after["WorkbenchEntityRefs"]])
        self.assertEqual(result["probe"]["summary"]["cases"], {"regular": 4, "large": 8, "all": 12}[result["scope"]])
        self.assertEqual(result["probe"]["summary"]["failed"], 0)
        self.assertEqual(result["probe"]["errors"], [])
        self.assertEqual(result["probe"]["external"], [])
        journal = [json.loads(line) for line in (root / "server-requests.jsonl").read_text().splitlines()]
        for action in ("route_confirm", "source_confirm", "hours_confirm"):
            self.assertTrue(any(row["method"] == "POST" and row["path"].endswith("/" + action) and row["status"] == 200 for row in journal))
        receipts = {row["receipt_ref"] for row in journal if row.get("receipt_ref")}
        self.assertTrue(receipts)
        self.assertEqual(receipts, {row["receipt_ref"] for row in after["WorkbenchCommandReceipts"]})
        print("WB_PROCESS_STAGE_VERIFIED " + json.dumps({"root": str(root), **result["probe"]["summary"]}), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
