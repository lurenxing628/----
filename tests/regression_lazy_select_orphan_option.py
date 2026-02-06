import os
import re
import sys
import tempfile


def _find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _setup_temp_runtime_env() -> str:
    tmpdir = tempfile.mkdtemp(prefix="aps_reg_lazy_select_orphan_")
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = os.path.join(tmpdir, "aps.db")
    os.environ["APS_LOG_DIR"] = os.path.join(tmpdir, "logs")
    os.environ["APS_BACKUP_DIR"] = os.path.join(tmpdir, "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = os.path.join(tmpdir, "templates_excel")
    return tmpdir


def main():
    _setup_temp_runtime_env()

    repo_root = _find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from app import create_app  # noqa: WPS433 (repo-local import)
    from flask import render_template

    app = create_app()

    missing_mc = "MISSING_MC"
    missing_op = "MISSING_OP"
    deleted_suffix = "\uff08\u5df2\u5220\u9664\uff09"  # （已删除）

    # 构造“问题场景”：
    # - 首屏 select 有回退 option（缺失 machine/operator）
    # - 懒加载模板 tplMachineOptions/tplOperatorOptions 不包含该回退项
    ctx = dict(
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
    )

    with app.test_request_context("/scheduler/batches/B_TEST?lazy_select=1"):
        html = render_template("scheduler/batch_detail.html", **ctx)

    # 1) 首屏 fallback option 必须存在且带 data-orphan + “已删除”
    exp_mc = (
        f'<option value="{missing_mc}" selected disabled data-static-disabled="1" data-orphan="1">'
        f"{missing_mc}{deleted_suffix}"
        "</option>"
    )
    exp_op = (
        f'<option value="{missing_op}" selected disabled data-static-disabled="1" data-orphan="1">'
        f"{missing_op}{deleted_suffix}"
        "</option>"
    )
    assert exp_mc in html, "首屏缺少 machine 回退 option（或属性不匹配）"
    assert exp_op in html, "首屏缺少 operator 回退 option（或属性不匹配）"
    assert 'data-linkage-row="1"' in html, "source 大小写不敏感回归：INTERNAL 应被识别为内部工序"

    # 2) 懒加载模板 options 不应包含缺失值（复现原问题条件）
    m = re.search(r'<template id="tplMachineOptions">([\s\S]*?)</template>', html)
    assert m, "缺少 tplMachineOptions"
    assert missing_mc not in m.group(1), "tplMachineOptions 不应包含缺失 machine_id（本用例要求）"

    m2 = re.search(r'<template id="tplOperatorOptions">([\s\S]*?)</template>', html)
    assert m2, "缺少 tplOperatorOptions"
    assert missing_op not in m2.group(1), "tplOperatorOptions 不应包含缺失 operator_id（本用例要求）"

    # 3) JS 必须包含“回插占位项 + 强制选中”的逻辑（防止首次交互静默丢值）
    assert "orphanOpt.selected = true" in html, "缺少 orphanOpt.selected 强制选中逻辑"
    assert 'dataset.orphan = "1"' in html or 'data-orphan"' in html, "缺少 data-orphan 标记逻辑"
    assert "_isSelectedOrphan" in html, "缺少 _isSelectedOrphan（孤儿/已删除选中项识别）逻辑"
    assert "optionsLoadFailed" in html or "data-options-load-failed" in html, "缺少 optionsLoadFailed（懒加载失败标记）逻辑"
    assert "dataset.lazy" in html, "缺少 data-lazy 保护条件逻辑"

    # 手工回归建议（更贴近真实浏览器行为）：
    # - 让某条内部工序 machine_id 或 operator_id 指向 DB 中已删除的资源（保留工序记录）。
    # - 打开批次详情页：GET /scheduler/batches/<batch_id>?lazy_select=1
    # - 首次点开设备/人员下拉：已删除项仍保持选中；另一侧下拉不应被“全禁用”；提示文案为“已删除”。

    print("OK")


if __name__ == "__main__":
    main()

