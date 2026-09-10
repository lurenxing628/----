"""Full application fixture with current offline assets and the real managed host."""

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.workbench import run_live_server as live
from tests.workbench.live_environment import REPO, sha256
from tests.workbench.run_live_server_support import inside, prepare_root, tree_hashes


def private_assets(root, _session):
    build = root / "full-build"
    manifest_path = build / "static/workbench/asset-manifest.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if manifest.get("target") != "chrome109":
        raise ValueError("Full fixture build must retain Chrome 109")
    for item in manifest["files"]:
        file = inside(build / "static", build / "static" / item["path"])
        data = file.read_bytes()
        if sha256(data) != item["sha256"] or len(data) != item["bytes"]:
            raise ValueError("Full fixture build payload changed: " + item["path"])
    for item in manifest["inputs"]:
        file = inside(REPO, REPO / item["path"])
        if sha256(file.read_bytes()) != item["sha256"]:
            raise ValueError("Full fixture build is stale: " + item["path"])
    templates = build / "templates/workbench"
    if not templates.exists():
        shutil.copytree(str(REPO / "templates/workbench"), str(templates))
    if tree_hashes(templates) != tree_hashes(REPO / "templates/workbench"):
        raise ValueError("Frozen fixture templates differ from current sources")
    return {"root": str(build), "static": str(build / "static"),
            "templates": str(build / "templates"), "build_id": manifest["build_id"],
            "sha256": sha256(raw), "frozen_manifest": str(manifest_path),
            "hashes": tree_hashes(build), "source_differences": [],
            "binding": "current full build; actual factory, worker and restore host",
            "global_build": False, "inputs": manifest["inputs"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--reuse-root", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    root, identity = prepare_root(args.root, reuse=args.reuse_root)
    live.freeze_built_assets = private_assets
    live.FORBIDDEN_PORTS = live.FORBIDDEN_PORTS | {53144}
    return live.serve(root, identity, reuse=args.reuse_root, port=args.port, profile="mixed")


if __name__ == "__main__":
    sys.exit(main())
