"""测试套件共享的 Excel 模板目录——一次预建、多用例只读复用。

许多 web/app 用例的本地 helper 各自 `tmp_path/"templates_excel"` 建空目录并
`setenv APS_EXCEL_TEMPLATE_DIR`，使 create_app→ensure_excel_templates 每个用例都
COLD 重写 11 个模板（~174ms/次×数百次）。本模块在 session 起始把 11 个交付模板
预建到一个共享目录（WARM），用例改用 `point_env_at_shared(monkeypatch)` 指向它，
省掉每用例的 COLD 重建。

只读复用：共享目录由 session fixture 一次性建好后不再被任何用例改写；需要 unlink/
改写模板或按设计要独立目录的用例（如 test_team_pages_excel_smoke、
test_app_factory_runtime_env_refresh、直接调 ensure_excel_templates 的刷新行为测试）
保留各自私有目录，不走本模块。

fail loud：预建不全 11 个模板即 raise；未发布就 point 即 raise——不静默兜底。
"""

from __future__ import annotations

import os

from core.services.common.excel_template_defaults import get_default_templates
from core.services.common.excel_templates import ensure_excel_templates

_EXPECTED_TEMPLATE_COUNT = len(get_default_templates())
_shared_template_dir: str = ""


def build_shared_template_dir(base_dir: str) -> str:
    """把全部交付模板 WARM 预建到 base_dir，建不全 11 个即 fail loud。"""
    stats = ensure_excel_templates(str(base_dir))
    template_dir = str(stats["template_dir"])
    built = sum(1 for entry in os.scandir(template_dir) if entry.name.endswith(".xlsx"))
    if built < _EXPECTED_TEMPLATE_COUNT:
        raise RuntimeError(
            f"共享 Excel 模板预建不完整：{built} < {_EXPECTED_TEMPLATE_COUNT} 个 @ {template_dir}"
        )
    return template_dir


def publish_shared_dir(base_dir: str) -> str:
    """session fixture 调用：预建并登记共享目录路径。"""
    global _shared_template_dir
    _shared_template_dir = build_shared_template_dir(base_dir)
    return _shared_template_dir


def reset_shared_dir() -> None:
    global _shared_template_dir
    _shared_template_dir = ""


def point_env_at_shared(monkeypatch) -> str:
    """把 APS_EXCEL_TEMPLATE_DIR 指向共享 WARM 目录（monkeypatch 自动还原）。"""
    if not _shared_template_dir:
        raise RuntimeError("共享 Excel 模板目录尚未发布：缺 session 级 autouse fixture")
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", _shared_template_dir)
    return _shared_template_dir
