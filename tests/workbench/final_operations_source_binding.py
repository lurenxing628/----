"""Observe every imported repo-owned module when running a sealed full copy."""

import hashlib
import json
import os
import stat
import sys
from pathlib import Path


def source_binding():
    name = os.environ.get("FINAL_OPERATIONS_SOURCE_MANIFEST")
    if not name:
        return None
    manifest = json.loads(Path(name).read_text(encoding="utf-8"))
    root, origin = Path(manifest["root"]).resolve(), Path(manifest["origin"]).resolve()
    rows = {row["path"]: row for row in manifest["files"]}
    packages = {Path(path).parts[0] if "/" in path else Path(path).stem for path in rows if path.endswith(".py")}
    loaded, violations = [], []
    for module_name, module in list(sys.modules.items()):
        value = getattr(module, "__file__", None)
        if not value:
            continue
        path = Path(value).resolve()
        owned_package = module_name.split(".")[0] in packages
        if Path(sys.prefix).resolve() in path.parents and not owned_package:
            continue
        if root not in path.parents and origin not in path.parents and not owned_package:
            continue
        if root not in path.parents:
            violations.append({"module": module_name, "path": str(path), "reason": "outside_sealed_source"})
            continue
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        actual = {"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                  "mode": stat.S_IMODE(path.stat().st_mode)}
        if actual != rows.get(relative):
            violations.append({"module": module_name, "path": str(path), "reason": "sealed_source_mismatch"})
        loaded.append({"module": module_name, "absolute_path": str(path), **actual})
    return {"manifest": name, "aggregate_sha256": manifest["aggregate_sha256"],
            "root": str(root), "loaded": loaded, "violations": violations}
