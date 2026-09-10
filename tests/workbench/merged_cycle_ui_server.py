"""ER-only production-mode HTTP server with guarded SQLite and private assets."""

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.workbench import run_live_server as live
from tests.workbench.merged_cycle_ui_assets import freeze
from tests.workbench.merged_cycle_ui_seed import seed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    root, identity = live.prepare_root(parser.parse_args().root)
    original = live.seed_run_data

    def prepare(app, **kwargs):
        result = original(app, **kwargs)
        result["er"] = seed(app)
        return result

    live.seed_run_data = prepare
    live.freeze_built_assets = freeze
    live.FORBIDDEN_PORTS.update({52392, 58448, 64612})
    return live.serve(root, identity, profile="calibration")


if __name__ == "__main__":
    sys.exit(main())
