from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Mapping

from tools.long_gate_fingerprint import stable_json_hash
from tools.quality_gate_shared import REPO_ROOT, parse_pytest_collect_nodeids

COLLECT_NODEIDS_REL = os.path.join("evidence", "QualityGate", "collect_nodeids.json").replace("\\", "/")
COLLECT_NODEIDS_SCHEMA_VERSION = 1


def _sha256_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _nodeids_by_file(nodeids: List[str]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    for nodeid in nodeids:
        file_path = str(nodeid).split("::", 1)[0]
        grouped.setdefault(file_path, []).append(str(nodeid))
    return {path: grouped[path] for path in sorted(grouped)}


def build_collect_nodeids_payload(
    stdout: str,
    *,
    pytest_version: str = "",
    collect_stdout_log_path: str = "",
) -> Dict[str, Any]:
    nodeids = parse_pytest_collect_nodeids(stdout)
    return {
        "schema_version": COLLECT_NODEIDS_SCHEMA_VERSION,
        "status": "passed",
        "nodeids": nodeids,
        "nodeid_count": len(nodeids),
        "nodeid_hash": stable_json_hash(nodeids),
        "nodeids_by_file": _nodeids_by_file(nodeids),
        "pytest_version": str(pytest_version or ""),
        "generated_from_stdout_sha256": _sha256_text(stdout),
        "collect_stdout_log_path": str(collect_stdout_log_path or "").replace("\\", "/"),
    }


def write_collect_nodeids(payload: Mapping[str, Any], *, repo_root: str = REPO_ROOT) -> str:
    root = os.path.abspath(repo_root)
    rel_path = COLLECT_NODEIDS_REL
    abs_path = os.path.join(root, rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as handle:
        json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
    return rel_path
