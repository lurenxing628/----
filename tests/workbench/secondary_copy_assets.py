"""Private CSS candidates; synthetic rule removal is never a historical baseline."""

import json
import os
from pathlib import Path

from tests.workbench.live_environment import REPO, sha256, write_json
from tests.workbench.run_live_server_support import freeze_built_assets, tree_hashes

SOURCE = "frontend/workbench/app/styles/10-shell.css"
TOKEN_SOURCE = "frontend/workbench/app/styles/00-tokens.css"
PUBLIC = "workbench/app/styles/10-shell.css"
PATCH = "  --ui-muted: var(--wb-secondary-copy);\n"


def freeze(root, session):
    result = freeze_built_assets(root, session)
    source = (REPO / SOURCE).read_text(encoding="utf-8")
    if source.count(PATCH) != 1:
        raise ValueError("Expected exactly one scoped secondary-copy correction")
    manifest = json.loads(Path(result["frozen_manifest"]).read_text(encoding="utf-8"))
    for name in (TOKEN_SOURCE, SOURCE):
        public = name[len("frontend/"):]
        target = Path(result["static"]) / public
        if public not in manifest["styles"] or not target.is_file():
            raise ValueError("Published maintained CSS layer is missing; build first: " + public)
        if target.read_bytes() != (REPO / name).read_bytes():
            raise ValueError("Published CSS differs from the current source; build first: " + name)
    before = source.replace(PATCH, "")
    baseline = os.environ.get("SECONDARY_COPY_BASELINE")
    if baseline and Path(baseline).read_text(encoding="utf-8") != before:
        raise ValueError("Provided CSS baseline differs from candidate minus the single correction")
    directory = Path(result["root"]) / "secondary-copy-sources"
    directory.mkdir()
    sources = [{"path": "before.css", "code": before}, {"path": "after.css", "code": source}]
    for item in sources:
        (directory / item["path"]).write_text(item["code"], encoding="utf-8")
    target = Path(result["static"]) / PUBLIC
    formal_hash = sha256(target.read_bytes())
    candidates = []
    for item in sources:
        destination = target.with_name("secondary-copy-before.css") if item["path"] == "before.css" else target
        destination.write_text(item["code"], encoding="utf-8")
        candidates.append({"phase": Path(item["path"]).stem, "source_sha256": sha256(item["code"].encode("utf-8")),
                           "path": str(destination), "sha256": sha256(destination.read_bytes())})
    result["secondary_copy"] = {"source": SOURCE, "formal_style_sha256": formal_hash,
                                "token_source": TOKEN_SOURCE,
                                "token_source_sha256": sha256((REPO / TOKEN_SOURCE).read_bytes()),
                                "baseline_bound_to_provided_file": bool(baseline), "candidates": candidates,
                                "baseline_file": {"path": str(Path(baseline).resolve()),
                                                  "sha256": sha256(Path(baseline).read_bytes())} if baseline else None,
                                "baseline_kind": "provided_css_file" if baseline else "synthetic_single_rule_removal",
                                "historical_baseline_claimed": False,
                                "target": {"chrome": "109"}, "global_build": False,
                                "binding": "Frozen formal main/pages and matching current CSS; only the body secondary-copy alias is removed for the synthetic before candidate"}
    result["hashes"] = tree_hashes(Path(result["root"]))
    write_json(root / "secondary-copy-assets.json", result)
    return result
