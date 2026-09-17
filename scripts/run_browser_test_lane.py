"""Run the browser acceptance lane: every test the formal gates deselect with ``-m "not perf"``.

Since 2026-09-17 the daily gate and the formal full gate no longer execute the real
Chromium 109 / Node probes (``tools/browser_lane_files.py``) nor the performance guards
(``tools.full_test_debt_shards.PERF_FILE_PATTERNS``). They are still real acceptance
tests, so run this lane after workbench UI changes and at least weekly. It resolves the
same Node/Chromium runtime as ``scripts/run_workbench_opt_in_browser.py`` (which stays
responsible for the per-test opt-in switches), refuses to start when the runtime is
missing, and writes a JSON report plus the pytest log side by side.

    .venv/bin/python scripts/run_browser_test_lane.py --list
    .venv/bin/python scripts/run_browser_test_lane.py --only final_planning --only final_operations
    .venv/bin/python scripts/run_browser_test_lane.py --report-dir evidence/browser-lane
"""
from __future__ import annotations

import argparse
import datetime
import fnmatch
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_workbench_opt_in_browser import parse_summary, runtime_environment, skipped_reasons  # noqa: E402
from tools.browser_lane_files import BROWSER_LANE_FILES, iter_test_files  # noqa: E402
from tools.full_test_debt_shards import PERF_FILE_PATTERNS  # noqa: E402


def lane_targets() -> List[str]:
    perf_files = [path for path in iter_test_files() if any(fnmatch.fnmatch(path, pattern) for pattern in PERF_FILE_PATTERNS)]
    return sorted(set(BROWSER_LANE_FILES) | set(perf_files))


def select_targets(targets: Sequence[str], only: Sequence[str]) -> List[str]:
    if not only:
        return list(targets)
    return [target for target in targets if any(token in target for token in only)]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the browser acceptance lane (perf-marked tests) with the real runtime.")
    parser.add_argument("--list", action="store_true", help="show the lane targets without running anything")
    parser.add_argument("--only", action="append", default=[], help="only targets whose path contains this text (repeatable)")
    parser.add_argument("--report-dir", default="", help="where to write the JSON report and pytest log (default: a fresh temp dir)")
    args = parser.parse_args(argv)
    targets = select_targets(lane_targets(), args.only)
    missing = [target for target in targets if not (ROOT / target).is_file()]
    if missing:
        raise SystemExit("browser lane lists files that do not exist, refresh tools/browser_lane_files.py: " + ", ".join(missing))
    if not targets:
        raise SystemExit("no lane targets match --only " + ", ".join(args.only))
    if args.list:
        print("\n".join(targets))
        return 0
    env = runtime_environment()
    report_dir = Path(args.report_dir).resolve() if args.report_dir else Path(tempfile.mkdtemp(prefix="aps-browser-lane-"))
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = report_dir / f"browser-lane-{stamp}.log"
    report_path = report_dir / f"browser-lane-{stamp}.json"
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs", "-m", "perf", *targets]
    print(f"BROWSER_LANE report={report_path}", flush=True)
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
    outcome = "passed" if returncode == 0 and counts.get("passed") else "failed"
    report = {
        "lane": "browser",
        "started_at": started.isoformat(timespec="seconds"),
        "duration_s": round((datetime.datetime.now() - started).total_seconds(), 1),
        "command": command,
        "targets": targets,
        "returncode": returncode,
        "counts": counts,
        "skipped": skipped_reasons(log_text),
        "outcome": outcome,
        "log": str(log_path),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"BROWSER_LANE outcome={outcome} counts={counts} report={report_path}", flush=True)
    return 0 if outcome == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
