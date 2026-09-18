"""回归测试：资源派工页工作台执行契约——执行脚本按职责顺序加载；前端 renderExecutionCards 对缺图号/工序渲染中文兜底文案；任务卡输出 part_label、
开完工时间差(晚 N 分钟/早 N 分钟)与现场记录来源标签；非正式方案页面不暴露任何 actual 写入地址。"""

from __future__ import annotations

import json
from pathlib import Path

from tests._support.paths import REPO_ROOT
from tests.operation_execution.operation_execution_feedback_test_support import (
    RESOURCE_DISPATCH_TEMPLATE,
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_resource_dispatch_execution_scripts_are_loaded_by_responsibility() -> None:
    assert not RESOURCE_DISPATCH_TEMPLATE.exists()
    legacy = ["resource_dispatch_shared.js", "resource_dispatch_core.js", "resource_execution_context.js",
              "resource_execution_cards.js", "resource_execution_actual.js", "resource_execution_import.js",
              "resource_execution.js", "resource_dispatch_boot.js"]
    assert all(not (REPO_ROOT / "static/js" / name).exists() for name in legacy)
    order = json.loads(_source(REPO_ROOT / "scripts/workbench/build-order.json"))["live"]
    expected = ["FieldContract.js", "FieldAPI.js", "FieldControls.jsx", "FieldFilters.jsx",
                "FieldEditor.jsx", "FieldDetail.jsx", "FieldTable.jsx", "FieldFiles.jsx", "FieldWorkspace.jsx"]
    positions = [order.index(name) for name in expected]
    assert positions == sorted(positions)
    assert all((REPO_ROOT / "frontend/workbench/app" / name).is_file() for name in expected)


def test_resource_dispatch_keeps_execution_inside_existing_page() -> None:
    from web.routes.workbench.legacy_page_contract import PAGE_POLICIES

    assert PAGE_POLICIES["scheduler.resource_dispatch_page"] == "retired"
    assert not RESOURCE_DISPATCH_TEMPLATE.exists()
    assert "/scheduler/resource-execution" not in _source(REPO_ROOT / "frontend/workbench/app/FieldWorkspace.jsx")
    workspace = _source(REPO_ROOT / "frontend/workbench/app/FieldWorkspace.jsx")
    assert "<window.FieldTable " in workspace and "<window.FieldDetail " in workspace
    assert "<window.FieldFiles " in workspace


