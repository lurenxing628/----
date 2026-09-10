"""Verify full dense candidates through managed HTTP; Main owns formal timing."""

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batches", type=int, default=100)
    parser.add_argument("--operations", type=int, default=2)
    parser.add_argument("--exclusive-window", help="Main's scheduled exclusive-window identifier; only for 100 x 50")
    parser.add_argument("--asset-root", type=Path, help="Main build directory containing asset-manifest.json")
    parser.add_argument("--profile", action="store_true", help="Exploration only; real worker cProfile")
    args = parser.parse_args()
    if not 1 <= args.batches <= 100 or not 1 <= args.operations <= 50:
        parser.error("Use 1..100 batches and 1..50 operations")
    from tests.workbench.final_capacity_probe import run_managed

    result = run_managed(args.output, batches=args.batches, operations=args.operations,
                         exclusive_window=args.exclusive_window, profile=args.profile, asset_root=args.asset_root)
    print(json.dumps({"root": result["root"], "complete": result["complete"],
                      "formal_capacity_passed": result["formal_capacity_passed"], "result": str(args.output / "result.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
