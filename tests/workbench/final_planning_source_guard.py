"""Bind the private full-entry host to G's explicit frozen-source inventory."""

import hashlib
import importlib
import json
import os
import sys
from pathlib import Path


def install():
    manifest = os.environ.get("FINAL_PLANNING_SOURCE_MANIFEST")
    harness = os.environ.get("FINAL_PLANNING_SOURCE_HARNESS")
    if not manifest and not harness:
        return None
    if not manifest or not harness:
        raise ValueError("Frozen source manifest and harness must be supplied together.")
    sys.path.insert(0, str(Path(harness).resolve()))
    module = importlib.import_module("source_guard")
    guard = module.FrozenSourceGuard(Path(__file__).resolve().parents[2], Path(harness), Path(manifest))
    guard.restrict_sys_path()

    def audit(event, args):
        if event == "open":
            guard.check_read(args[0])

    sys.addaudithook(audit)
    return guard


def finish(guard, root, label):
    if guard is None:
        return
    guard.verify_files()
    records = guard.inspect_modules()
    value = {"source": str(guard.source), "manifest": str(guard.manifest_path),
             "aggregate_sha256": guard.manifest["aggregate_sha256"],
             "files_checked": len(guard.files), "loaded_modules": records, "sys_path": list(sys.path),
             "harness_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in sorted(guard.harness.glob("*.py"))}}
    (root / ("final_planning_source-" + label + ".json")).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
