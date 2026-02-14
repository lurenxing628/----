from __future__ import annotations

import os
import sys
from pathlib import Path


def runtime_base_dir(anchor_file: str | None = None) -> str:
    """
    获取运行根目录：
    - 源码运行：入口锚点文件所在目录（通常为仓库根目录 app.py 所在目录）
    - PyInstaller onedir：exe 所在目录
    """
    try:
        if getattr(sys, "frozen", False):
            return str(Path(sys.executable).resolve().parent)
        if anchor_file:
            return str(Path(anchor_file).resolve().parent)
        return str(Path.cwd().resolve())
    except Exception:
        if getattr(sys, "frozen", False):
            return os.path.abspath(os.path.dirname(sys.executable) or ".")
        if anchor_file:
            return os.path.abspath(os.path.dirname(anchor_file) or ".")
        return os.path.abspath(".")

