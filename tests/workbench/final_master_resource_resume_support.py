"""Resume only preservation/restart after a successful full browser run; keep its raw result immutable."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from tests.workbench.final_master_acceptance_cli import start, stop
from tests.workbench.final_master_fixture_support import snapshot, source_hashes
from tests.workbench.final_master_preservation_support import resource_preservation, restart_preservation
from tests.workbench.final_operations_source_binding import source_binding
from tests.workbench.live_environment import REPO, environment, read_identity, write_json
from tests.workbench.test_live_browser import runtime_tools


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root):
    root = root.resolve()
    read_identity(root)
    old_path = root / "final-master-result.json"
    old_hash, initial = digest(old_path), read_json(old_path)
    browser_path = root / "resource-probe-results.json"
    browser_hash, browser = digest(browser_path), read_json(browser_path)
    assert initial["phase"] == "resources" and initial["browser_returncode"] == 0
    assert initial["initial_final"]["stopped"] and not initial["source_changes"]
    assert browser["summary"]["cases"] == 224 and browser["summary"]["failed"] == 0
    assert read_json(root / "final-master-resource-probe-sources.json")["selected_scope"] == "all"
    assert not browser["errors"] and not browser["external"]
    assert not browser["unexpected_http_errors"] and not browser["unexpected_failed_requests"] and not browser["unexpected_console_errors"]
    before, after = read_json(root / "final-master-db-before.json"), read_json(root / "final-master-db-after.json")
    assert snapshot(root) == after, "Database changed after the original browser finished"
    manifest = read_json(Path(initial["ready"]["assets"]["frozen_manifest"]))
    assert all(digest(REPO / row["path"]) == row["sha256"] for row in manifest["inputs"])
    report = {"root": str(root), "kind": "preservation_restart_only", "original_result_sha256": old_hash,
              "original_browser_sha256": browser_hash, "build_id": manifest["build_id"], "source_before": source_hashes()}
    server = stream = ready = None
    try:
        report["resource_preservation"] = resource_preservation(before, after, browser, root, initial["ready"]["pid"])
        node, executable, modules = runtime_tools()
        env = environment(root)
        env.update(WORKBENCH_NODE=node, WORKBENCH_BROWSER=executable, NODE_PATH=modules, FINAL_MASTER_PYTHON=sys.executable,
                   FINAL_MASTER_PHASE="resources", PYTHONPATH=str(REPO), PYTHONPYCACHEPREFIX=str(root / "tmp/resume-pycache"),
                   CHECKUP_CALLGRAPH=str(root / "tmp/resume-callgraph"))
        server, stream, ready = start(root, env, reuse=True)
        restarted = snapshot(root)
        report["restart_preservation"] = restart_preservation(after, restarted)
        assert ready["assets"]["build_id"] == initial["ready"]["assets"]["build_id"]
        assert not ready["assets"]["source_differences"]
        write_json(root / "final-master-resource-resume-db.json", restarted)
        command = [node, str(REPO / "tests/workbench/final_master_overview.cjs"), str(root / "server-ready.json"), "restart"]
        with (root / "browser-resource-resume-restart.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(command, env=env, cwd=str(root), stdout=log, stderr=subprocess.STDOUT, timeout=300)
        report["restart_browser_returncode"] = result.returncode
        report["restart_final"] = stop(server, stream, ready)
        server = None
        trace_path = root / ("final-master-schedule-config-trace-" + str(ready["pid"]) + ".json")
        trace = read_json(trace_path)
        assert trace["completed"] and trace["attempted_writes"] == 0 and trace["requests"] == []
        assert after["tables"]["ScheduleConfig"] == restarted["tables"]["ScheduleConfig"]
        report["config_restart_preservation"] = {"passed": True, "rows": len(restarted["tables"]["ScheduleConfig"]),
            "rows_exact": True, "attempted_writes": 0, "trace_path": str(trace_path), "trace_sha256": digest(trace_path)}
        assert result.returncode == 0
        report["passed"] = True
    finally:
        if server is not None:
            report["cleanup_final"] = stop(server, stream, ready)
        report["source_after"] = source_hashes()
        assert report["source_before"] == report["source_after"]
        binding = source_binding()
        assert binding is not None and not binding["violations"]
        write_json(root / ("final-master-resume-imports-" + str(os.getpid()) + ".json"), binding)
        report["source_binding"] = {key: binding[key] for key in ("root", "aggregate_sha256", "manifest", "violations")}
        assert digest(old_path) == old_hash and digest(browser_path) == browser_hash, "Do not rewrite historical results"
        write_json(root / "final-master-resource-resume-result.json", report)
    print(json.dumps({"root": str(root), "passed": report.get("passed", False), "original_browser_rerun": False,
                      "config_rows": report["config_restart_preservation"]["rows"]}))


if __name__ == "__main__":
    run(Path(sys.argv[1]))
