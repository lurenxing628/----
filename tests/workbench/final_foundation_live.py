"""Run explicit foundation groups against one private Main host and frozen source."""

import argparse
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.workbench.final_foundation_live_nav_cases import build_navigation_cases, execution_plan
from tests.workbench.final_foundation_live_source_guard import configuration, install, test_snapshot


def browser_handshake(root, env, node, host, report, plan):
    from tests.workbench.final_foundation_live_source_guard import ENV
    from tests.workbench.final_foundation_live_support import HERE, FoundationHost, read_json
    from tests.workbench.live_environment import write_json

    nonce = uuid.uuid4().hex
    control = {"nonce": nonce, "root": str(root), "initial": host.ready, "execution": plan}
    if ENV in env:
        control["source_guard"] = json.loads(env[ENV])
    if plan["navigation_seed"]:
        prepared = read_json(root / "foundation-navigation-seed.json")
        assert prepared["root"] == str(root)
        control["navigation"] = build_navigation_cases(prepared)
        write_json(root / "foundation-navigation-case-plan.json", control["navigation"])
    write_json(root / "foundation-control.json", control)
    command = [node, str(HERE / "final_foundation_live.cjs"), str(root / "foundation-control.json")]
    restarted = browser = None
    with (root / "foundation-browser.stdout.log").open("w", encoding="utf-8") as out, (root / "foundation-browser.stderr.log").open("w", encoding="utf-8") as err:
        try:
            browser = subprocess.Popen(command, cwd=str(root), env=env, stdout=out, stderr=err)
            report["browser_pid"] = browser.pid
            request = root / "foundation-restart-request.json"
            deadline = time.monotonic() + plan["browser_timeout_seconds"]
            while browser.poll() is None:
                if time.monotonic() > deadline:
                    raise TimeoutError("Foundation browser exceeded its declared group deadline")
                if restarted is None and request.exists():
                    value = read_json(request)
                    assert value["nonce"] == nonce and value["browser_pid"] == browser.pid
                    pages = value["pages"]
                    assert plan["restart_pages"] > 0 and len(pages) == plan["restart_pages"]
                    assert len({row["page_id"] for row in pages}) == plan["restart_pages"]
                    assert all(row["alive"] and row["context_id"] for row in pages)
                    report["initial_shutdown"] = host.stop()
                    restarted = FoundationHost(root, port=urlsplit(host.ready["url"]).port, reuse=True,
                                               navigation_seed=host.navigation_seed)
                    ready = restarted.wait_ready()
                    assert ready["url"] == host.ready["url"] and ready["pid"] != host.ready["pid"]
                    report["restart_ready"] = ready
                    write_json(root / "foundation-restart-ready.json", {"nonce": nonce, "browser_pid": browser.pid,
                                                                         "ready": ready, "old_pid_stopped": True})
                time.sleep(0.05)
            report["browser_returncode"] = browser.returncode
        finally:
            if browser is not None and browser.poll() is None:
                browser.terminate()
                try:
                    browser.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    browser.kill()
                    browser.wait()
                    report["forced_browser_stop"] = True
            if "initial_shutdown" not in report:
                report["initial_shutdown"] = host.stop()
            if restarted is not None:
                report["restart_shutdown"] = restarted.stop()
    if (root / "foundation-browser.json").exists():
        report["browser"] = read_json(root / "foundation-browser.json")


def run(parent=None, asset_root=None, expected_build=None, expected_manifest=None, groups=("legacy",), source_config=None):
    plan = execution_plan(groups)
    if set(plan["groups"]) - {"legacy"} and source_config is None:
        raise ValueError("New groups require an explicit frozen source root and forbidden original source root")
    if set(plan["groups"]) - {"legacy"} and not (asset_root and expected_build and expected_manifest):
        raise ValueError("New groups require the authorized prebuilt asset root, build ID and manifest SHA256")
    guard = install(source_config) if source_config is not None else None
    from tests.workbench.final_foundation_live_support import (
        FoundationHost,
        build_private,
        runtime_tools,
        source_snapshot,
        verify_read_retention,
    )
    from tests.workbench.live_environment import create_root, environment, write_json

    node, browser, modules = runtime_tools()
    root = create_root(parent)
    env = environment(root)
    env.update(WORKBENCH_NODE=node, WORKBENCH_BROWSER=browser, NODE_PATH=modules,
               PYTHONPYCACHEPREFIX=str(root / "tmp/pycache"))
    before = source_snapshot()
    report = {"root": str(root), "complete": False, "final_head_bound": False,
              "execution": plan, "test_snapshot": test_snapshot(),
              "scope": "Main shell full-build snapshot; domain business workflows belong to C/D/E/F"}
    write_json(root / "foundation-sources-before.json", before)
    print("FOUNDATION_LIVE_ROOT " + str(root), flush=True)
    try:
        report["build"] = build_private(root, env, node, asset_root, expected_build, expected_manifest)
        host = FoundationHost(root, navigation_seed=plan["navigation_seed"])
        try:
            report["initial_ready"] = host.wait_ready()
        except Exception:
            host.stop()
            raise
        browser_handshake(root, env, node, host, report, plan)
        if plan["restart_pages"]:
            assert "restart_ready" in report, "The planned live-page restart was not executed"
        report["retention"] = verify_read_retention(root, report["initial_ready"], report.get("restart_ready"))
        result = report.get("browser", {})
        report["complete"] = bool(report.get("browser_returncode") == 0 and result.get("complete") and report.get("retention"))
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        after = source_snapshot()
        write_json(root / "foundation-sources-after.json", after)
        report["source_changes"] = sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
        report["source_binding"] = "snapshot_with_source_drift" if report["source_changes"] else "unchanged_snapshot_not_final_HEAD"
        if guard is not None:
            report["source_guard"] = guard.evidence()
            if guard.violations or report["source_changes"]:
                report["complete"] = False
        write_json(root / "foundation-result.json", report)
    return root, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--temp-parent", type=Path)
    parser.add_argument("--prebuilt-asset-root", type=Path)
    parser.add_argument("--expected-build-id")
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument("--groups", default="legacy", help="Comma-separated legacy,canonical,boot or all")
    parser.add_argument("--describe-groups", action="store_true", help="Print fixed denominators and B test hashes without starting a host")
    parser.add_argument("--expected-source-root", type=Path)
    parser.add_argument("--forbid-source-root", type=Path, action="append", default=[])
    parser.add_argument("--expected-test-snapshot-sha256")
    args = parser.parse_args()
    groups = args.groups.split(",")
    if args.describe_groups:
        print(json.dumps({"execution": execution_plan(groups), "test_snapshot": test_snapshot(), "browser_executed": False}, indent=2))
        return 0
    guarded = args.expected_source_root is not None or bool(args.forbid_source_root)
    if guarded and args.expected_source_root is None:
        parser.error("--forbid-source-root requires --expected-source-root")
    config = configuration(args.expected_source_root, args.forbid_source_root, args.expected_test_snapshot_sha256) if guarded else None
    if args.expected_test_snapshot_sha256 and not guarded:
        parser.error("--expected-test-snapshot-sha256 requires source-root guards")
    root, result = run(args.temp_parent, args.prebuilt_asset_root, args.expected_build_id, args.expected_manifest_sha256, groups, config)
    print(json.dumps({"root": str(root), "complete": result["complete"], "source_binding": result["source_binding"]}))
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
