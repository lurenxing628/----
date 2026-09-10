"""Revalidate saved process oracles without repeating successful UI or changing historical reports."""

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.workbench.final_master_fixture_support import snapshot, source_hashes
from tests.workbench.final_master_resource_resume_support import digest, read_json
from tests.workbench.final_operations_source_binding import source_binding
from tests.workbench.live_environment import REPO, read_identity, write_json
from tests.workbench.test_live_browser import runtime_tools


def run(root):
    root = root.resolve()
    read_identity(root)
    files = ["final-master-result.json", "an-process-batch-report.json"]
    hashes = {name: digest(root / name) for name in files}
    original = read_json(root / files[0])
    assert original["phase"] == "process_batches" and original["browser_returncode"] == 1
    assert original["restart_browser_returncode"] == 0 and not original["source_changes"]
    assert original["process_batch_preservation"]["passed"] and original["restart_preservation"]["passed"]
    assert original["initial_final"]["stopped"] and original["restart_final"]["stopped"]
    manifest = read_json(Path(original["ready"]["assets"]["frozen_manifest"]))
    assert all(digest(REPO / row["path"]) == row["sha256"] for row in manifest["inputs"])
    node, _, modules = runtime_tools()
    env = dict(os.environ, AN_PYTHON=sys.executable, PYTHONPATH=str(REPO), NODE_PATH=modules)
    before, sources = snapshot(root), source_hashes()
    command = [node, str(REPO / "tests/workbench/final_master_process_revalidate.cjs"), str(root)]
    log_path = root / ("final-master-process-revalidation-" + str(os.getpid()) + ".log")
    with log_path.open("w", encoding="utf-8") as log:
        result = subprocess.run(command, env=env, cwd=str(REPO), stdout=log, stderr=subprocess.STDOUT, timeout=300)
    assert result.returncode == 0, "Revalidation failed; original results retained; see " + str(log_path)
    assert snapshot(root) == before and source_hashes() == sources
    assert {name: digest(root / name) for name in files} == hashes
    binding = source_binding()
    assert binding is not None and not binding["violations"]
    write_json(root / ("final-master-process-resume-imports-" + str(os.getpid()) + ".json"), binding)
    proof_path = root / "final-master-process-revalidation.json"
    proof = read_json(proof_path)
    report = {"root": str(root), "passed": True, "browser_rerun": False, "old_results_unchanged": hashes,
              "build_id": manifest["build_id"], "summary": proof["summary"], "proof_path": str(proof_path),
              "proof_sha256": digest(proof_path), "database_unchanged_by_revalidation": True,
              "preservation_passed_in_original_run": True, "restart_passed_in_original_run": True,
              "source_binding": {key: binding[key] for key in ("root", "aggregate_sha256", "manifest", "violations")}}
    write_json(root / "final-master-process-resume-result.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    run(Path(sys.argv[1]))
