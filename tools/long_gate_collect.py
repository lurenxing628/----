from __future__ import annotations

import json
import os
from typing import Any, Dict, Mapping

from tools.long_gate_schema import COLLECT_NODEIDS_SCHEMA_VERSION
from tools.quality_gate_shared import (
    QUALITY_GATE_COLLECT_NODEIDS_REL,
    parse_pytest_collect_nodeids,
    sanitize_quality_gate_output,
)


def build_collect_nodeids_payload(stdout: str, *, pytest_version: str, collect_stdout_log_path: str) -> Dict[str, Any]:
    """collect 收集结果的唯一写出形状；`tools.long_gate_records.admit_collect_nodeids` 按同一形状读回。"""
    stdout = sanitize_quality_gate_output(stdout)
    return {
        "schema_version": COLLECT_NODEIDS_SCHEMA_VERSION,
        "nodeids": parse_pytest_collect_nodeids(stdout),
        "collect_stdout_content": stdout,
        "pytest_version": pytest_version,
        "collect_stdout_log_path": collect_stdout_log_path,
    }


def write_collect_nodeids(payload: Mapping[str, Any], *, repo_root: str) -> str:
    abs_path = os.path.join(repo_root, QUALITY_GATE_COLLECT_NODEIDS_REL.replace("/", os.sep))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
    return QUALITY_GATE_COLLECT_NODEIDS_REL
