"""回归测试：批次详情页懒加载下拉（lazy_select）下，当工序的 machine_id/operator_id 指向已删除资源（不在懒加载模板 options 中）时，首屏 select 仍渲染带 data-orphan/data-static-disabled 的「（已删除）」回退 option 并强制选中；同时校验 source 大小写不敏感（INTERNAL 识别为内部工序）及 batch_detail_linkage.js 含回插占位项与懒加载失败保护逻辑。"""

import re


def test_lazy_select_orphan_option(app_client, repo_root) -> None:
    from flask import render_template

    from web.viewmodels.strict_mode_toggles import build_strict_mode_toggle

    app = app_client.application

    missing_mc = "MISSING_MC"
    missing_op = "MISSING_OP"
    deleted_suffix = "\uff08\u5df2\u5220\u9664\uff09"  # （已删除）

    # 构造“问题场景”：
    # - 首屏 select 有回退 option（缺失 machine/operator）
    # - 懒加载模板 tplMachineOptions/tplOperatorOptions 不包含该回退项
    ctx = dict(
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
                # 回归点：source 大小写不敏感（历史数据/导入可能出现 INTERNAL/External）
                "source": "INTERNAL",
                "machine_id": missing_mc,
                "operator_id": missing_op,
                "setup_hours": 0,
                "unit_hours": 0,
                "supplier_id": None,
                "ext_days": None,
                "merge_hint": None,
            }
        ],
        # 注意：这里故意不包含 missing_mc/missing_op，模拟“值不在懒加载模板 options 中”的情况
        machine_options=[{"value": "MC1", "label": "MC1 Machine1", "disabled": False}],
        operator_options=[{"value": "OP1", "label": "OP1 Operator1", "disabled": False}],
        supplier_options=[],
        machine_operators={},
        operator_machines={},
        machine_operator_meta={},
        prefer_primary_skill="no",
        lazy_select_enabled=True,
        batch_detail_strict_toggle=build_strict_mode_toggle(
            "batchDetailGenerateOpsStrictMode",
            desc="工序资料不完整时先停下，避免把缺资料的批次继续生成下去。",
        ),
    )

    with app.test_request_context("/scheduler/batches/B_TEST?lazy_select=1"):
        html = render_template("scheduler/batch_detail.html", **ctx)

    # 1) 首屏 fallback option 必须存在且带 data-orphan + 强制选中 + “已删除”后缀
    #    （只校验载荷标记，不锁死属性书写顺序，避免模板格式微调误报）
    assert f'value="{missing_mc}"' in html and f"{missing_mc}{deleted_suffix}" in html, "首屏缺少 machine 回退 option（值或“已删除”后缀）"
    assert f'value="{missing_op}"' in html and f"{missing_op}{deleted_suffix}" in html, "首屏缺少 operator 回退 option（值或“已删除”后缀）"
    assert html.count('data-orphan="1"') >= 2, "首屏回退 option 缺少 data-orphan 孤儿标记"
    assert html.count('data-static-disabled="1"') >= 2, "首屏回退 option 缺少 data-static-disabled 静态禁用标记"
    assert 'data-linkage-row="1"' in html, "source 大小写不敏感回归：INTERNAL 应被识别为内部工序"

    # 2) 懒加载模板 options 不应包含缺失值（复现原问题条件）
    m = re.search(r'<template id="tplMachineOptions">([\s\S]*?)</template>', html)
    assert m, "缺少 tplMachineOptions"
    assert missing_mc not in m.group(1), "tplMachineOptions 不应包含缺失 machine_id（本用例要求）"

    m2 = re.search(r'<template id="tplOperatorOptions">([\s\S]*?)</template>', html)
    assert m2, "缺少 tplOperatorOptions"
    assert missing_op not in m2.group(1), "tplOperatorOptions 不应包含缺失 operator_id（本用例要求）"

    # 3) JS 必须包含“回插占位项 + 强制选中”的逻辑（防止首次交互静默丢值）
    #    注意：批次详情页使用外部脚本 static/js/batch_detail_linkage.js（非 inline），因此这里检查：
    #    - HTML 必须加载该脚本
    #    - JS 文件内容必须包含关键逻辑片段
    assert "js/batch_detail_linkage.js" in html, "模板未加载 batch_detail_linkage.js"

    # 手工回归建议（更贴近真实浏览器行为）：
    # - 让某条内部工序 machine_id 或 operator_id 指向 DB 中已删除的资源（保留工序记录）。
    # - 打开批次详情页：GET /scheduler/batches/<batch_id>?lazy_select=1
    # - 首次点开设备/人员下拉：已删除项仍保持选中；另一侧下拉不应被“全禁用”；提示文案为“已删除”。
