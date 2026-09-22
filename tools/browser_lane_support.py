"""Shared targets, runtime discovery and result parsing for browser lane runners."""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List

from tools.browser_lane_files import BROWSER_LANE_FILES, iter_test_files
from tools.full_test_debt_shards import PERF_FILE_PATTERNS

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATTERN = re.compile(r"^(?:=+ )?((?:\d+ \w+(?:, )?)+) in [\d.]+s", re.MULTILINE)
# Prefer the persistent copy; macOS may remove the older /tmp runtime.
BROWSER_CACHE = Path.home() / ".cache/aps-chromium109-assessment"
DEFAULT_BROWSER_CANDIDATES = (
    BROWSER_CACHE / "stage/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
    Path("/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
)
BUNDLED_NODE = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node"


def lane_targets() -> List[str]:
    """Use the same browser and performance inventory as the pytest lane marker."""
    files = [Path(path).relative_to(ROOT).as_posix() for path in iter_test_files(str(ROOT / "tests"))]
    perf_files = [path for path in files if any(fnmatch.fnmatch(path, pattern) for pattern in PERF_FILE_PATTERNS)]
    return sorted(set(BROWSER_LANE_FILES) | set(perf_files))


def default_browser() -> str:
    """Return the first installed candidate, or the persistent path for diagnostics."""
    for candidate in DEFAULT_BROWSER_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    return str(DEFAULT_BROWSER_CANDIDATES[0])


def runtime_environment() -> Dict[str, str]:
    """Resolve real Node/Chromium binaries and preserve the caller's environment."""
    env = dict(os.environ)
    for key in ("FORCE_COLOR", "COLORTERM"):
        env.pop(key, None)
    env["NO_COLOR"] = "1"
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    node = env.get("WORKBENCH_NODE") or (str(BUNDLED_NODE / "bin/node") if (BUNDLED_NODE / "bin/node").is_file() else shutil.which("node"))
    browser = env.get("WORKBENCH_BROWSER") or default_browser()
    missing = []
    if not node or not Path(node).is_file():
        missing.append("WORKBENCH_NODE (Node for Playwright probes)")
    if not Path(browser).is_file():
        missing.append(
            "WORKBENCH_BROWSER (Chromium 109 binary). Unpack the archive next to it:\n"
            f"    unzip -q -o {BROWSER_CACHE}/chromium-mac-arm64-1041.zip -d {BROWSER_CACHE}/stage/\n"
            f"    xattr -dr com.apple.quarantine {BROWSER_CACHE}/stage/chrome-mac/Chromium.app")
    if missing:
        raise SystemExit("Cannot run the opt-in browser lane, missing: " + "; ".join(missing))
    assert node is not None
    env["WORKBENCH_NODE"] = node
    env["WORKBENCH_BROWSER"] = browser
    node_path = [value for value in (env.get("NODE_PATH"), str(BUNDLED_NODE / "node_modules")) if value]
    env["NODE_PATH"] = os.pathsep.join(node_path)
    return env


def parse_summary(log_text: str) -> Dict[str, int]:
    """Read the final pytest count line from combined output."""
    counts: Dict[str, int] = {}
    matches = SUMMARY_PATTERN.findall(log_text)
    if matches:
        for part in matches[-1].split(", "):
            number, label = part.split(" ", 1)
            counts[label.strip()] = int(number)
    return counts


def skipped_reasons(log_text: str) -> List[str]:
    """Keep pytest's -rs reason lines for the lane receipt."""
    return [line.strip() for line in log_text.splitlines() if line.startswith("SKIPPED ")]
