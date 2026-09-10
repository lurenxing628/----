"""Real whole-workbench browser and stop/restart acceptance. Run as a module."""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from tests.workbench.final_master_fixture_support import changed_sources, snapshot, source_hashes
from tests.workbench.final_master_preservation_support import resource_preservation, restart_preservation
from tests.workbench.live_environment import REPO, create_root, environment, write_json
from tests.workbench.test_live_browser import runtime_tools

HERE = Path(__file__).resolve().parent


def start(root, env, reuse=False):
    command = [sys.executable, "-B", str(HERE / "final_master_server_support.py"), "--root", str(root)]
    if reuse:
        command.append("--reuse-root")
    previous = json.loads((root / "server-ready.json").read_text()) if reuse else None
    stream = (root / ("server-restart.log" if reuse else "server-initial.log")).open("w", encoding="utf-8")
    server = subprocess.Popen(command, env=env, cwd=str(root), stdout=stream, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError("Private factory failed; see " + str(stream.name))
            ready_path = root / "server-ready.json"
            if ready_path.exists():
                ready = json.loads(ready_path.read_text(encoding="utf-8"))
                if ready["pid"] == server.pid and (previous is None or ready["session"] != previous["session"]):
                    assert ready["paths"]["DATABASE_PATH"] == str(root / "db/aps-live.db")
                    assert ready["url"].startswith("http://127.0.0.1:") and not ready["url"].endswith(":53144")
                    return server, stream, ready
            time.sleep(.1)
        raise TimeoutError("Private full-build server did not start within 300 seconds")
    except BaseException:
        if server.poll() is None:
            server.terminate()
        server.wait(timeout=30)
        stream.close()
        raise


def stop(server, stream, ready):
    if server.poll() is None:
        server.terminate()
    code = server.wait(timeout=40)
    stream.close()
    assert code == 0, "Private shutdown failed: " + str(stream.name)
    final = json.loads((Path(ready["root"]) / "sessions" / ready["session"] / "server-final.json").read_text())
    assert final["stopped"] and final["assets_unchanged"] and final["files_retained"]
    assert not final["isolation_violations"]
    for value in final["sqlite_connections"]:
        if value != ":memory:":
            Path(value).resolve().relative_to(Path(ready["root"]))
    assert final["events"].index("runtime_shutdown_joined") < final["events"].index("launcher_locks_released")
    return final


def run(phase="overview"):
    node, browser, modules = runtime_tools()
    root = create_root(Path("/tmp"))
    env = environment(root)
    env.update(WORKBENCH_NODE=node, WORKBENCH_BROWSER=browser, NODE_PATH=modules,
               FINAL_MASTER_PYTHON=sys.executable, AN_PYTHON=sys.executable, PYTHONPATH=str(REPO),
               FINAL_MASTER_PHASE=phase, PYTHONPYCACHEPREFIX=str(root / "tmp/pycache"), CHECKUP_CALLGRAPH=str(root / "tmp/callgraph"))
    report = {"root": str(root), "phase": phase, "source_before": source_hashes(), "commands": []}
    write_json(root / "final-master-source-before.json", report["source_before"])
    print("FINAL_MASTER_ROOT " + str(root), flush=True)
    server = stream = ready = None
    try:
        server, stream, ready = start(root, env)
        report["ready"] = ready
        browser_ready = {**ready, "resource_url": ready["url"] + "/workbench?view=process"}
        write_json(root / "final-master-browser-ready.json", browser_ready)
        before = snapshot(root)
        write_json(root / "final-master-db-before.json", before)
        if phase == "process_batches":
            with (root / "uploads-generation.log").open("w", encoding="utf-8") as output:
                subprocess.run([node, str(HERE / "migrated_process_batch_files.mjs"), str(root)], env=env,
                               cwd=str(root), stdout=output, stderr=subprocess.STDOUT, check=True, timeout=180)
        probe_path = HERE / ("final_master_" + ("overview" if phase == "inspect" else phase) + ".cjs")
        command = [node, str(probe_path), str(root / "final-master-browser-ready.json"), phase]
        report["commands"].append(command)
        with (root / ("browser-" + phase + ".log")).open("w", encoding="utf-8") as output:
            result = subprocess.run(command, env=env, cwd=str(root), stdout=output, stderr=subprocess.STDOUT, timeout=1800)
        report["browser_returncode"] = result.returncode
        report["initial_final"] = stop(server, stream, ready)
        server = None
        after = snapshot(root)
        write_json(root / "final-master-db-after.json", after)
        report["read_database_unchanged"] = before == after
        if phase == "resources":
            proof = resource_preservation(before, after, json.loads((root / "resource-probe-results.json").read_text()), root, ready["pid"])
            report["resource_preservation"] = proof
            write_json(root / "final-master-resource-preservation.json", proof)
        if phase == "process_batches":
            from tests.workbench.final_master_preservation_support import process_batch_preservation

            report["process_batch_preservation"] = process_batch_preservation(before, after, root)
            write_json(root / "final-master-process-batch-preservation.json", report["process_batch_preservation"])
        server, stream, ready = start(root, env, reuse=True)
        restarted = snapshot(root)
        write_json(root / "final-master-db-restarted.json", restarted)
        report["restart_database_unchanged"] = after == restarted
        report["restart_preservation"] = restart_preservation(after, restarted)
        write_json(root / "final-master-restart-preservation.json", report["restart_preservation"])
        report["restart_ready"] = ready
        command = [node, str(HERE / "final_master_overview.cjs"), str(root / "server-ready.json"), "restart"]
        report["commands"].append(command)
        with (root / "browser-restart.log").open("w", encoding="utf-8") as output:
            restarted_probe = subprocess.run(command, env=env, cwd=str(root), stdout=output, stderr=subprocess.STDOUT, timeout=300)
        report["restart_browser_returncode"] = restarted_probe.returncode
        report["restart_final"] = stop(server, stream, ready)
        server = None
        if phase == "resources":
            trace_path = root / ("final-master-schedule-config-trace-" + str(ready["pid"]) + ".json")
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            assert trace["completed"] and trace["attempted_writes"] == 0 and trace["requests"] == []
            assert after["tables"]["ScheduleConfig"] == restarted["tables"]["ScheduleConfig"]
            report["config_restart_preservation"] = {"passed": True, "rows": len(restarted["tables"]["ScheduleConfig"]),
                "trace_path": str(trace_path), "attempted_writes": 0, "rows_exact": True}
        assert result.returncode == 0 and restarted_probe.returncode == 0, "Browser failed; see " + str(root)
        assert report["restart_preservation"]["passed"]
        if phase in ("overview", "inspect", "controls", "context_restore"):
            assert report["read_database_unchanged"]
    finally:
        if server is not None:
            report["cleanup_final"] = stop(server, stream, ready)
        report["source_after"] = source_hashes()
        report["source_changes"] = changed_sources(report["source_before"], report["source_after"])
        write_json(root / "final-master-result.json", report)
    print("FINAL_MASTER_VERIFIED " + str(root), flush=True)
    return root, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("overview", "inspect", "resources", "process_batches", "controls", "context_restore"), default="overview")
    run(parser.parse_args().phase)
