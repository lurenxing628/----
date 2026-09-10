"""Own one isolated real managed HTTP server; never select an existing live root."""

import argparse
import json
import os
import signal
import sys
import threading
from contextlib import ExitStack
from functools import partial
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.workbench.final_capacity_binding import binding_evidence, install_capacity_binding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    spec = json.loads((args.root / "final-capacity.json").read_text(encoding="utf-8"))
    if spec["root"] != str(args.root.resolve()) or spec["kind"] != "final-capacity-B-v1":
        raise ValueError("This is not a dedicated capacity root")
    binding = install_capacity_binding(required=bool(spec["exclusive_window"]))
    from tests.workbench.final_capacity_assets import freeze_named_assets
    from tests.workbench.final_capacity_observation import observe_worker, peak_rss_bytes
    from tests.workbench.final_capacity_support import seed_dense
    from tests.workbench.run_live_server import LiveRunServer
    from tests.workbench.run_live_server_support import prepare_root, write_json

    root, identity = prepare_root(args.root, reuse=args.reuse)
    stopped = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_args: stopped.set())
    fixture = LiveRunServer(root, identity, args.reuse, profile="first-plan")
    write_json(fixture.directory / "capacity-spec.json", spec)
    source_proof = {"before": binding_evidence(binding)}
    write_json(fixture.directory / "capacity-source-binding.json", source_proof)
    try:
        with ExitStack() as stack:
            stack.enter_context(observe_worker(fixture.directory, profile=args.profile))
            stack.enter_context(patch("tests.workbench.run_live_server.seed_run_data",
                partial(seed_dense, operations=spec["operations"], batches=spec["batches"])))
            if spec.get("asset_root"):
                stack.enter_context(patch("tests.workbench.run_live_server.freeze_built_assets",
                    partial(freeze_named_assets, asset_root=spec["asset_root"], manifest_sha256=spec["manifest_sha256"])))
            ready = fixture.start(port=0)
            if ready["url"].endswith(":53144"):
                raise RuntimeError("Reserved preview port was allocated")
            while not stopped.wait(0.1):
                if Path(ready["stop_file"]).exists():
                    break
            final = fixture.close()
    finally:
        if fixture.final is None:
            fixture.close()
        source_proof["after"] = binding_evidence(binding)
        write_json(fixture.directory / "capacity-source-binding.json", source_proof)
    write_json(fixture.directory / "capacity-process.json", {"pid": os.getpid(), "stopped": True,
               "runtime_closed": final["runtime"]["closed"], "isolation_violations": final["isolation_violations"],
               "peak_rss_bytes": peak_rss_bytes()})
    return 0 if final["assets_unchanged"] and not final["isolation_violations"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
