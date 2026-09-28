"""Prepare synthetic field data on host; this is not Win7 acceptance execution."""
import os
import sys
from pathlib import Path

from tests.workbench import run_live_server as live
from tests.workbench.final_execution_seed import seed
from tests.workbench.final_master_fixture_support import freeze_full_build


def main():
    root, identity = live.prepare_root(Path(sys.argv[1]))
    live.freeze_built_assets = freeze_full_build
    profile = os.environ.get("WIN7_EXECUTION_SEED_PROFILE", "execution")
    if profile not in ("execution", "calibration"):
        raise ValueError("Unsupported isolated seed profile")
    live.seed_run_data = lambda app, **kwargs: seed(app, profile, root)
    return live.serve(root, identity, profile="mixed")


if __name__ == "__main__":
    sys.exit(main())
