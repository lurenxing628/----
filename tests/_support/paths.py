"""测试套件统一的仓库根解析(与子目录深度无关)。

从本文件位置向上 walk 到含 `pyproject.toml` 的目录作为仓库根——不再依赖
`Path(__file__).parents[1]` / `os.path.join(__file__, "..")` 这类写死深度的解析。
P6 把测试迁入 `tests/<模块>/` 子目录后,文件深度会变,写死跳数会指向错目录;
本模块是唯一真相源:测试统一 import `REPO_ROOT`(Path)/`REPO_ROOT_STR`(str)/
`find_repo_root()`,在任意深度都解析到同一仓库根。
"""

from __future__ import annotations

from pathlib import Path


def _resolve_repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError(
        "仓库根定位失败:自 tests/_support/paths.py 向上未找到含 pyproject.toml 的目录"
    )


REPO_ROOT: Path = _resolve_repo_root()
REPO_ROOT_STR: str = str(REPO_ROOT)


def find_repo_root() -> Path:
    """返回仓库根(Path)。兼容历史内联 `find_repo_root()` 调用点。"""
    return REPO_ROOT
