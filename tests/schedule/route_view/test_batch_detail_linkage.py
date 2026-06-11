"""回归测试：批次详情页 batch_detail.html 渲染时注入设备/人员联动契约——data-linkage-row 标记、懒加载模板节点、已删除资源回退占位项、window.__APS_BATCH_DETAIL_LINKAGE__ 双向映射（operatorMachines=None 时以 JSON null 注入由 machineOperators 反推）。"""

from __future__ import annotations

import re
from typing import Any, Dict


def test_batch_detail_linkage(app_client) -> None:
    from flask import render_template

    from web.viewmodels.strict_mode_toggles import build_strict_mode_toggle

    app = app_client.application

    ctx: Dict[str, Any] = dict(
        title="regression",
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
        batch_detail_strict_toggle=build_strict_mode_toggle(
            "batchDetailGenerateOpsStrictMode",
            desc="工序资料不完整时先停下，避免把缺资料的批次继续生成下去。",
        ),
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
