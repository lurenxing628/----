"""ED-only real factory fixture; no changes to the shared live-server implementation."""

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.workbench import run_live_server as live
from tests.workbench.ed_material_process_assets import freeze
from tests.workbench.ed_material_process_seed import seed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root, identity = live.prepare_root(args.root)
    original = live.seed_run_data

    def prepare(app, **kwargs):
        result = original(app, **kwargs)
        result["ed"] = seed(app)
        return result

    live.seed_run_data = prepare
    live.freeze_built_assets = freeze
    live.FORBIDDEN_PORTS.update({52392, 58448, 64612})
    return live.serve(root, identity, profile="calibration")


if __name__ == "__main__":
    sys.exit(main())
