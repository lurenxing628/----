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
        operation_update_actions={"opform_1": "/scheduler/ops/update-token/TOKEN"},
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
    assert re.search(r'"operationUpdateActions"\s*:\s*\{[^}]*"opform_1"', html), "缺少工序更新地址映射"
    assert html.index("window.__APS_BATCH_DETAIL_LINKAGE__ = JSON.parse") < html.index("var actionByFormId"), (
        "工序保存脚本必须先解析 linkage JSON，再读取 operationUpdateActions"
    )

    # 契约：允许 operatorMachines 为 null（由 machineOperators 反推）
    assert re.search(r'"operatorMachines"\s*:\s*null\b', html_null), "operatorMachines=None 时应以 JSON null 注入"


def _placement_base_ctx() -> Dict[str, Any]:
    from web.viewmodels.strict_mode_toggles import build_strict_mode_toggle

    return dict(
        title="regression",
        batch={"batch_id": "B_TEST", "part_no": "P1", "part_name": "", "quantity": 1, "due_date": None, "ready_date": None},
        priority_zh="P", ready_status_zh="Y", batch_status_zh="S",
        operations=[],
        machine_options=[], operator_options=[], supplier_options=[],
        machine_operators={}, operator_machines={}, machine_operator_meta={},
        prefer_primary_skill="yes", lazy_select_enabled=False,
        batch_detail_strict_toggle=build_strict_mode_toggle("batchDetailGenerateOpsStrictMode", desc="x"),
    )


def test_batch_detail_schedule_placement_ok_renders_card(app_client) -> None:
    from flask import render_template

    app = app_client.application
    ctx = _placement_base_ctx()
    ctx["schedule_placement"] = {
        "state": "ok", "message": "",
        "version_label": "v8", "generated_at_label": "2026年6月1日 08:00",
        "strategy_label": "综合优先级和交期", "op_count": 1,
        "span_label": "2026年6月1日 08:00 ～ 2026年6月1日 12:00",
        "span_notice": "有 1 条排程记录的开始或结束时间缺失或写法不对，时间跨度只按可解析记录计算；已排工序数量仍是全量。",
        "gantt_link": {"label": "在甘特中定位本批次", "url": "/scheduler/gantt?gantt_batch=B_TEST&version=8", "disabled": False},
        "op_rows": [
            {
                "op_label": "OP10", "plan_machine_label": "M1 设备1", "plan_operator_label": "O1 人员1",
                "execution_status_label": "待开工", "actual_start_time_label": "暂无实际开工",
                "actual_end_time_label": "暂无实际完工", "actual_summary_label": "暂未记录现场实际",
                "has_execution_record": False,
            }
        ],
    }
    with app.test_request_context("/scheduler/batches/B_TEST"):
        html = render_template("scheduler/batch_detail.html", **ctx)

    assert "最新方案排程去向" in html
    assert "v8" in html and "1 道" in html
    assert "OP10" in html and "M1 设备1" in html
    assert "暂未记录现场实际" in html  # 无记录行单格诚实文案
    assert "时间跨度只按可解析记录计算" in html
    assert "在甘特中定位本批次" in html  # gantt_link 非 disabled 且有 url → 渲染按钮


def test_batch_detail_schedule_placement_disabled_link_and_empty_states(app_client) -> None:
    from flask import render_template

    app = app_client.application

    # gantt_link disabled → 不渲染定位按钮
    ctx_disabled = _placement_base_ctx()
    ctx_disabled["schedule_placement"] = {
        "state": "ok", "message": "", "version_label": "v8", "generated_at_label": "-",
        "strategy_label": "-", "op_count": 1, "span_label": "时间记录异常",
        "gantt_link": {"label": "在甘特中定位本批次", "url": "", "disabled": True},
        "op_rows": [{
            "op_label": "OP10", "plan_machine_label": "外协 鑫源机械", "plan_operator_label": "外协/未分配",
            "execution_status_label": "待开工", "actual_start_time_label": "暂无实际开工",
            "actual_end_time_label": "暂无实际完工", "actual_summary_label": "暂未记录现场实际",
            "has_execution_record": False,
        }],
    }
    # 未排入空态 → 诚实文案、无表格无按钮
    ctx_not_placed = _placement_base_ctx()
    ctx_not_placed["schedule_placement"] = {
        "state": "not_placed", "message": "本批次未排入最新方案",
        "version_label": "-", "generated_at_label": "-", "strategy_label": "-",
        "op_count": 0, "span_label": "-", "gantt_link": None, "op_rows": [],
    }

    with app.test_request_context("/scheduler/batches/B_TEST"):
        html_disabled = render_template("scheduler/batch_detail.html", **ctx_disabled)
        html_not_placed = render_template("scheduler/batch_detail.html", **ctx_not_placed)

    assert "最新方案排程去向" in html_disabled
    assert "外协 鑫源机械" in html_disabled  # 外协行单源 display 展示
    assert "在甘特中定位本批次" not in html_disabled  # disabled → 按钮不渲染

    assert "本批次未排入最新方案" in html_not_placed
    assert "在甘特中定位本批次" not in html_not_placed
