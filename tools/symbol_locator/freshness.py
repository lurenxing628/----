"""产物新鲜度:检测静态图快照是否落后于源码,必要时重建。

重建调既有 callgraph_extract.py(硬依赖 networkx,优先用 .venv 的 python 跑);
产物目录跟随 CHECKUP_CALLGRAPH(与 static_index、callgraph_extract 同源)。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Optional, Set, Tuple

from .static_index import FUNCTIONS_JSON, REPO_ROOT

_FIRST_PARTY = ("src", "core", "web", "data", "app", "tools", "scripts", "plugins", "desktop")
_EXCLUDE = {
    ".git", "__pycache__", ".venv", "venv", "node_modules", "vendor",
    "backups", "evidence", ".ruff_cache", ".pytest_cache", "dist", "build",
}
_EXTRACT = os.path.join(REPO_ROOT, ".codestable", "checkup", "scripts", "callgraph_extract.py")
_VENV_PY = os.path.join(REPO_ROOT, ".venv", "bin", "python")
_LAST_REBUILD_ERROR = None


def snapshot_mtime():
    # type: () -> Optional[float]
    if not os.path.exists(FUNCTIONS_JSON):
        return None
    return os.path.getmtime(FUNCTIONS_JSON)


def _scan_sources():
    # type: () -> Tuple[float, Set[str]]
    newest = 0.0
    current_files = set()  # type: Set[str]
    try:
        root_entries = os.listdir(REPO_ROOT)
    except OSError:
        root_entries = []
    for fn in root_entries:
        if not fn.endswith(".py"):
            continue
        fp = os.path.join(REPO_ROOT, fn)
        if not os.path.isfile(fp):
            continue
        try:
            mtime = os.path.getmtime(fp)
        except OSError:
            continue
        current_files.add(fn)
        if mtime > newest:
            newest = mtime
    for root in _FIRST_PARTY:
        base = os.path.join(REPO_ROOT, root)
        if not os.path.isdir(base):
            continue
        for current, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in _EXCLUDE]
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                fp = os.path.join(current, fn)
                try:
                    mtime = os.path.getmtime(fp)
                except OSError:
                    continue
                rel = os.path.relpath(fp, REPO_ROOT).replace("\\", "/")
                current_files.add(rel)
                if mtime > newest:
                    newest = mtime
    return newest, current_files


def is_stale():
    # type: () -> bool
    snap = snapshot_mtime()
    if snap is None:
        return True
    newest, current_files = _scan_sources()
    if newest > snap:
        return True
    try:
        with open(FUNCTIONS_JSON, encoding="utf-8") as fh:
            functions = json.load(fh)
    except (OSError, ValueError):
        return True
    if not isinstance(functions, dict):
        return True
    for info in functions.values():
        if not isinstance(info, dict) or info.get("rel") not in current_files:
            return True
    return False


def rebuild():
    # type: () -> bool
    """调 callgraph_extract 重建产物(继承 CHECKUP_CALLGRAPH);成功返回 True。"""
    global _LAST_REBUILD_ERROR
    _LAST_REBUILD_ERROR = None
    interpreter = _VENV_PY if os.path.exists(_VENV_PY) else sys.executable
    try:
        proc = subprocess.run(
            [interpreter, _EXTRACT], cwd=REPO_ROOT, env=dict(os.environ),
            capture_output=True, text=True)
    except OSError as exc:
        _LAST_REBUILD_ERROR = str(exc)
        return False
    if proc.returncode != 0:
        _LAST_REBUILD_ERROR = (proc.stderr or proc.stdout or "").strip()
        return False
    return True


def rebuild_error_hint():
    # type: () -> str
    """给 CLI 打印重建失败的可操作提示。"""
    if not _LAST_REBUILD_ERROR:
        return "重建静态图失败"
    lower = _LAST_REBUILD_ERROR.lower()
    if "networkx" in lower:
        return "重建静态图失败:缺少 networkx;请先修复仓库 .venv 里的 networkx 后重试。"
    first_line = _LAST_REBUILD_ERROR.splitlines()[0].strip()
    if first_line:
        return f"重建静态图失败:{first_line}"
    return "重建静态图失败"


def snapshot_label():
    # type: () -> str
    snap = snapshot_mtime()
    if snap is None:
        return "(无快照)"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(snap))
