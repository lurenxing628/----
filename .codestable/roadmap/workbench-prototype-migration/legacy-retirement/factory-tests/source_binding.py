"""Generate source attestations; copying/applying remains an explicit caller step."""

import argparse
import hashlib
import json
import stat
import sys
from pathlib import Path

from source_inventory import discover, inspect_imports


def inventory(root):
    return discover(root)[0]


def fingerprints(root, paths):
    rows = []
    for name in paths:
        path = root / name
        data = path.read_bytes()
        rows.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                     "mode": format(stat.S_IMODE(path.stat().st_mode), "04o")})
    return rows


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("capture", "check"))
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--origin", type=Path)
    parser.add_argument("--extra", action="append", default=[])
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "capture":
        names, scope = discover(root, args.extra)
        imports = inspect_imports(root, names, scope["owned_import_roots"])
        if imports["missing_repo_modules"]:
            raise RuntimeError("Missing repo-owned source modules: " + repr(imports["missing_repo_modules"]))
        rows = fingerprints(root, names)
        if fingerprints(root, discover(root, args.extra)[0]) != rows:
            raise RuntimeError("Source drifted during capture; no snapshot accepted.")
        value = {"schema_version": 2, "root": str(root), "origin_root": str((args.origin or root).resolve()),
                 "capture_python": sys.version,
                 "scope": scope, "static_import_inventory": imports, "files": rows,
                 "aggregate_sha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()}
        write_json(args.manifest, value)
        args.manifest.with_suffix(".files").write_text("\n".join(names) + "\n", encoding="utf-8")
        print(json.dumps({"files": len(rows), "bytes": sum(row["bytes"] for row in rows), "aggregate_sha256": value["aggregate_sha256"]}))
    else:
        value = json.loads(args.manifest.read_text(encoding="utf-8"))
        actual = fingerprints(root, [row["path"] for row in value["files"]])
        if actual != value["files"]:
            changed = [a["path"] for a, b in zip(actual, value["files"]) if a != b]
            raise RuntimeError("Snapshot preimage drift: " + repr(changed))
        print(json.dumps({"root": str(root), "verified_files": len(actual), "aggregate_sha256": value["aggregate_sha256"]}))


if __name__ == "__main__":
    main()
