"""测试套件共享的 Excel 模板目录——一个目录，多用例复用。

历史上这里要 WARM 预建 11 个交付模板：create_app 启动时会调 ensure_excel_templates，
每个用例各建一个空目录就等于 COLD 重写 11 个模板（~174ms/次×数百次）。

2026-09 启动期模板生成整套退役后，create_app 只 makedirs 这个目录，不再往里写东西，
所以这里不再预建任何文件，只负责给出一个共享路径并把 APS_EXCEL_TEMPLATE_DIR 指过去。
需要独立目录的用例（如 test_app_factory_runtime_env_refresh）仍然保留各自私有目录。

fail loud：未发布就 point 即 raise——不静默兜底。
"""

from __future__ import annotations

import os

_shared_template_dir: str = ""


def publish_shared_dir(base_dir: str) -> str:
    """session fixture 调用：登记共享目录路径。"""
    global _shared_template_dir
    os.makedirs(str(base_dir), exist_ok=True)
    _shared_template_dir = str(base_dir)
    return _shared_template_dir


def reset_shared_dir() -> None:
    global _shared_template_dir
    _shared_template_dir = ""


def point_env_at_shared(monkeypatch) -> str:
    """把 APS_EXCEL_TEMPLATE_DIR 指向共享目录（monkeypatch 自动还原）。"""
    if not _shared_template_dir:
        raise RuntimeError("共享 Excel 模板目录尚未发布：缺 session 级 autouse fixture")
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", _shared_template_dir)
    return _shared_template_dir
