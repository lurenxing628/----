"""Run the workbench opt-in browser probes with their opt-in switches actually turned on.

The registry group ``workbench_browser_opt_in`` (tools/test_registry_groups_workbench.py) holds real Chromium 109
acceptance tests that are guarded by per-test environment switches such as ``ED_RUN_BROWSER=1``. The daily and
full gates only collect them and report "skipped"; nothing runs them, so UI changes rot them silently (found on
2026-09-14: the material pager text and the process clipping check had been broken since the 2026-09-13 UI refresh).

This lane turns every switch found in the target files on, refuses to count a skipped test as a pass, and writes a
JSON report plus the pytest log next to each other. It is a targeted lane, not a full gate: run it after workbench
UI changes and at least weekly.

    .venv/bin/python scripts/run_workbench_opt_in_browser.py --list
    .venv/bin/python scripts/run_workbench_opt_in_browser.py --only material
    .venv/bin/python scripts/run_workbench_opt_in_browser.py --report-dir evidence/opt-in-browser
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
GROUP_ID = "workbench_browser_opt_in"
SWITCH_PATTERN = re.compile(r'os\.environ\.get\("([A-Z][A-Z0-9_]+)"\)\s*(?:==|!=)\s*"1"')
SUMMARY_PATTERN = re.compile(r"^(?:=+ )?((?:\d+ \w+(?:, )?)+) in [\d.]+s", re.MULTILINE)
DEFAULT_BROWSER = "/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
BUNDLED_NODE = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node"


def load_group() -> dict:
    sys.path.insert(0, str(ROOT))
    from tools import test_registry_groups_workbench as registry

    for value in vars(registry).values():
        if isinstance(value, tuple):
            for group in value:
                if isinstance(group, dict) and group.get("group_id") == GROUP_ID:
                    return group
    raise SystemExit(f"registry group {GROUP_ID} not found in tools/test_registry_groups_workbench.py")


def opt_in_switches(targets: Sequence[str]) -> Dict[str, List[str]]:
    """Map each opt-in environment switch to the test files guarded by it."""
    switches = {}  # type: Dict[str, List[str]]
    for target in targets:
        text = (ROOT / target).read_text(encoding="utf-8")
        for name in sorted(set(SWITCH_PATTERN.findall(text))):
            switches.setdefault(name, []).append(target)
    return switches


def runtime_environment() -> Dict[str, str]:
    env = dict(os.environ)
    for key in ("FORCE_COLOR", "COLORTERM"):  # colourised pytest output breaks the summary parsing
        env.pop(key, None)
    env["NO_COLOR"] = "1"
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    node = env.get("WORKBENCH_NODE") or (str(BUNDLED_NODE / "bin/node") if (BUNDLED_NODE / "bin/node").is_file() else shutil.which("node"))
    browser = env.get("WORKBENCH_BROWSER") or DEFAULT_BROWSER
    missing = []
    if not node or not Path(node).is_file():
        missing.append("WORKBENCH_NODE (Node for Playwright probes)")
    if not Path(browser).is_file():
        missing.append("WORKBENCH_BROWSER (Chromium 109 binary; /tmp copies are removed by macOS daily cleanup)")
    if missing:
        raise SystemExit("Cannot run the opt-in browser lane, missing: " + "; ".join(missing))
    env["WORKBENCH_NODE"] = node
    env["WORKBENCH_BROWSER"] = browser
    node_path = [value for value in (env.get("NODE_PATH"), str(BUNDLED_NODE / "node_modules")) if value]
    env["NODE_PATH"] = os.pathsep.join(node_path)
    return env


def select_targets(group: dict, only: Sequence[str]) -> List[str]:
    targets = list(group["target_paths"])
    if only:
        targets = [target for target in targets if any(token in target for token in only)]
    return targets


def parse_summary(log_text: str) -> Dict[str, int]:
    counts = {}  # type: Dict[str, int]
    matches = SUMMARY_PATTERN.findall(log_text)
    if matches:
        for part in matches[-1].split(", "):
            number, label = part.split(" ", 1)
            counts[label.strip()] = int(number)
    return counts


def skipped_reasons(log_text: str) -> List[str]:
    return [line.strip() for line in log_text.splitlines() if line.startswith("SKIPPED ")]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run workbench opt-in browser probes with their switches turned on.")
    parser.add_argument("--list", action="store_true", help="show targets and switches without running anything")
    parser.add_argument("--only", action="append", default=[], help="only targets whose path contains this text (repeatable)")
    parser.add_argument("--report-dir", default="", help="where to write the JSON report and pytest log (default: a fresh temp dir)")
    args = parser.parse_args(argv)

    group = load_group()
    targets = select_targets(group, args.only)
    if not targets:
        raise SystemExit("no opt-in targets match --only " + ", ".join(args.only))
    switches = opt_in_switches(targets)
    if args.list:
        for target in targets:
            guards = [name for name, files in switches.items() if target in files]
            print(target + ("  <- " + ", ".join(guards) if guards else "  <- no opt-in switch found"))
        return 0

    env = runtime_environment()
    forced = {}  # type: Dict[str, str]
    for name in switches:
        if env.get(name) != "1":
            forced[name] = "1"
            env[name] = "1"
    report_dir = Path(args.report_dir).resolve() if args.report_dir else Path(tempfile.mkdtemp(prefix="aps-opt-in-browser-"))
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = report_dir / f"opt-in-browser-{stamp}.log"
    report_path = report_dir / f"opt-in-browser-{stamp}.json"
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs", *targets]
    print(f"OPT_IN_BROWSER_LANE report={report_path}", flush=True)
    print("switches turned on: " + (", ".join(sorted(forced)) or "none (all already set)"), flush=True)
    started = datetime.datetime.now()
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
        returncode = process.wait()
    log_text = log_path.read_text(encoding="utf-8")
    counts = parse_summary(log_text)
    reasons = skipped_reasons(log_text)
    outcome = "passed"
    if returncode != 0:
        outcome = "failed"
    elif counts.get("skipped", 0) or not counts.get("passed"):
        outcome = "skipped"  # a skipped opt-in test did not run; that is the rot this lane exists to expose
    report = {
        "schema_version": 1, "group": GROUP_ID, "started": started.isoformat(timespec="seconds"),
        "finished": datetime.datetime.now().isoformat(timespec="seconds"), "targets": targets,
        "switches_turned_on": sorted(forced), "switches_already_set": sorted(name for name in switches if name not in forced),
        "runtime": {"node": env["WORKBENCH_NODE"], "browser": env["WORKBENCH_BROWSER"]},
        "pytest_returncode": returncode, "counts": counts, "skipped": reasons, "outcome": outcome, "log": str(log_path),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OPT_IN_BROWSER_RESULT {outcome} {json.dumps(counts, ensure_ascii=False)}", flush=True)
    if outcome == "failed":
        return 1
    if outcome == "skipped":
        print("Skipped opt-in tests did not run; see -rs lines in " + str(log_path), file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
