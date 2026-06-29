#!/usr/bin/env python3
"""Medium optimizer benchmark gate wrapper.

Default mode prints the command plan. Use --run to execute the medium gate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for probe in [here.parent] + list(here.parents):
        if (probe / "app.py").exists() and (probe / "schema.sql").exists():
            return probe
    raise RuntimeError("repo root not found")


REPO_ROOT = find_repo_root()


def command_plan() -> List[Dict[str, object]]:
    py = sys.executable
    return [
        {
            "id": "fjsp_graph_ready_smoke",
            "args": [py, "tests/_scripts_e2e/benchmark_fjsp.py", "--instances", "mk01", "--time-budget", "1", "--calendar-days", "30"],
            "coverage": "FJSP one-instance graph-ready smoke; report path defaults to ignored long_gate dir.",
        },
        {
            "id": "smtwt_local_search",
            "args": [py, "tests/_scripts_e2e/benchmark_smtwt_localsearch.py"],
            "coverage": "SMTWT overdue_count non-degradation shape against Moore-Hodgson optimum.",
        },
        {
            "id": "sgs_large_resource_pool",
            "args": [py, "tests/_scripts_e2e/benchmark_sgs_large_resource_pool.py"],
            "coverage": "Large resource-pool scheduling stays valid and writes ignored long_gate report.",
        },
    ]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or list medium optimizer benchmark gate commands.")
    parser.add_argument("--run", action="store_true", help="execute commands instead of only printing the plan")
    return parser


def run_command(entry: Dict[str, object]) -> Dict[str, object]:
    started = time.time()
    proc = subprocess.run(
        [str(arg) for arg in entry["args"]],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )
    return {
        "id": entry["id"],
        "returncode": int(proc.returncode),
        "elapsed_seconds": round(time.time() - started, 3),
        "stdout_tail": proc.stdout.splitlines()[-12:],
        "stderr_tail": proc.stderr.splitlines()[-12:],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    plan = command_plan()
    if not args.run:
        print(json.dumps({"schema_version": 1, "status": "planned", "commands": plan}, ensure_ascii=False, indent=2))
        return 0
    results = [run_command(entry) for entry in plan]
    status = "passed" if all(item["returncode"] == 0 for item in results) else "failed"
    print(json.dumps({"schema_version": 1, "status": status, "results": results}, ensure_ascii=False, indent=2))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
