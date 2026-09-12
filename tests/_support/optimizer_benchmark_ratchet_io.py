"""Light-ratchet measurement receipts and clean-only atomic baseline storage."""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
from pathlib import Path

from tests._support.optimizer_compare_algorithms_provenance import capture_source, machine_metadata, source_binding

RATCHET_SCHEMA_VERSION = 2
RATCHET_MEASUREMENT = {
    "clock": "time.perf_counter",
    "scope": "whole_light_ratchet_including_oracle_and_all_cases",
    "execution": "serial_single_worker",
}


def snapshot_protocol_failures(snapshot, *, label):
    if snapshot.get("schema_version") != RATCHET_SCHEMA_VERSION or any(
        key not in snapshot for key in ("measurement", "machine", "source_before", "source_after", "runtime_ms")
    ):
        return [{"reason": label + "_migration_required", "required_schema_version": RATCHET_SCHEMA_VERSION}]
    failures = []
    if snapshot.get("measurement") != RATCHET_MEASUREMENT:
        failures.append({"reason": label + "_measurement_mismatch"})
    if not isinstance(snapshot.get("machine"), dict) or not snapshot["machine"]:
        failures.append({"reason": label + "_machine_unknown"})
    runtime = snapshot.get("runtime_ms")
    if type(runtime) not in (int, float) or not math.isfinite(runtime) or runtime <= 0:
        failures.append({"reason": label + "_runtime_unknown"})
    before, after = snapshot.get("source_before"), snapshot.get("source_after")
    if not all(_valid_receipt(source) for source in (before, after)):
        return failures + [{"reason": label + "_source_unknown"}]
    binding = source_binding(before, after)
    if before != after:
        failures.append({"reason": label + "_source_changed_during_run"})
    dirty = not before["worktree_clean"] or not after["worktree_clean"]
    if snapshot.get("dirty_worktree") is not dirty or snapshot.get("git_commit") != after["head"]:
        failures.append({"reason": label + "_source_metadata_mismatch"})
    if snapshot.get("proof_binding_status") != binding:
        failures.append({"reason": label + "_source_binding_mismatch"})
    return failures


def _valid_receipt(source):
    if not isinstance(source, dict):
        return False
    for key, length in (("head", 40), ("source_sha256", 64), ("diff_sha256", 64)):
        value = source.get(key)
        if not isinstance(value, str) or re.fullmatch("[0-9a-f]{" + str(length) + "}", value) is None:
            return False
    if not all(isinstance(source.get(key), str) and source[key] for key in ("repo_root", "branch")):
        return False
    status = source.get("status_porcelain")
    return isinstance(status, list) and type(source.get("worktree_clean")) is bool and source["worktree_clean"] == (not status)


def load_baseline(path):
    path = Path(path)
    if not path.exists():
        return None

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("nonfinite JSON number: " + value)

    result = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
    if not isinstance(result, dict):
        raise ValueError("baseline must be an object")
    return result


def write_baseline_file(path, snapshot, *, repo_root):
    current = capture_source(repo_root)
    if current.get("worktree_clean") is not True or current != snapshot["source_after"]:
        raise ValueError("formal baseline requires current clean source to match the measured source receipt")
    if machine_metadata() != snapshot["machine"]:
        raise ValueError("formal baseline machine/runtime mismatch")
    text = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=str(path.parent), delete=False) as stream:
            temporary = stream.name
            stream.write(text)
        os.replace(temporary, str(path))
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)
