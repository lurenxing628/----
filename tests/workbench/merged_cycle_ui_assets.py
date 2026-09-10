"""Pin formal main/workbench assets, compile explicit private ER/ED candidates."""

import json
import os
import subprocess
from pathlib import Path

from tests.workbench.ed_material_process_assets import OWNED as ED_COMPONENTS
from tests.workbench.live_environment import REPO, sha256, write_json
from tests.workbench.run_live_server_support import freeze_built_assets, tree_hashes


def freeze(root, session):
    value = freeze_built_assets(root, session)
    assert REPO not in Path(value["root"]).resolve().parents
    order = json.loads((REPO / "scripts/workbench/build-order.json").read_text())
    names = ("ProcessContract.js",) + ED_COMPONENTS
    sources = [{"path": "app/" + name, "code": (REPO / "frontend/workbench/app" / name).read_text(encoding="utf-8")}
               for name in names]
    request = {"babel_path": str(REPO / "frontend/workbench/prototype" / order["babel"]["path"]), "sources": sources}
    result = subprocess.run([os.environ["WORKBENCH_NODE"], str(REPO / "scripts/workbench/compile.cjs")],
                            input=json.dumps(request), text=True, capture_output=True, timeout=180, check=True)
    candidates = []
    for source, output in zip(sources, json.loads(result.stdout)["outputs"]):
        target = Path(value["static"]) / "workbench" / Path(output["path"]).with_suffix(".js")
        baseline = sha256(target.read_bytes())
        target.write_text(output["code"], encoding="utf-8")
        candidates.append({"source": "frontend/workbench/" + source["path"], "source_sha256": sha256(source["code"].encode("utf-8")),
                           "static": str(target), "baseline_sha256": baseline, "candidate_sha256": sha256(target.read_bytes())})
    value.update(global_build=False, candidates=candidates, hashes=tree_hashes(Path(value["root"])),
                 binding="Frozen formal main/workbench plus explicit ER and read-only ED component candidates; not a full rebuild")
    write_json(root / "er-build.json", value)
    return value
