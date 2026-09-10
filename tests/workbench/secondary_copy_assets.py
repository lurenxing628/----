"""Private before/after style builds; all other formal assets, including main, stay pinned."""

import json
import os
import subprocess
from pathlib import Path

from tests.workbench.live_environment import REPO, sha256, write_json
from tests.workbench.run_live_server_support import freeze_built_assets, tree_hashes

SOURCE = "frontend/workbench/app/WorkbenchControlStyles.jsx"
PATCH = ('      /* Secondary copy on the light canvas; dark retains its own lighter ink. */\n'
         '      html:not([data-theme="dark"]) body.aps-workbench { --ui-muted: #607087; }\n')


def freeze(root, session):
    result = freeze_built_assets(root, session)
    source = (REPO / SOURCE).read_text(encoding="utf-8")
    if source.count(PATCH) != 1:
        raise ValueError("Expected exactly one scoped secondary-copy correction")
    before = source.replace(PATCH, "")
    baseline = os.environ.get("SECONDARY_COPY_BASELINE")
    if baseline and Path(baseline).read_text(encoding="utf-8") != before:
        raise ValueError("Pre-edit evidence differs from candidate minus the single correction")
    directory = Path(result["root"]) / "secondary-copy-sources"
    directory.mkdir()
    sources = [{"path": "before.jsx", "code": before}, {"path": "after.jsx", "code": source}]
    for item in sources:
        (directory / item["path"]).write_text(item["code"], encoding="utf-8")
    babel = REPO / "frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js"
    request = {"babel_path": str(babel), "sources": sources}
    compiled = subprocess.run([os.environ["WORKBENCH_NODE"], str(REPO / "scripts/workbench/compile.cjs")],
                              input=json.dumps(request), text=True, capture_output=True, check=True)
    built = json.loads(compiled.stdout)
    target = Path(result["static"]) / "workbench/app/WorkbenchControlStyles.js"
    formal_hash = sha256(target.read_bytes())
    candidates = []
    for item, output in zip(sources, built["outputs"]):
        destination = target.with_name("secondary-copy-before.js") if item["path"] == "before.jsx" else target
        destination.write_text(output["code"], encoding="utf-8")
        candidates.append({"phase": Path(item["path"]).stem, "source_sha256": sha256(item["code"].encode("utf-8")),
                           "path": str(destination), "sha256": sha256(destination.read_bytes())})
    result["secondary_copy"] = {"source": SOURCE, "formal_style_sha256": formal_hash,
                                "baseline_bound_to_pre_edit_file": bool(baseline), "candidates": candidates,
                                "target": built["target"], "global_build": False,
                                "binding": "Frozen formal main/pages plus only before/after WorkbenchControlStyles candidates"}
    result["hashes"] = tree_hashes(Path(result["root"]))
    write_json(root / "secondary-copy-assets.json", result)
    return result
