from __future__ import annotations

import fnmatch
import os
from typing import Dict, List, Literal, Sequence, Tuple

from tools.test_registry import iter_startup_regressions

ShardKind = Literal["serial", "parallel"]

SERIAL_FILE_PATTERNS: Tuple[str, ...] = (
    "tests/regression_ui_browser_geometry_smoke.py",
    "tests/regression_runtime_probe_resolution.py",
    "tests/regression_*runtime*.py",
    "tests/regression_*port*.py",
    "tests/regression_check_manual_layout_runtime_resolution.py",
    "tests/regression_validate_dist_runtime_identity.py",
    "tests/test_startup*.py",
    "tests/test_long_gate*.py",
    "tests/test_long_gate_required_regression_cache.py",
    "tests/test_long_gate_startup_regression_cache.py",
    "tests/test_long_gate_full_test_debt_cache.py",
    "tests/test_run_quality_gate.py",
    "tests/test_architecture_fitness.py",
    "tests/test_win7*.py",
)

SERIAL_EXACT_PATHS = frozenset(iter_startup_regressions())

SERIAL_NODEID_PATTERNS: Tuple[str, ...] = (
    "*portfile*",
    "*port_file*",
    "*runtime*",
    "*runtime_probe*",
    "*win7_launcher_runtime_paths*",
    "*long_gate*",
    "*git_hook_checks*",
    "*evidence*",
)


def nodeid_file(nodeid: str) -> str:
    return str(nodeid or "").split("::", 1)[0].replace("\\", "/")


def classify_nodeid(nodeid: str) -> ShardKind:
    path = nodeid_file(nodeid)
    name = os.path.basename(path)
    if path in SERIAL_EXACT_PATHS:
        return "serial"
    if any(fnmatch.fnmatch(path, pattern) for pattern in SERIAL_FILE_PATTERNS):
        return "serial"
    if name.startswith("smoke_web_phase") or name.startswith("test_startup"):
        return "serial"
    if any(fnmatch.fnmatch(str(nodeid or ""), pattern) for pattern in SERIAL_NODEID_PATTERNS):
        return "serial"
    return "parallel"


def split_nodeids(nodeids: Sequence[str], shard_count: int) -> Tuple[List[str], List[List[str]]]:
    if shard_count < 1:
        raise ValueError("shard_count must be >= 1")
    seen = set()
    serial: List[str] = []
    parallel_by_file: Dict[str, List[str]] = {}
    for raw_nodeid in nodeids:
        nodeid = str(raw_nodeid)
        if nodeid in seen:
            raise ValueError(f"duplicate nodeid: {nodeid}")
        seen.add(nodeid)
        if classify_nodeid(nodeid) == "serial":
            serial.append(nodeid)
        else:
            parallel_by_file.setdefault(nodeid_file(nodeid), []).append(nodeid)

    shards: List[List[str]] = [[] for _ in range(int(shard_count))]
    for _, file_nodeids in sorted(parallel_by_file.items(), key=lambda item: item[0]):
        target_index = min(range(len(shards)), key=lambda index: len(shards[index]))
        shards[target_index].extend(file_nodeids)
    return serial, shards
