"""D real full-entry K/B/P acceptance; screenshots require Main's separate V."""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tests.workbench.final_planning_oracle import verify
from tests.workbench.live_environment import create_root, environment, write_json
from tests.workbench.test_live_browser import runtime_tools

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def verify_build_inputs(root):
    build = json.loads((root / "piece_main_build.json").read_text(encoding="utf-8"))
    changed = [item["path"] for item in build["sources"]
               if hashlib.sha256((REPO / item["path"]).read_bytes()).hexdigest() != item["sha256"]]
    template = REPO / "templates/workbench/index.html"
    if hashlib.sha256(template.read_bytes()).hexdigest() != build["template_sha256"]:
        changed.append("templates/workbench/index.html")
    write_json(root / "final_planning_build_input_recheck.json", {"build_id": build["build_id"], "changed": changed})
    assert not changed, "Build source changed during acceptance: " + repr(changed)


def invoke(node, name, args, root, env, timeout):
    suffix = "-" + args[-1] if name == "final_planning_browser.cjs" else ""
    with (root / (name + suffix + ".out.log")).open("w", encoding="utf-8") as out, \
            (root / (name + suffix + ".err.log")).open("w", encoding="utf-8") as err:
        return subprocess.run([node, str(HERE / name)] + args, cwd=str(root),
                              env=env, stdout=out, stderr=err, timeout=timeout).returncode


def host_phase(root, env, node, width, theme, mode, previous=None):
    label = "final_planning_server-" + mode
    args = [sys.executable, "-B", str(HERE / "final_planning_server.py"), str(root)]
    if previous:
        args += ["reuse", str(urlsplit(previous["url"]).port)]
    result = {"mode": mode}
    with (root / (label + ".out.log")).open("w", encoding="utf-8") as out, \
            (root / (label + ".err.log")).open("w", encoding="utf-8") as err:
        server = subprocess.Popen(args, cwd=str(root), env=env, stdout=out, stderr=err)
        try:
            deadline = time.monotonic() + 90
            while True:
                assert server.poll() is None, "Factory startup failed: " + str(root)
                ready_file = root / "server-ready.json"
                if ready_file.exists():
                    ready = json.loads(ready_file.read_text(encoding="utf-8"))
                    if ready["pid"] == server.pid:
                        break
                assert time.monotonic() < deadline, "Factory startup timed out"
                time.sleep(.1)
            result["ready"] = ready
            result["browser_returncode"] = invoke(node, "final_planning_browser.cjs",
                [str(ready_file), str(width), theme, mode], root, env, 360)
        finally:
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=10)
                    result["forced_kill"] = True
            result["server_returncode"] = server.returncode
        if (root / "server-final.json").exists():
            result["isolation"] = json.loads((root / "server-final.json").read_text(encoding="utf-8"))
    write_json(root / (label + ".json"), result)
    return result


@pytest.mark.parametrize("width,theme", [(1920, "light"), (1920, "dark"), (1392, "light"), (1392, "dark")])
def test_full_planning_actions_and_new_process_retention(width, theme):
    node, browser, modules = runtime_tools()
    root = create_root(os.environ.get("FINAL_PLANNING_TEMP_PARENT"))
    env = environment(root)
    env.update(NODE_PATH=modules, WORKBENCH_BROWSER=browser, WORKBENCH_NODE=node,
               PYTHONPYCACHEPREFIX=str(root / "pycache"))
    print("FINAL_PLANNING_ARTIFACTS " + str(root), flush=True)
    assert invoke(node, "final_planning_build.cjs", [str(root)], root, env, 180) == 0, str(root)
    first = host_phase(root, env, node, width, theme, "actions")
    verify_build_inputs(root)
    assert first["browser_returncode"] == 0, str(root / "final_planning_actions.json")
    second = host_phase(root, env, node, width, theme, "restart", first["ready"])
    verify_build_inputs(root)
    assert second["browser_returncode"] == 0, str(root / "final_planning_restart.json")
    assert first["ready"]["pid"] != second["ready"]["pid"]
    for result in (first, second):
        assert "forced_kill" not in result and result["server_returncode"] == 0, str(root)
        proof = result["isolation"]
        assert proof["stopped"] and proof["assets_unchanged"]
        assert proof["isolation_violations"] == []
        assert proof["python_sources"]["changed"] == [], "Loaded source changed during evidence run"
        assert "runtime_shutdown_joined" in proof["events"]
        for value in proof["sqlite_connections"]:
            if value != ":memory:":
                Path(value).resolve().relative_to(root)
    result = verify(root, first, second)
    write_json(root / "final_planning_result.json", result)
    assert not result["errors"], json.dumps(result, ensure_ascii=False)
    print("FINAL_PLANNING_VERIFIED " + json.dumps({"root": str(root),
          "width": width, "theme": theme, "actions": result["actions"]}), flush=True)
