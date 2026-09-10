"""Run ER independently; always join server shutdown and retain real evidence."""

import json
import subprocess
import sys
import time
from pathlib import Path

from tests.workbench.live_environment import create_root, environment, write_json
from tests.workbench.test_live_browser import runtime_tools

HERE = Path(__file__).resolve().parent


def run_probe():
    node, browser, modules = runtime_tools()
    root = create_root()
    env = environment(root)
    env.update(NODE_PATH=modules, WORKBENCH_BROWSER=browser, WORKBENCH_NODE=node, AN_PYTHON=sys.executable)
    outcome = {"root": str(root)}
    print("ER_ARTIFACTS " + str(root), flush=True)
    server = None
    with (root / "server.log").open("w") as log:
        try:
            server = subprocess.Popen([sys.executable, "-B", str(HERE / "merged_cycle_ui_server.py"), "--root", str(root)],
                                      env=env, cwd=str(root), stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 240
            ready = root / "server-ready.json"
            while not ready.exists():
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError((root / "server.log").read_text()[-6000:])
                time.sleep(.05)
            with (root / "er-probe.log").open("w") as output:
                probe = subprocess.run([node, str(HERE / "merged_cycle_ui_probe.cjs"), str(ready)], env=env,
                                       cwd=str(root), stdout=output, stderr=subprocess.STDOUT, timeout=1800)
            outcome["probe_returncode"] = probe.returncode
        except Exception as error:
            outcome["runner_error"] = str(error)
        finally:
            if server is not None:
                if server.poll() is None:
                    server.terminate()
                    try:
                        server.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=10)
                        outcome["forced_kill"] = True
                outcome["server_returncode"] = server.returncode
            for name, key in (("server-final.json", "isolation"), ("er-report.json", "probe")):
                if (root / name).is_file():
                    outcome[key] = json.loads((root / name).read_text())
            write_json(root / "er-result.json", outcome)
    return root, outcome
