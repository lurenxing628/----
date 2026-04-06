from __future__ import annotations

import os
import re
import sys
import tempfile
from typing import Any, Dict


def _find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _setup_runtime() -> None:
    tmpdir = tempfile.mkdtemp(prefix="aps_reg_batch_linkage_")
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = os.path.join(tmpdir, "aps.db")
    os.environ["APS_LOG_DIR"] = os.path.join(tmpdir, "logs")
    os.environ["APS_BACKUP_DIR"] = os.path.join(tmpdir, "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = os.path.join(tmpdir, "templates_excel")


def main() -> None:
    _setup_runtime()
    repo_root = _find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from flask import render_template

    from app import create_app

    app = create_app()

    ctx: Dict[str, Any] = dict(
        title="regression",
        ui_mode="v1",
        batch={
            "batch_id": "B_TEST",
            "part_no": "P1",
            "part_name": "",
            "quantity": 1,
            "due_date": None,
            "ready_date": None,
        },
        priority_zh="P",
        ready_status_zh="Y",
        batch_status_zh="S",
        operations=[
            {
                "id": 1,
                "op_code": "OP1",
                "seq": 1,
                "op_type_name": "OT",
                "source": "internal",
                "machine_id": "MISSING_MC",
                "operator_id": "MISSING_OP",
                "setup_hours": 0,
                "unit_hours": 0,
                "supplier_id": None,
                "ext_days": None,
                "merge_hint": None,
            }
        ],
        machine_options=[{"value": "MC1", "label": "MC1 Machine1", "disabled": False}],
        operator_options=[{"value": "OP1", "label": "OP1 Operator1", "disabled": False}],
        supplier_options=[],
        machine_operators={"MC1": ["OP1"]},
        operator_machines={"OP1": ["MC1"]},
        machine_operator_meta={"MC1": {"OP1": {"is_primary": "yes", "skill_level": "expert"}}},
        prefer_primary_skill="yes",
        lazy_select_enabled=True,
    )

    with app.test_request_context("/scheduler/batches/B_TEST?lazy_select=1"):
        html = render_template("scheduler/batch_detail.html", **ctx)
        ctx_null: Dict[str, Any] = dict(ctx)
        ctx_null["operator_machines"] = None
        html_null = render_template("scheduler/batch_detail.html", **ctx_null)

    # 模板契约：联动行、懒加载模板、回退占位项
    assert 'data-linkage-row="1"' in html, "缺少联动行标记"
    assert 'id="tplMachineOptions"' in html, "缺少设备懒加载模板"
    assert 'id="tplOperatorOptions"' in html, "缺少人员懒加载模板"
    assert "（已删除）" in html, "缺少已删除回退占位项"

    # 链接脚本注入契约
    assert 'id="batch-detail-linkage-data"' in html, "缺少 linkage JSON 注入节点"
    assert "window.__APS_BATCH_DETAIL_LINKAGE__" in html, "缺少 linkage 配置注入"
    assert "machineOperators" in html and "operatorMachines" in html, "缺少 linkage 双向映射注入"
    assert "lazySelectEnabled" in html, "缺少 lazySelectEnabled 注入"

    # 契约：允许 operatorMachines 为 null（由 machineOperators 反推）
    assert re.search(r'"operatorMachines"\s*:\s*null\b', html_null), "operatorMachines=None 时应以 JSON null 注入"

    # JS 契约：核心函数与关键分支存在（仅验证语义钩子）
    js_path = os.path.join(repo_root, "static", "js", "batch_detail_linkage.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    for needle in (
        "ensureSelectOptionsLoaded",
        "isSelectedOrphan",
        "setSelectOptionsByAllowed",
        "reorderOperatorOptionsByPreference",
        'dataset.orphan = "1"',
        'dataset.optionsLoaded = "1"',
        "optionsLoadFailed",
        "data-linkage-row",
        "cfg.operatorMachines || buildOperatorMachinesFromMachineOperators",
    ):
        assert needle in js, f"缺少关键联动逻辑片段: {needle}"

    # 关键提示文案约束（防回退）
    assert re.search(r"当前设备/人员组合不匹配", js), "缺少不匹配提示"
    assert re.search(r"已删除：请改选或清空", js), "缺少孤儿资源提示"

    print("OK")


if __name__ == "__main__":
    main()

