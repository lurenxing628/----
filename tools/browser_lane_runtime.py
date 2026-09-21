"""Shared browser-lane selection and runtime resolution; never import script entrypoints."""
from __future__ import annotations

import fnmatch
import os
import shutil
from pathlib import Path
from typing import Dict, List

from tools.browser_lane_files import BROWSER_LANE_FILES, iter_test_files
from tools.full_test_debt_shards import PERF_FILE_PATTERNS

# 别把默认路径放回 /tmp：macOS 每日清理会把它掏空，浏览器车道就会以"运行时缺失"退出，
# 看起来像环境问题，其实是默认值指了个每天都会消失的位置。~/.cache 下那份是解压好的常驻副本，
# 和旁边的 chromium-mac-arm64-1041.zip 同源。
BROWSER_CACHE = Path.home() / ".cache/aps-chromium109-assessment"
DEFAULT_BROWSER_CANDIDATES = (
    BROWSER_CACHE / "stage/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
    Path("/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
)
BUNDLED_NODE = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node"


def default_browser() -> str:
    """取第一个真的在盘上的候选；都不在时返回常驻位置，让报错指向该去准备的地方。"""
    for candidate in DEFAULT_BROWSER_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    return str(DEFAULT_BROWSER_CANDIDATES[0])


def runtime_environment() -> Dict[str, str]:
    env = dict(os.environ)
    for key in ("FORCE_COLOR", "COLORTERM"):  # colourised pytest output breaks the summary parsing
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
    env["WORKBENCH_NODE"] = node
    env["WORKBENCH_BROWSER"] = browser
    node_path = [value for value in (env.get("NODE_PATH"), str(BUNDLED_NODE / "node_modules")) if value]
    env["NODE_PATH"] = os.pathsep.join(node_path)
    return env


def lane_targets() -> List[str]:
    perf_files = [path for path in iter_test_files() if any(fnmatch.fnmatch(path, pattern) for pattern in PERF_FILE_PATTERNS)]
    return sorted(set(BROWSER_LANE_FILES) | set(perf_files))
