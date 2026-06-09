from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
CURRENT_PAYLOAD = REPO_ROOT / "evidence" / "QualityGate" / "current_full_test_debt.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.full_test_debt_shards import split_nodeids  # noqa: E402


def _parse_counts(raw_value: str) -> List[int]:
    counts: List[int] = []
    for raw_item in str(raw_value or "").split(","):
        text = raw_item.strip()
        if not text:
            continue
        value = int(text)
        if value < 1:
            raise ValueError("shard count must be >= 1")
        if value not in counts:
            counts.append(value)
    if not counts:
        raise ValueError("at least one shard count is required")
    return counts


def _load_nodeids(payload_path: Path) -> List[str]:
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    raw_nodeids = payload.get("collected_nodeids") if isinstance(payload, dict) else None
    nodeids = [str(item) for item in list(raw_nodeids or []) if str(item)]
    if not nodeids:
        raise RuntimeError(f"payload has no collected_nodeids: {payload_path}")
    return nodeids


def _duration_by_nodeid(payload: Dict[str, Any]) -> Dict[str, float]:
    durations: Dict[str, float] = {}
    for report in list(payload.get("reports") or []):
        if not isinstance(report, dict):
            continue
        nodeid = str(report.get("nodeid") or "")
        if not nodeid:
            continue
        durations[nodeid] = durations.get(nodeid, 0.0) + float(report["duration"])
    return durations


def _distribution_row(nodeids: Sequence[str], shard_count: int, durations: Dict[str, float]) -> Dict[str, Any]:
    serial, parallel = split_nodeids(nodeids, int(shard_count))
    parallel_counts = [len(items) for items in parallel]
    non_empty_parallel_counts = [count for count in parallel_counts if count > 0]
    max_parallel = max(non_empty_parallel_counts or [0])
    min_parallel = min(non_empty_parallel_counts or [0])
    serial_report_s = sum(durations.get(nodeid, 0.0) for nodeid in serial)
    parallel_report_s = [sum(durations.get(nodeid, 0.0) for nodeid in shard) for shard in parallel]
    max_parallel_report_s = max(parallel_report_s or [0.0])
    return {
        "shard_count": int(shard_count),
        "serial_count": len(serial),
        "parallel_counts": parallel_counts,
        "max_parallel_count": max_parallel,
        "min_parallel_count": min_parallel,
        "parallel_imbalance": max_parallel - min_parallel,
        "serial_report_s": round(serial_report_s, 3),
        "parallel_report_s": [round(value, 3) for value in parallel_report_s],
        "max_parallel_report_s": round(max_parallel_report_s, 3),
        "estimated_report_s": round(serial_report_s + max_parallel_report_s, 3),
        "total_count": len(nodeids),
    }


def build_distribution(payload_path: Path, shard_counts: Sequence[int]) -> Dict[str, Any]:
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"payload must be a JSON object: {payload_path}")
    nodeids = [str(item) for item in list(payload.get("collected_nodeids") or []) if str(item)]
    if not nodeids:
        raise RuntimeError(f"payload has no collected_nodeids: {payload_path}")
    durations = _duration_by_nodeid(payload)
    try:
        source_payload = str(payload_path.relative_to(REPO_ROOT))
    except ValueError:
        source_payload = str(payload_path)
    return {
        "schema_version": 1,
        "source_payload": source_payload,
        "total_count": len(nodeids),
        "duration_source": "pytest report duration fields",
        "distributions": [_distribution_row(nodeids, count, durations) for count in shard_counts],
    }


def _run_shard_count(shard_count: int, *, allow_dirty_worktree_proof: bool = False) -> Dict[str, Any]:
    command = [
        sys.executable,
        "tools/check_full_test_debt.py",
        "--sharded",
        "--shard-count",
        str(shard_count),
    ]
    if allow_dirty_worktree_proof:
        command.append("--allow-dirty-worktree-proof")
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=str(REPO_ROOT), check=False)
    duration_s = time.perf_counter() - started
    return {
        "shard_count": int(shard_count),
        "duration_s": round(duration_s, 3),
        "returncode": int(completed.returncode),
        "command": command,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark or inspect full_test_debt shard counts.")
    parser.add_argument("--payload", default=str(CURRENT_PAYLOAD), help="current_full_test_debt payload to inspect")
    parser.add_argument("--counts", default="", help="comma-separated shard counts")
    parser.add_argument("--shard-counts", default="3,4,5,6", help="comma-separated shard counts")
    parser.add_argument("--mode", choices=("estimate", "run"), default="estimate")
    parser.add_argument("--run", action="store_true", help="alias for --mode run")
    parser.add_argument("--allow-dirty-worktree-proof", action="store_true")
    parser.add_argument("--write-json", default="", help="optional output JSON path")
    args = parser.parse_args(argv)

    payload_path = Path(str(args.payload))
    if not payload_path.is_absolute():
        payload_path = REPO_ROOT / payload_path
    shard_counts = _parse_counts(str(args.counts or args.shard_counts))
    result = build_distribution(payload_path, shard_counts)
    mode = "run" if bool(args.run) else str(args.mode)
    result["mode"] = mode
    if mode == "run":
        result["runs"] = [
            _run_shard_count(count, allow_dirty_worktree_proof=bool(args.allow_dirty_worktree_proof))
            for count in shard_counts
        ]

    output = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.write_json:
        output_path = Path(str(args.write_json))
        if not output_path.is_absolute():
            output_path = REPO_ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
