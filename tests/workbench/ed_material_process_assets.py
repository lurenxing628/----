"""Transpile only explicitly owned candidates into the private frozen copy."""

import json
import os
import subprocess
from pathlib import Path

from tests.workbench.live_environment import REPO, sha256, write_json
from tests.workbench.run_live_server_support import freeze_built_assets, tree_hashes

OWNED = ("ResourceForms.jsx", "ProcessDetail.jsx", "ProcessRouteEntry.jsx", "ProcessSourceEditor.jsx",
         "ProcessHoursEditor.jsx", "ProcessStageEditor.jsx")


def freeze(root, session):
    result = freeze_built_assets(root, session)
    if os.environ.get("ED_CANDIDATE") != "1":
        return result
    order = json.loads((REPO / "scripts/workbench/build-order.json").read_text())
    manifest = json.loads(Path(result["frozen_manifest"]).read_text())
    inputs = {row["path"]: row["sha256"] for row in manifest["inputs"]}
    sources = []
    for name in OWNED:
        file = REPO / "frontend/workbench/app" / name
        if inputs.get(str(file.relative_to(REPO))) != sha256(file.read_bytes()):
            sources.append({"path": "app/" + name, "code": file.read_text(encoding="utf-8")})
    request = {"babel_path": str(REPO / "frontend/workbench/prototype" / order["babel"]["path"]), "sources": sources}
    compiled = subprocess.run([os.environ["WORKBENCH_NODE"], str(REPO / "scripts/workbench/compile.cjs")],
                              input=json.dumps(request), text=True, capture_output=True, check=True)
    candidates = []
    for source, output in zip(sources, json.loads(compiled.stdout)["outputs"]):
        target = Path(result["static"]) / "workbench" / Path(output["path"]).with_suffix(".js")
        old = sha256(target.read_bytes())
        target.write_text(output["code"], encoding="utf-8")
        candidates.append({"source": "frontend/workbench/" + source["path"], "source_sha256": sha256(source["code"].encode("utf-8")),
                           "static": str(target), "baseline_sha256": old, "candidate_sha256": sha256(target.read_bytes())})
    result["ed_candidates"] = candidates
    result["binding"] = "Formal baseline manifest plus explicitly listed private component candidates; not a formal rebuild"
    result["hashes"] = tree_hashes(Path(result["root"]))
    write_json(root / "ed-candidate-assets.json", result)
    return result
