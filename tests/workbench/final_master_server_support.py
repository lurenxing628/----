"""Task C server entry: real LiveRunServer, no shared server or app changes."""

import argparse
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

from tests.workbench import run_live_server as live
from tests.workbench.final_master_fixture_support import freeze_full_build, seed_master
from tests.workbench.live_environment import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--reuse-root", action="store_true")
    args = parser.parse_args()
    root, identity = live.prepare_root(args.root, reuse=args.reuse_root)
    config_trace = None
    if os.environ.get("FINAL_MASTER_PHASE") == "resources":
        from tests.workbench.final_master_config_trace_support import trace_schedule_config

        config_trace = trace_schedule_config(root)
    original_seed = live.seed_run_data

    def prepare(app, **kwargs):
        phase = os.environ.get("FINAL_MASTER_PHASE", "overview")
        if phase == "resources":
            from tests.workbench.live_server import seed_fixture
            from tests.workbench.resource_live_server import seed_resources

            result = seed_fixture(app, root)
            seed_resources(app)
            result["task_c"] = {"profile": phase}
            assert config_trace is not None, "Resource run requires its configuration observer"
            config_trace["attach"](app)
            return result
        if phase == "process_batches":
            from tests.workbench.live_server import seed_fixture
            from tests.workbench.migration_pages_live_server import seed

            result = seed_fixture(app, root)
            seed(app)
            result["task_c"] = {"profile": phase, "private_legacy_column": "PartOperations.private_stage_note"}
            return result
        result = original_seed(app, **kwargs)
        result["task_c"] = seed_master(app)
        return result

    live.seed_run_data = prepare
    live.freeze_built_assets = freeze_full_build
    live.FORBIDDEN_PORTS.update({53144, 52392, 58448, 64612})
    try:
        return live.serve(root, identity, reuse=args.reuse_root, profile="mixed")
    finally:
        if config_trace is not None:
            config_trace["finish"]()
        if os.environ.get("FINAL_OPERATIONS_SOURCE_MANIFEST"):
            from tests.workbench.final_operations_source_binding import source_binding

            binding = source_binding()
            write_json(root / ("final-master-imports-" + str(os.getpid()) + ".json"), binding)
            assert binding is not None and not binding["violations"], "Private source import binding failed"


if __name__ == "__main__":
    sys.exit(main())
