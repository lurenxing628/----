from __future__ import annotations

import fnmatch
import os
from typing import Dict, List, Literal, Sequence, Tuple

from tools.browser_lane_files import is_browser_lane_file
from tools.test_registry import iter_startup_regressions

ShardKind = Literal["serial", "parallel"]

SERIAL_FILE_PATTERNS: Tuple[str, ...] = (
    "tests/scheduler_graph/test_*.py",
    "tests/algorithm/test_optimizer_end_to_end*.py",
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
    # P6：按「文件名::测试名」匹配(剥掉目录段),避免子目录名(如 app_runtime 含 "runtime")
    # 污染 nodeid 关键词匹配把整目录误判 serial。扁平期目录恒为无关键词的 tests/,行为不变。
    tail = name + str(nodeid or "")[len(path):]
    if any(fnmatch.fnmatch(tail, pattern) for pattern in SERIAL_NODEID_PATTERNS):
        return "serial"
    return "parallel"


# Heavy browser and performance tests were deleted, rather than excluded.
PERF_FILE_PATTERNS: Tuple[str, ...] = ()

def is_perf_nodeid(nodeid: str) -> bool:
    path = nodeid_file(nodeid)
    if is_browser_lane_file(path):
        return True
    return any(fnmatch.fnmatch(path, pattern) for pattern in PERF_FILE_PATTERNS)


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
