"""Task E: current factory and managed host, with owned data and a full offline build."""

import argparse
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.workbench.final_execution_source_binding import finish_guard, install_guard

SOURCE_BINDING = install_guard()

from tests.workbench import run_live_server as live
from tests.workbench.final_execution_seed import seed
from tests.workbench.final_execution_wire import attach_wire
from tests.workbench.run_live_server_support import prepare_root, tree_hashes


def private_assets(root, _session):
    build = root / "full-build"
    manifest_path = build / "static/workbench/asset-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["target"] != "chrome109":
        raise ValueError("Full build must retain Chrome 109")
    return {"root": str(build), "static": str(build / "static"),
            "templates": str(build / "templates"), "build_id": manifest["build_id"],
            "frozen_manifest": str(manifest_path), "hashes": tree_hashes(build),
            "binding": "scripts/workbench/build.py, all live sources including main.jsx",
            "global_build": False, "inputs": manifest["inputs"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--profile", choices=("execution", "reports", "calibration", "chain", "resources"), required=True)
    parser.add_argument("--reuse-root", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    root, identity = prepare_root(args.root, reuse=args.reuse_root)
    original_create = live.LiveRunServer.start

    def start(self, port=0):
        ready = original_create(self, port)
        attach_wire(self.app, self.directory)
        return ready

    live.LiveRunServer.start = start
    live.freeze_built_assets = private_assets
    live.seed_run_data = lambda app, **kwargs: seed(app, args.profile, root)
    live.FORBIDDEN_PORTS = live.FORBIDDEN_PORTS | {53144, 52392, 58448, 64612}
    try:
        return live.serve(root, identity, reuse=args.reuse_root, port=args.port, profile="mixed")
    finally:
        finish_guard(SOURCE_BINDING, root / ("sealed-process-" + str(os.getpid()) + ".json"))


if __name__ == "__main__":
    sys.exit(main())
