"""EQ: real main.jsx + factory + managed worker, private SQLite/build/port only."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.workbench.live_environment import create_root, environment, write_json
from tests.workbench.piece_main_oracle import verify
from tests.workbench.test_live_browser import runtime_tools

HERE = Path(__file__).resolve().parent
MATRIX = [(1920, "light", False), (1392, "dark", False)]
if os.environ.get("PIECE_MAIN_ALL_THEMES") == "1":
    MATRIX += [(1920, "dark", False), (1392, "light", False)]
if os.environ.get("PIECE_MAIN_LONG_IDS") == "1":
    MATRIX.append((1392, "dark", True))


def invoke(node, name, args, root, env, timeout):
    with (root / (name + ".out.log")).open("w", encoding="utf-8") as out, (root / (name + ".err.log")).open("w", encoding="utf-8") as err:
        result = subprocess.run([node, str(HERE / name)] + args, cwd=str(root), env=env,
                                stdout=out, stderr=err, timeout=timeout)
    return result.returncode


def run_browser(width, theme, long_ids=False):
    node, browser, modules = runtime_tools()
    root = create_root()
    env = environment(root)
    env.update(NODE_PATH=modules, WORKBENCH_BROWSER=browser, WORKBENCH_NODE=node)
    env["PIECE_MAIN_LONG_IDS"] = "1" if long_ids else "0"
    report = {"root": str(root), "width": width, "theme": theme, "long_ids": long_ids}
    print("PIECE_MAIN_ARTIFACTS " + str(root), flush=True)
    assert invoke(node, "piece_main_build.cjs", [str(root)], root, env, 180) == 0, str(root)
    server = None
    with (root / "piece_main_server.out.log").open("w", encoding="utf-8") as out, (root / "piece_main_server.err.log").open("w", encoding="utf-8") as err:
        try:
            server = subprocess.Popen([sys.executable, "-B", str(HERE / "piece_main_server.py"), str(root)],
                                      cwd=str(root), env=env, stdout=out, stderr=err)
            ready = root / "server-ready.json"
            deadline = time.monotonic() + 90
            while not ready.exists():
                assert server.poll() is None, "Factory startup failed: " + str(root)
                assert time.monotonic() < deadline, "Factory startup timeout: " + str(root)
                time.sleep(.1)
            report["ready"] = json.loads(ready.read_text(encoding="utf-8"))
            report["browser_returncode"] = invoke(node, "piece_main_browser.cjs", [str(ready), str(width), theme], root, env, 300)
        except Exception as error:
            report["runner_error"] = str(error)
        finally:
            if server is not None and server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=10)
                    report["forced_kill"] = True
            report["server_returncode"] = None if server is None else server.returncode
    for filename, key in [("piece_main_browser.json", "browser"), ("server-final.json", "isolation")]:
        if (root / filename).exists():
            report[key] = json.loads((root / filename).read_text(encoding="utf-8"))
    if (root / "business-after.json").exists() and "browser" in report:
        report["retention"] = verify(root)
    write_json(root / "piece_main_result.json", report)
    return root, report


@pytest.mark.parametrize("width,theme,long_ids", MATRIX,
    ids=[str(width) + "-" + theme + ("-long-identities" if long_ids else "") for width, theme, long_ids in MATRIX])
def test_real_piece_main_user_chain(width, theme, long_ids):
    root, result = run_browser(width, theme, long_ids)
    assert "runner_error" not in result, result.get("runner_error")
    assert "forced_kill" not in result, str(root)
    assert result["server_returncode"] == 0, str(root / "piece_main_server.err.log")
    isolation = result["isolation"]
    assert isolation["stopped"] and isolation["assets_unchanged"]
    assert isolation["isolation_violations"] == []
    for value in isolation["sqlite_connections"]:
        if value != ":memory:":
            Path(value).resolve().relative_to(root)
    browser = result["browser"]
    assert result["retention"]["errors"] == [], str(root / "piece_main_retention.json")
    assert browser["browser_version"].startswith("109.")
    assert browser["external_requests"] == [] and browser["page_errors"] == []
    assert browser["console_errors"] == [] and browser["served_main"], str(root)
    assert browser["capture_errors"] == [], str(root)
    assert all(row["method"] == "GET" for row in browser["aborted_reads"]), str(root)
    assert all(row["method"] == "GET" and row["failure"] == {"errorText": "net::ERR_ABORTED"}
               for row in browser["failed_requests"]), str(root)
    assert result["browser_returncode"] == 0, browser.get("error", "") + "\nArtifacts: " + str(root)
    assert browser["findings"] == [], json.dumps(browser["findings"], ensure_ascii=False) + "\n" + str(root)
    assert {row["stage"] for row in browser["stages"]} >= {"trial_adopted", "original_plan_and_key_recovered",
        "original_scenario_plan_run_and_candidate_key_recovered"}
    assert result["retention"]["adopted_versions"] == [5, 6]
    assert len(browser["predecessor_links"]["targets"]) == 3
    print("PIECE_MAIN_VERIFIED " + json.dumps({"root": str(root), "matrix": [width, theme],
        "tables": result["retention"]["table_count"], "versions": result["retention"]["adopted_versions"]}), flush=True)
