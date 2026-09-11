"""Scoped verification only. Never runs all-algorithm tests or the shared gate."""

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PRODUCT = [
    "core/algorithm_runtime/downtime.py", "core/algorithm_runtime/internal_slot.py",
    "core/algorithm_runtime/run_state.py", "core/algorithm_runtime/slot_overlap_reuse.py",
    "core/algorithms/greedy/dispatch/sgs.py", "core/algorithms/greedy/dispatch/sgs_scoring.py",
    "core/algorithms/greedy/internal_operation.py", "core/algorithms/greedy/auto_assign.py",
]
NEW_TESTS = ["tests/_support/sgs_slot_reuse_case.py", "tests/algorithm/test_sgs_slot_reuse_contract.py",
             "tests/algorithm/test_sgs_slot_reuse_equivalence.py"]


def main():
    paths = PRODUCT + NEW_TESTS
    source_hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}
    for path in paths:
        ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path, feature_version=(3, 8))
    selected = set()
    for pattern in ("test_sgs*.py", "test_auto_assign*.py", "test_dispatch_callback*.py",
                    "test_internal_slot_estimator_consistency.py", "test_downtime_overlap_index_equivalence.py",
                    "test_machine_last_state_gap_backfill_contract.py"):
        selected.update(str(path.relative_to(ROOT)) for path in (ROOT / "tests/algorithm").glob(pattern))
    commands = [
        [sys.executable, "-m", "pytest", "-q", *sorted(selected)],
        [sys.executable, "-m", "ruff", "check", *paths],
        [sys.executable, "-m", "pyright", *paths],
    ]
    evidence = []
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        evidence.append(dict(command=command, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
        print(result.stdout, end="", flush=True)
        print(result.stderr, end="", file=sys.stderr, flush=True)
    after_hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}
    report = dict(scope="SGS and immediate slot/resource contracts only", python=sys.version,
                  python38_ast=True, test_files=sorted(selected), commands=evidence,
                  source_sha256=source_hashes, sources_unchanged=source_hashes == after_hashes,
                  full_algorithm_run=False, clean_worktree_proof=False)
    (OUT / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if report["sources_unchanged"] and all(row["returncode"] == 0 for row in evidence) else 1)


if __name__ == "__main__":
    main()
