"""Isolated cache fixtures; no workbench build, browser, or repository evidence writes."""

from __future__ import annotations

import copy

from tools import long_gate_fingerprint as fingerprint_mod
from tools import long_gate_manifest, quality_gate_shared
from tools.long_gate_cache import write_success
from tools.long_gate_collect import build_collect_nodeids_payload, write_collect_nodeids
from tools.long_gate_schema import stable_json_hash


def real_entries(root):
    manifest = long_gate_manifest.build_manifest_from_quality_gate_plan(
        quality_gate_shared.build_quality_gate_command_plan(), repo_root=str(root)
    )
    return {entry["entry_id"]: entry for entry in manifest["entries"]}


def stub_execution_probes(monkeypatch):
    for name in (
        "_git_executable_realpath", "_git_version", "_node_executable_realpath",
        "_node_version", "_node_browser_runtime_capability", "_chrome_executable_resolution",
        "_chrome_version", "_chrome_executable_identity", "_chrome_headless_preflight",
    ):
        monkeypatch.setattr(fingerprint_mod, name, lambda **kwargs: "stable-runtime")


def seed_collect_proof(root):
    payload = build_collect_nodeids_payload(
        "tests/test_cache_probe.py::test_probe\n", pytest_version="test-runtime"
    )
    write_collect_nodeids(payload, repo_root=str(root))


def cache_success(root, entry, fingerprint):
    outputs = []
    for relpath in entry["output_result_files"]:
        path = root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("{}\n", encoding="utf-8")
        outputs.append(str(path))
    write_success(
        entry, fingerprint,
        {"returncode": 0, "stdout": "fixture: optional browser skipped", "stderr": "", "duration_s": 0.01},
        outputs, repo_root=str(root),
    )


def legacy_plaintext_fingerprint(current, secret):
    old = copy.deepcopy(current)
    environment = old["components"]["environment"]
    environment.pop("schema_version", None)
    environment["values"]["SECRET_KEY"] = secret
    environment["hash"] = stable_json_hash(environment["values"])
    old.pop("hash")
    old["hash"] = "sha256:" + stable_json_hash(old)
    return old
