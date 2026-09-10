"""Freeze the built shell and compile only the three EL-owned candidates."""

import json
import os
import subprocess
from pathlib import Path

from tests.workbench.live_environment import REPO, sha256, write_json
from tests.workbench.run_live_server_support import freeze_built_assets, tree_hashes

OWNED = ("ResourceWorkspace.jsx", "ResourceForms.jsx", "resource-contract.js")


def freeze(root, session):
    result = freeze_built_assets(root, session)
    if os.environ.get("EL_CANDIDATE") != "1":
        return result
    order = json.loads((REPO / "scripts/workbench/build-order.json").read_text())
    sources = [{"path": "app/" + name, "code": (REPO / "frontend/workbench/app" / name).read_text(encoding="utf-8")}
               for name in OWNED]
    request = {"babel_path": str(REPO / "frontend/workbench/prototype" / order["babel"]["path"]), "sources": sources}
    compiled = subprocess.run([os.environ["WORKBENCH_NODE"], str(REPO / "scripts/workbench/compile.cjs")],
                              input=json.dumps(request), text=True, capture_output=True, check=True)
    outputs = json.loads(compiled.stdout)["outputs"]
    assert len(outputs) == len(sources)
    candidates = []
    for source, output in zip(sources, outputs):
        target = Path(result["static"]) / "workbench" / Path(output["path"]).with_suffix(".js")
        old = sha256(target.read_bytes())
        target.write_text(output["code"], encoding="utf-8")
        candidates.append({"source": "frontend/workbench/" + source["path"],
                           "source_sha256": sha256(source["code"].encode("utf-8")), "static": str(target),
                           "baseline_sha256": old, "candidate_sha256": sha256(target.read_bytes())})
    result["el_candidates"] = candidates
    result["binding"] = "Frozen formal build plus three EL component candidates; not a formal rebuild"
    result["hashes"] = tree_hashes(Path(result["root"]))
    write_json(root / "el-candidate-assets.json", result)
    return result
