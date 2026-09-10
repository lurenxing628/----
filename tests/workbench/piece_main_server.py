"""Reuse the real factory/managed-runtime host, replacing only its fixture build/seed."""

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.workbench import run_live_server as host
from tests.workbench.piece_main_seed import seed
from tests.workbench.run_live_server_support import prepare_root, tree_hashes


def private_build(root, _session):
    evidence = json.loads((root / "piece_main_build.json").read_text(encoding="utf-8"))
    Path(evidence["root"]).resolve().relative_to(root)
    evidence["hashes"] = tree_hashes(Path(evidence["root"]))
    return evidence


if __name__ == "__main__":
    root, identity = prepare_root(Path(sys.argv[1]))
    host.freeze_built_assets = private_build
    host.seed_run_data = seed
    host.FORBIDDEN_PORTS = host.FORBIDDEN_PORTS | {52392, 58448, 64612}
    sys.exit(host.serve(root, identity, profile="mixed"))
