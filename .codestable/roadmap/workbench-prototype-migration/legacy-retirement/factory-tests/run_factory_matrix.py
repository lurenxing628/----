"""Bind a real method matrix run to a source manifest and test script hashes."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from source_binding import fingerprints, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("variant", choices=("baseline", "candidate"))
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    source = root / ("source" if args.variant == "candidate" else "baseline")
    manifest = json.loads((root / args.manifest).read_text(encoding="utf-8"))
    names = [row["path"] for row in manifest["files"]]
    assert fingerprints(source, names) == manifest["files"]
    runner = Path(__file__).resolve().parent
    scripts = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in runner.glob("*.py")}
    runtime = root / "runs" / (args.run + "-" + args.variant + "-matrix")
    runtime.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, "-B", str(runner / "factory_routes_worker.py"), str(source), str(runtime)]
    if args.variant == "candidate":
        command.append("--candidate")
    with (runtime / "worker.log").open("w", encoding="utf-8") as output:
        result = subprocess.run(command, cwd=str(source), env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", FACTORY_SOURCE_MANIFEST=str(root / args.manifest)),
                                stdout=output, stderr=subprocess.STDOUT, timeout=120)
    assert fingerprints(source, names) == manifest["files"]
    payload = json.loads((runtime / "result.json").read_text(encoding="utf-8"))
    report = {"source_aggregate_sha256": manifest["aggregate_sha256"], "source_unchanged_before_after": True,
              "scripts_sha256": scripts, "result": str(runtime / "result.json"), "returncode": result.returncode,
              "passed": payload["passed"] and result.returncode == 0, "counts": payload.get("counts"), "error": payload.get("error")}
    write_json(root / (args.run + "-" + args.variant + "-matrix.json"), report)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
