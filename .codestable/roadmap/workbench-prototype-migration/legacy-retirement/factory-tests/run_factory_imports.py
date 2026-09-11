"""Bound sequential subprocesses; preserve failed runs rather than overwrite them."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from import_cases import CASES
from source_binding import fingerprints, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("variant", choices=("candidate", "baseline"))
    parser.add_argument("--run", required=True)
    parser.add_argument("--manifest")
    parser.add_argument("--cases", nargs="*", default=list(CASES))
    args = parser.parse_args()
    root = args.root.resolve()
    source = root / ("source" if args.variant == "candidate" else "baseline")
    manifest_path = root / (args.manifest or (args.variant + "-flash-manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    names = [row["path"] for row in manifest["files"]]
    assert fingerprints(source, names) == manifest["files"], "Candidate source drift before run"
    runner = Path(__file__).resolve().parent
    scripts = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in runner.glob("*.py")}
    results = []
    for key in args.cases:
        runtime = root / "runs" / (args.run + "-" + args.variant + "-" + key)
        runtime.mkdir(parents=True, exist_ok=False)
        command = [sys.executable, "-B", str(runner / "factory_import_worker.py"), str(source), str(runtime), key]
        if args.variant == "candidate":
            command.append("--candidate")
        with (runtime / "worker.log").open("w", encoding="utf-8") as output:
            process = subprocess.run(command, cwd=str(source), env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", FACTORY_SOURCE_MANIFEST=str(manifest_path)),
                                     stdout=output, stderr=subprocess.STDOUT, timeout=120)
        result_path = runtime / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else {"passed": False, "error": "Worker startup failed; inspect worker.log"}
        row = {"case": key, "returncode": process.returncode, "passed": result["passed"], "result": str(result_path), "error": result.get("error")}
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    assert fingerprints(source, names) == manifest["files"], "Candidate source drift during run"
    report = {"source_aggregate_sha256": manifest["aggregate_sha256"], "source_unchanged_before_after": True,
              "scripts_sha256": scripts, "cases": results, "passed": all(row["passed"] and row["returncode"] == 0 for row in results)}
    write_json(root / (args.run + "-" + args.variant + "-imports.json"), report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
