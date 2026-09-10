"""Actual entrypoint, factory, SQLite and managed worker with explicit restart."""

import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.workbench.final_planning_source_guard import finish, install

source_guard = install()

from tests.workbench import run_live_server as host
from tests.workbench.final_planning_seed import observe_official_tables, seed
from tests.workbench.piece_main_server import private_build
from tests.workbench.run_live_server_support import prepare_root

if __name__ == "__main__":
    reuse = len(sys.argv) > 2 and sys.argv[2] == "reuse"
    root, identity = prepare_root(Path(sys.argv[1]), reuse=reuse)
    host.freeze_built_assets = private_build
    required_case = os.environ.get("FINAL_PLANNING_REQUIRED_CASE")
    if required_case:
        from functools import partial

        from tests.workbench.final_planning_required_seed import seed as required_seed

        host.seed_run_data = partial(required_seed, required_case=required_case)
    else:
        host.seed_run_data = seed
    host.FORBIDDEN_PORTS = host.FORBIDDEN_PORTS | {53144}
    attach = host.attach_journal

    def journal(app, path):
        attach(app, path)
        observe_official_tables(app, root)

    host.attach_journal = journal
    port = int(sys.argv[3]) if reuse else 0
    result = host.serve(root, identity, profile="mixed", reuse=reuse, port=port)
    finish(source_guard, root, "restart" if reuse else "first")
    sys.exit(result)
