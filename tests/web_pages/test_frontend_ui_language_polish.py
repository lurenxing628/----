"""回归测试：前端模板、JS、手册与服务层的面向用户文案必须是规范中文，不得泄露内部术语——校验排产配置/批次/运行面板提示、甘特图与日志展示字段用中文 label、Excel 预览用 display_data、错误文案中文优先而英文仅作兼容别名，并守护若干已知乱码错误消息已被修复。"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Tuple

import openpyxl
import pytest

from tests._support.paths import REPO_ROOT
from tests._support.workbench_browser_contract import browser_contract


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _read_analysis_template() -> str:
    """Read current analysis presenters; do not restore removed templates."""
    return "\n".join(_read(path) for path in (
        "frontend/workbench/app/PlanCatalogUI.jsx", "frontend/workbench/app/PlanDetailsUI.jsx",
        "frontend/workbench/app/RunHistoryControls.jsx", "frontend/workbench/app/RunCandidateControls.jsx",
        "frontend/workbench/app/RunCandidateAnalysis.jsx",
    ))


def test_scheduler_config_and_batch_hints_are_user_facing_chinese() -> None:
    browser_contract("""
const value = {type:'work',hours:'8',eff:'100',allowNormal:'yes',allowUrgent:'no',note:''};
expect(window.APSCalendarContract.input(value).eff === 100);
for (const eff of ['', '0', '-1', 'bad', '201']) {
  let message = '';
  try { window.APSCalendarContract.input({...value,eff}); } catch(error) { message = error.message; }
  expect(message === '效率须大于 0 且不超过 200%。', 'Bad efficiency was accepted or leaked an internal field name');
}
const node = await render(React.createElement(window.PreflightControls.Rules,
  {value:{ready_check:true,missing_resource_policy:'auto_assign'},onChange:()=>{},disabled:false}));
expect(node.textContent.includes('缺资源工序'));
expect(node.textContent.includes('自动分配') && node.textContent.includes('暂不排'));
expect(node.textContent.includes('已开工工序：保留记录（不可修改）'));
expect(!node.textContent.includes('missing_resource_policy') && !node.textContent.includes('strict_mode'));
return true;
""", scripts=("static/workbench/app/resource-contract.js", "static/workbench/app/ResourceControls.js",
              "static/workbench/app/CalendarContract.js", "static/workbench/app/PreflightControls.js"))
    batch = _read("frontend/workbench/app/BatchDetail.jsx")
    assert "刷新详情" in batch
    assert "B.label('status', entity.status)" in batch
    assert "解析器不支持 strict_mode" not in batch
    calendar = _read("frontend/workbench/app/CalendarFields.jsx")
    assert "效率（%）" in calendar and "可排工时（小时）" in calendar
    assert "假期安排生产但未单独设置效率时" not in calendar


def test_scheduler_run_copy_avoids_vague_vocabulary_for_operators() -> None:
    forbidden_terms = ("配置不合法", "安全取值", "工时空着时可能", "可能按 0 小时", "当前配置无效",
                       "配置无效", "格式不合法", "时间不合法", "外协周期缺失或不合法")
    for path in (
        "frontend/workbench/app/PreflightControls.jsx", "frontend/workbench/app/RunJobControls.jsx",
        "frontend/workbench/app/PlanGantt.jsx", "frontend/workbench/app/PlanWorkspace.jsx",
        "web/viewmodels/scheduler_run_options.py", "web/viewmodels/page_manuals_scheduler.py",
        "web/viewmodels/page_manuals_scheduler_week_plan.py", "web/viewmodels/scheduler_degradation_presenter.py",
        "core/services/scheduler/summary/schedule_summary_degradation.py", "static/docs/scheduler_manual.md",
    ):
        source = _read(path)
        for term in forbidden_terms:
            assert term not in source, (path, term)


def test_scheduler_config_repair_notices_use_public_field_labels() -> None:
    source = _read("frontend/workbench/app/SystemMaintenanceConfig.jsx")
    assert "base.dirty_reasons[field.key]" in source
    assert "{field.label}" in source and "base.stored_values[field.key]" in source
    assert "notice.fields" not in source

    panel_vm = _read("web/viewmodels/scheduler_config_panel.py")
    assert 'raw_notice.get("field_labels")' in panel_vm
    assert "detail_items = tuple" in panel_vm
    assert 'raw_notice.get("fields")' not in panel_vm

    config_outcome = _read("core/services/scheduler/config/config_page_outcome.py")
    assert '"field_labels"' in config_outcome
    assert "public_config_field_labels" in config_outcome

    active_preset_service = _read("core/services/scheduler/config/active_preset_service.py")
    assert "当前启用排产配置模板的结构化来源记录" in active_preset_service
    assert "褰撳墠" not in active_preset_service


def test_scheduler_analysis_gantt_and_logs_do_not_surface_internal_terms() -> None:
    import logging
    import re
    import sqlite3
    import tempfile

    from core.services.workbench.system_reads import log_records

    analysis = _read_analysis_template()
    for label in ("齐套检查", "缺设备人员时的规则", "任务详情", "前序", "后序", "计划开始", "计划结束"):
        assert label in analysis
    for term in ("attempts / 优化曲线 / 超期明细", 'data-col-key="score"', "r.dispatch_mode }}/{{ r.dispatch_rule"):
        assert term not in analysis
    logs = _read("frontend/workbench/app/SystemMaintenanceRecords.jsx")
    assert "日志详情" in logs and "操作记录" in logs and "{row.summary}" in logs
    assert "{row.module}" not in logs and "{row.action}" not in logs
    # Operation summaries retain the public vocabulary of the existing log view.
    with tempfile.TemporaryDirectory(prefix="aps-A-log-label-") as directory:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript(_read("schema.sql"))
            conn.execute("INSERT INTO OperationLogs(log_level,module,action,detail) VALUES ('INFO','scheduler','schedule','{}')")
            conn.commit()
            before = list(conn.iterdump())
            rows, sources = log_records(conn, directory, logging.getLogger("A-log-label-contract"))
            operation = [row for row in rows if row["type"] == "operation"]
            assert len(operation) == 1 and sources
            assert list(conn.iterdump()) == before
            summary = operation[0]["summary"]
            assert re.findall(r"[\u4e00-\u9fff]+", summary) == ["排产管理", "排产"], operation[0]
            assert "scheduler" not in summary and "schedule" not in summary
        finally:
            conn.close()


def test_debug_details_do_not_expose_flask_endpoint_names_to_users() -> None:
    for path in ("frontend/workbench/app/main.jsx", "frontend/workbench/app/ResourceForms.jsx",
                 "frontend/workbench/app/BatchForms.jsx", "frontend/workbench/app/SystemMaintenanceConfig.jsx",
                 "frontend/workbench/app/PlanWorkspace.jsx", "templates/workbench/legacy_result.html"):
        source = _read(path)
        for term in ("后端接口未注册（endpoint", "endpoint）", "missing_preset_endpoints|join"):
            assert term not in source


def test_process_excel_current_tables_render_chinese_display_fields() -> None:
    from types import SimpleNamespace

    from web.routes.workbench.legacy_presentation import preview_fields

    cases = (
        ("personnel.excel_operator_preview", {"状态": "在岗"}, {"状态": "active"}),
        ("equipment.excel_machine_preview", {"状态": "停机"}, {"状态": "inactive"}),
        ("scheduler.excel_batches_preview", {"优先级": "急件", "齐套": "部分齐套"}, {"优先级": "urgent", "齐套": "partial"}),
        ("scheduler.excel_calendar_preview", {"类型": "工作日", "允许普通件": "是", "允许急件": "否"}, {"类型": "workday"}),
        ("personnel.excel_operator_calendar_preview", {"类型": "休息日", "允许普通件": "否", "允许急件": "是"}, {"类型": "holiday"}),
        ("process.excel_op_type_preview", {"归属": "自制"}, {"归属": "internal"}),
        ("process.excel_part_op_hours_preview", {"图号": "P1", "工序": "10", "单件工时(h)": "0.25"},
         {"图号": "P1", "工序": 10, "单件工时(h)": 0.25, "归属": "external"}),
        ("process.excel_supplier_preview", {"状态": "启用", "备注": "原备注"}, {"状态": "active", "备注": "原备注"}),
    )
    for endpoint, public, raw in cases:
        original = dict(raw)
        row = SimpleNamespace(data=raw, display_data={**public, "op_id": "private-operation"},
                              display_changes={}, changes={})
        fields = preview_fields(row, endpoint)
        projected = {field["label"]: field["value"] for field in fields}
        assert projected == public, (endpoint, projected)
        assert row.data == original
        assert "op_id" not in projected and "private-operation" not in str(projected)
    template = _read("templates/workbench/legacy_result.html")
    assert "row|legacy_preview_fields(request.endpoint)" in template
    assert "{{ field.label }}" in template and "{{ field.value }}" in template
    assert "{{ field.before }}" in template and "{{ field.after }}" in template
    assert "r.data | tojson_zh" not in template
    detail = _read("frontend/workbench/app/ProcessDetail.jsx")
    assert "P = window.APSProcessContract" in detail and "P.sourceLabel(row.source)" in detail
    browser_contract("""
expect(window.APSProcessContract.sourceLabel('internal') === '自制');
expect(window.APSProcessContract.sourceLabel('external') === '外协');
expect(window.APSProcessContract.sourceLabel('unknown') === '未归类');
return true;
""", scripts=("static/workbench/app/resource-contract.js", "static/workbench/app/ProcessContract.js"))
    batch_route = _read("web/routes/domains/scheduler/scheduler_excel_batches.py")
    assert "encode_preview_rows_payload" in batch_route

    operator_route = _read("web/routes/personnel_excel_operators.py")
    assert '"状态显示": operator_status_label' in operator_route

    machine_route = _read("web/routes/equipment_excel_machines.py")
    assert '"状态显示": machine_status_label' in machine_route

    assert '"优先级显示": batch_priority_label' in batch_route
    assert '"齐套显示": ready_status_label' in batch_route

    calendar_route = _read("web/routes/domains/scheduler/scheduler_excel_calendar.py")
    assert '"类型显示": calendar_day_type_label' in calendar_route
    assert '"允许普通件显示": yes_no_label' in calendar_route
    assert '"允许急件显示": yes_no_label' in calendar_route

    operator_calendar_route = _read("web/routes/personnel_excel_operator_calendar.py")
    assert '"类型显示": calendar_day_type_label' in operator_calendar_route
    assert '"允许普通件显示": yes_no_label' in operator_calendar_route
    assert '"允许急件显示": yes_no_label' in operator_calendar_route

    op_type_service = _read("core/services/process/op_type_service.py")
    assert '"归属显示": source_type_label(ot.category)' in op_type_service

    supplier_service = _read("core/services/process/supplier_service.py")
    assert '"状态显示": supplier_status_label(s.status)' in supplier_service

    part_operation_hours_route = _read("web/routes/process_excel_part_operation_hours.py")
    assert '"归属显示": source_type_label(source)' in part_operation_hours_route

    operator_machine_route = _read("web/routes/personnel_excel_links.py")
    assert "project_preview_rows_for_display" in operator_machine_route
    assert '"技能等级": skill_level_label' in operator_machine_route
    assert '"主操设备": yes_no_label' in operator_machine_route

    operator_machine_service = _read("core/services/personnel/operator_machine_service.py")
    assert "主操设备=yes" not in operator_machine_service
    # “同一人员只能有一条主操设备填是”的文案随主操唯一性强制逻辑抽到了 import 辅助模块
    operator_machine_import_helpers = _read("core/services/personnel/operator_machine_import_helpers.py")
    assert "主操设备填“是”" in operator_machine_import_helpers


def test_manuals_keep_backend_supported_english_aliases_but_mark_them_as_compatible() -> None:
    from core.models.enums import (
        BatchPriority,
        CalendarDayType,
        MachineStatus,
        OperatorStatus,
        ReadyStatus,
        SourceType,
        SupplierStatus,
        YesNo,
    )
    from core.services.common.enum_normalizers import (
        normalize_machine_status,
        normalize_op_type_category,
        normalize_operator_status,
        normalize_skill_level,
        normalize_supplier_status,
        normalize_yesno_narrow,
    )
    from core.services.common.normalization_matrix import (
        normalize_batch_priority_value,
        normalize_calendar_day_type_value,
        normalize_ready_status_value,
    )

    process_manuals = "\n".join(
        (
            _read("web/viewmodels/page_manuals_process.py"),
            _read("web/viewmodels/page_manuals_process_excel.py"),
        )
    )
    scheduler_manuals = "\n".join(
        (
            _read("web/viewmodels/page_manuals_scheduler.py"),
            _read("web/viewmodels/page_manuals_scheduler_admin.py"),
            _read("web/viewmodels/page_manuals_scheduler_outputs.py"),
            _read("web/viewmodels/page_manuals_scheduler_week_plan.py"),
        )
    )
    personnel_manuals = "\n".join(
        (
            _read("web/viewmodels/page_manuals_personnel.py"),
            _read("web/viewmodels/page_manuals_personnel_excel.py"),
        )
    )
    equipment_manuals = "\n".join(
        (
            _read("web/viewmodels/page_manuals_equipment.py"),
            _read("web/viewmodels/page_manuals_equipment_excel.py"),
        )
    )
    full_manual = _read("static/docs/scheduler_manual.md")
    manual_sources = "\n".join((process_manuals, scheduler_manuals, personnel_manuals, equipment_manuals, full_manual))

    assert "以前文件里写过 新手 / 一般 / 中级 / 高级 / 专家 的，系统会尽量读懂" in personnel_manuals
    assert "以前文件里写过 1/0 的，系统会尽量读懂" in scheduler_manuals
    assert "类型模板下拉推荐填：工作日 / 假期" in scheduler_manuals
    assert "新表按下拉推荐写" in scheduler_manuals
    assert "状态模板下拉优先选：在岗 / 停用" in personnel_manuals
    assert "新文件请填中文" in full_manual
    assert "归属可填：自制 / 外协。新文件请只填这两个中文选项" in process_manuals
    assert "兼容英文标准值" not in manual_sources
    assert "internal` / `external" not in manual_sources
    assert "`internal`" not in full_manual
    assert "`external`" not in full_manual
    assert "`locked`" not in full_manual
    assert "`unlocked`" not in full_manual
    assert "兼容英文标准值 `internal`/`external`" not in manual_sources

    assert normalize_operator_status("active") == OperatorStatus.ACTIVE.value
    assert normalize_operator_status("inactive") == OperatorStatus.INACTIVE.value
    assert normalize_machine_status("maintain") == MachineStatus.MAINTAIN.value
    assert normalize_supplier_status("active") == SupplierStatus.ACTIVE.value
    assert normalize_supplier_status("inactive") == SupplierStatus.INACTIVE.value
    assert normalize_op_type_category("internal") == SourceType.INTERNAL.value
    assert normalize_op_type_category("external") == SourceType.EXTERNAL.value
    assert normalize_skill_level("beginner") == "beginner"
    assert normalize_skill_level("normal") == "normal"
    assert normalize_skill_level("expert") == "expert"
    assert normalize_yesno_narrow("yes") == YesNo.YES.value
    assert normalize_yesno_narrow("no") == YesNo.NO.value
    from core.services.personnel.operator_machine_normalizers import normalize_yes_no_optional

    assert normalize_yes_no_optional("true", field="主操设备") == YesNo.YES.value
    assert normalize_yes_no_optional("false", field="主操设备") == YesNo.NO.value
    assert normalize_yes_no_optional("on", field="主操设备") == YesNo.YES.value
    assert normalize_yes_no_optional("off", field="主操设备") == YesNo.NO.value
    assert normalize_batch_priority_value("urgent") == BatchPriority.URGENT.value
    assert normalize_batch_priority_value("critical") == BatchPriority.CRITICAL.value
    assert normalize_ready_status_value("partial") == ReadyStatus.PARTIAL.value
    assert normalize_calendar_day_type_value("workday") == CalendarDayType.WORKDAY.value
    assert normalize_calendar_day_type_value("holiday") == CalendarDayType.HOLIDAY.value
    assert normalize_calendar_day_type_value("weekend") == CalendarDayType.HOLIDAY.value

    static_manual = _read("static/docs/scheduler_manual.md")
    assert "发现问题就停下" in static_manual
    assert "缺工种、缺供应商或外协周期不正确" in static_manual
    assert "route_raw 自动补建模板" not in static_manual
    assert "未指定设备或人员时，系统自动分配" in static_manual
    assert "智能派工规则" in static_manual
    assert "dispatch_mode / dispatch_rule / auto_assign_enabled" not in static_manual


def test_supplier_manual_matches_required_default_days_and_template_columns() -> None:
    manual_sources = "\n".join(
        _read(rel_path)
        for rel_path in (
            "web/viewmodels/page_manuals_process.py",
            "web/viewmodels/page_manuals_process_excel.py",
            "static/docs/scheduler_manual.md",
        )
    )
    assert "默认周期必须填写大于 0 的有限数字(天)" in manual_sources
    assert "`默认周期` 必填，必须是大于 0 的有限数字" in manual_sources
    assert "下载的模板包含“状态”和“备注”两列" in manual_sources
    assert "模板只有4列" not in manual_sources
    assert "不填默认1天" not in manual_sources
    assert "不填默认 1 天" not in manual_sources
    assert "留空默认 1 天" not in manual_sources
    assert "周期默认1天" not in manual_sources


def test_material_status_and_delete_messages_match_user_page_labels() -> None:
    material_page = _read("web/viewmodels/page_manuals_material.py")
    material_route = _read("web/routes/material.py")
    material_service = _read("core/services/material/material_service.py")

    assert "状态为可用" in material_page
    assert "删除可能失败；这时先去处理引用它的批次物料需求" in material_page
    assert "请先处理关联需求后再试" in material_route
    delete_block = material_route.split("def materials_delete", 1)[-1].split("# ============================================================", 1)[0]
    assert "请稍后重试" not in delete_block
    assert "请选择：可用 / 停用" in material_service
    assert "请选择：启用 / 停用" not in material_service


def test_excel_templates_default_to_chinese_enum_values_accepted_by_backend() -> None:
    from core.models.enums import (
        BatchPriority,
        CalendarDayType,
        MachineStatus,
        OperatorStatus,
        ReadyStatus,
        SourceType,
        SupplierStatus,
        YesNo,
    )
    from core.services.common.enum_normalizers import (
        normalize_machine_status,
        normalize_op_type_category,
        normalize_operator_status,
        normalize_skill_level,
        normalize_supplier_status,
        normalize_yesno_narrow,
    )
    from core.services.common.excel_templates import get_default_templates
    from core.services.common.normalization_matrix import (
        normalize_batch_priority_value,
        normalize_calendar_day_type_value,
        normalize_ready_status_value,
    )

    raw_enum_values = {
        "active",
        "inactive",
        "maintain",
        "internal",
        "external",
        "beginner",
        "normal",
        "expert",
        "urgent",
        "critical",
        "partial",
        "workday",
        "holiday",
        "yes",
        "no",
    }
    normalizers = {
        ("人员基本信息.xlsx", "状态"): (normalize_operator_status, {OperatorStatus.ACTIVE.value, OperatorStatus.INACTIVE.value}),
        ("设备信息.xlsx", "状态"): (normalize_machine_status, set(MachineStatus._value2member_map_)),
        ("工种配置.xlsx", "归属"): (normalize_op_type_category, set(SourceType._value2member_map_)),
        ("供应商配置.xlsx", "状态"): (normalize_supplier_status, set(SupplierStatus._value2member_map_)),
        ("人员设备关联.xlsx", "技能等级"): (lambda value: normalize_skill_level(value, default="normal"), {"beginner", "normal", "expert"}),
        ("设备人员关联.xlsx", "技能等级"): (lambda value: normalize_skill_level(value, default="normal"), {"beginner", "normal", "expert"}),
        ("人员设备关联.xlsx", "主操设备"): (normalize_yesno_narrow, set(YesNo._value2member_map_)),
        ("设备人员关联.xlsx", "主操设备"): (normalize_yesno_narrow, set(YesNo._value2member_map_)),
        ("批次信息.xlsx", "优先级"): (normalize_batch_priority_value, set(BatchPriority._value2member_map_)),
        ("批次信息.xlsx", "齐套"): (normalize_ready_status_value, set(ReadyStatus._value2member_map_)),
        ("工作日历.xlsx", "类型"): (normalize_calendar_day_type_value, {CalendarDayType.WORKDAY.value, CalendarDayType.HOLIDAY.value}),
        ("人员专属工作日历.xlsx", "类型"): (
            normalize_calendar_day_type_value,
            {CalendarDayType.WORKDAY.value, CalendarDayType.HOLIDAY.value},
        ),
        ("工作日历.xlsx", "允许普通件"): (normalize_yesno_narrow, set(YesNo._value2member_map_)),
        ("工作日历.xlsx", "允许急件"): (normalize_yesno_narrow, set(YesNo._value2member_map_)),
        ("人员专属工作日历.xlsx", "允许普通件"): (normalize_yesno_narrow, set(YesNo._value2member_map_)),
        ("人员专属工作日历.xlsx", "允许急件"): (normalize_yesno_narrow, set(YesNo._value2member_map_)),
    }

    for template_def in get_default_templates():
        filename = str(template_def["filename"])
        headers = list(template_def["headers"])
        enum_cols = template_def.get("format_spec", {}).get("enum_cols", {}) or {}
        sample_rows = list(template_def.get("sample_rows") or [])
        enum_cells = []
        for row in sample_rows:
            for col_idx, cell in enumerate(row):
                if col_idx in enum_cols and isinstance(cell, str):
                    enum_cells.append(cell)
        enum_values = enum_cells + [str(value) for values in enum_cols.values() for value in values]
        assert not (set(enum_values) & raw_enum_values), f"{filename} 模板默认值不应继续使用英文枚举"

        for col_idx, values in enum_cols.items():
            header = str(headers[col_idx])
            key = (filename, header)
            assert key in normalizers, f"{filename} 的枚举列 {header} 缺少后端归一化测试"
            normalize, allowed = normalizers[key]
            for value in values:
                assert normalize(value) in allowed, f"{filename}.{header} 的模板值 {value!r} 后端不接受"


def test_ensure_excel_templates_refreshes_known_stale_generated_template(tmp_path) -> None:
    from core.services.common.excel_templates import ExcelTemplateError, build_xlsx_bytes, ensure_excel_templates

    stale_path = tmp_path / "人员基本信息.xlsx"
    stale_bytes = build_xlsx_bytes(
        ["工号", "姓名", "状态", "班组", "备注"],
        [["OP001", "张三", "active", None, "旧模板"]],
        format_spec={"enum_cols": {2: ["active", "inactive"]}},
    ).getvalue()
    stale_path.write_bytes(
        stale_bytes
    )

    with pytest.raises(ExcelTemplateError) as exc_info:
        ensure_excel_templates(str(tmp_path))
    assert "不能安全自动覆盖" in str(exc_info.value)
    assert stale_path.read_bytes() == stale_bytes

    workbook = None
    try:
        workbook = openpyxl.load_workbook(filename=stale_path, data_only=True)
        ws = workbook.active
        assert ws["C2"].value == "active"
    finally:
        if workbook is not None:
            workbook.close()


def test_ensure_excel_templates_refreshes_known_legacy_id_headers(tmp_path) -> None:
    from core.services.common.excel_templates import build_xlsx_bytes, ensure_excel_templates

    op_type_path = tmp_path / "工种配置.xlsx"
    op_type_path.write_bytes(
        build_xlsx_bytes(
            ["工种ID", "工种名称", "归属"],
            [["OT001", "数车", "自制"]],
            format_spec={"text_cols": [0, 1], "enum_cols": {2: ["自制", "外协"]}},
        ).getvalue()
    )
    supplier_path = tmp_path / "供应商配置.xlsx"
    supplier_path.write_bytes(
        build_xlsx_bytes(
            ["供应商ID", "名称", "对应工种", "默认周期", "状态", "备注"],
            [["S001", "外协-标印厂", "标印", 1, "启用", "保留数据"]],
            format_spec={"text_cols": [0, 1, 2, 4, 5], "float_cols": [3], "enum_cols": {4: ["启用", "停用"]}},
        ).getvalue()
    )

    stats = ensure_excel_templates(str(tmp_path))

    assert "工种配置.xlsx" in stats["created"]
    assert "供应商配置.xlsx" in stats["created"]
    workbook = None
    try:
        workbook = openpyxl.load_workbook(filename=op_type_path, data_only=True)
        ws = workbook.active
        assert [ws.cell(1, col).value for col in range(1, 4)] == ["工种编号", "工种名称", "归属"]
        assert [ws.cell(2, col).value for col in range(1, 4)] == ["OT001", "数车", "自制"]
    finally:
        if workbook is not None:
            workbook.close()

    workbook = None
    try:
        workbook = openpyxl.load_workbook(filename=supplier_path, data_only=True)
        ws = workbook.active
        assert [ws.cell(1, col).value for col in range(1, 7)] == ["供应商编号", "名称", "对应工种", "默认周期", "状态", "备注"]
        assert [ws.cell(2, col).value for col in range(1, 7)] == ["S001", "外协-标印厂", "标印", 1, "启用", "保留数据"]
    finally:
        if workbook is not None:
            workbook.close()


def test_template_download_preserves_existing_disk_file_when_headers_match(tmp_path) -> None:
    from flask import Flask

    from core.services.common.excel_templates import build_xlsx_bytes
    from web.routes.excel_utils import send_excel_template_file

    custom_path = tmp_path / "人员基本信息.xlsx"
    custom_path.write_bytes(
        build_xlsx_bytes(
            ["工号", "姓名", "状态", "班组", "备注"],
            [["OP999", "自定义示例", "active", "A组", "保留用户模板"]],
            format_spec={"enum_cols": {2: ["active", "inactive", "在岗", "停用"]}},
        ).getvalue()
    )

    app = Flask(__name__)

    @app.get("/template")
    def _template():
        return send_excel_template_file(str(custom_path), download_name="人员基本信息.xlsx")

    response = app.test_client().get("/template")
    assert response.status_code == 200

    workbook = None
    try:
        workbook = openpyxl.load_workbook(filename=io.BytesIO(response.data), data_only=True)
        ws = workbook.active
        assert ws["A2"].value == "OP999"
        assert ws["C2"].value == "active"
        assert ws["E2"].value == "保留用户模板"
    finally:
        if workbook is not None:
            workbook.close()


def test_ensure_excel_templates_preserves_user_custom_template_with_extra_rows(tmp_path) -> None:
    from core.services.common.excel_templates import build_xlsx_bytes, ensure_excel_templates

    custom_path = tmp_path / "人员基本信息.xlsx"
    custom_path.write_bytes(
        build_xlsx_bytes(
            ["工号", "姓名", "状态", "班组", "备注"],
            [
                ["OP001", "张三", "active", "A组", "用户自定义示例"],
                ["OP002", "李四", "inactive", "B组", "用户额外示例"],
            ],
            format_spec={"enum_cols": {2: ["active", "inactive", "在岗", "停用"]}},
        ).getvalue()
    )

    stats = ensure_excel_templates(str(tmp_path))
    assert "人员基本信息.xlsx" in stats["skipped"]

    workbook = None
    try:
        workbook = openpyxl.load_workbook(filename=custom_path, data_only=True)
        ws = workbook.active
        assert ws["C2"].value == "active"
        assert ws["E3"].value == "用户额外示例"
    finally:
        if workbook is not None:
            workbook.close()


def test_import_errors_present_chinese_first_and_english_as_compatible_aliases() -> None:
    sources = "\n".join(
        _read(rel_path)
        for rel_path in (
            "core/services/common/excel_validators.py",
            "web/routes/process_excel_op_types.py",
            "web/routes/process_excel_suppliers.py",
            "web/routes/domains/scheduler/scheduler_excel_calendar.py",
            "web/routes/domains/scheduler/scheduler_excel_calendar_rows.py",
            "core/services/personnel/operator_machine_normalizers.py",
        )
    )
    assert "允许：normal/urgent/critical；或中文" not in sources
    assert "允许：yes/no/partial；或中文" not in sources
    assert "允许：workday/holiday；或中文" not in sources
    assert "允许：yes/no/true/false/1/0；或中文" not in sources
    assert "允许：internal / external；或中文" not in sources
    assert "允许：active / inactive；或中文" not in sources
    assert "可填写：普通 / 急件 / 特急。以前的 Excel 如果写过英文，系统会尽量按中文意思读取；新文件请直接填中文" in sources
    assert "新文件请填写：齐套 / 未齐套 / 部分齐套。以前的 Excel 如果写过 是 / 否 或英文，系统会尽量按中文意思读取；新文件请直接填中文推荐值" in sources
    assert "新文件请填写：工作日 / 假期。以前的 Excel 如果写过周末 / 节假日或英文，系统会尽量按中文意思读取；新文件请直接填中文推荐值" in sources
    assert "可填写：是 / 否。以前的 Excel 如果写过英文，系统会尽量按中文意思读取；新文件请直接填中文" in sources
    assert "请填写中文：自制、外协。以前的 Excel 如果写过“内部、外部、内、外”，系统会尽量按自制或外协读取" in sources
    assert "可填写：启用 / 停用 / 在用 / 正常 / 禁用。以前的 Excel 如果写过英文状态，系统会尽量按中文意思读取；新文件请直接填中文" in sources
    assert "以前的 Excel 如果写过英文，系统会尽量按中文意思读取；新文件请直接填中文" in sources


def test_excel_exports_use_chinese_labels_for_enum_columns() -> None:
    route_expectations = {
        "web/routes/personnel_excel_operators.py": ("operator_status_label",),
        "web/routes/equipment_excel_machines.py": ("machine_status_label",),
        "web/routes/process_excel_op_types.py": ("source_type_label",),
        "web/routes/process_excel_suppliers.py": ("supplier_status_label",),
        "web/routes/personnel_excel_links.py": ("skill_level_label", "yes_no_label"),
        "web/routes/equipment_excel_links.py": ("skill_level_label", "yes_no_label"),
        "web/routes/domains/scheduler/scheduler_excel_batches.py": ("batch_priority_label", "ready_status_label"),
        "web/routes/domains/scheduler/scheduler_excel_calendar.py": ("calendar_day_type_label", "yes_no_label"),
        "web/routes/personnel_excel_operator_calendar.py": ("calendar_day_type_label", "yes_no_label"),
        "web/routes/process_excel_part_operations.py": ("source_type_label",),
    }
    for rel_path, helpers in route_expectations.items():
        source = _read(rel_path)
        for helper in helpers:
            assert helper in source, f"{rel_path} 导出枚举字段应使用 {helper}"


def test_frontend_scripts_keep_internal_details_out_of_user_messages() -> None:
    boot = _read("frontend/workbench/app/main.jsx")
    assert "工作台资源未完整加载，请检查本机安装文件。" in boot
    assert "root.replaceChildren(alert, retry)" in boot
    for term in ("缺失：", "未找到数据接口 URL（data-url；兼容 data-data-url）", "dataUrl="):
        assert term not in boot
    transport = _read("frontend/workbench/app/transport.js")
    for phrase in ("本机状态读取超时，请稍后重试。", "无法连接本机服务", "读到的数据不完整，页面没有改动。请刷新后重试。"):
        assert phrase in transport
    assert "AbortController" in transport and "clearTimeout(timer)" in transport
    detail = _read("frontend/workbench/app/PlanDetailsUI.jsx")
    for phrase in ("工艺前后序", "前序", "后序", "计划开始", "计划结束", "读取完整计划并定位"):
        assert phrase in detail
    for term in ("间隔（分钟）", "间隔(分)", "关键链前驱：", "关键链依据："):
        assert term not in detail
    manual = _read("static/docs/scheduler_manual.md")
    manual_viewmodel = _read("web/viewmodels/page_manuals_scheduler_outputs.py")
    # 手册整改后，缩放档位和查看模式的细节收进页面说明；总说明书只保留操作要点。
    for phrase in (
        "当前为查看模式",
        "月、周、日",
        "12小时 / 6小时",
        "1分钟",
        "范围太大",
        "拖拽调整功能尚未开放",
    ):
        assert phrase in manual_viewmodel
    assert "便于点击的命中区域" in manual
    assert "后续页面入口接好并放行后再开放" not in manual
    assert "后续草稿和校验链路完成后再开放" not in manual
    for phrase in (
        "查看模式",
        "时间粒度",
        "范围太大",
        "短工序",
        "不能放进文件名的符号",
    ):
        assert phrase in manual_viewmodel
    assert "不能放进下载文件名的符号" in manual


def test_process_and_scheduler_errors_use_chinese_terms() -> None:
    route_parser = _read("core/services/process/route_parser_errors.py")
    assert "当前要求先把工种资料补完整" in route_parser
    assert "严格模式已拒绝" not in route_parser
    assert "strict_mode 已拒绝" not in route_parser
    assert "默认周期无法解析（{raw_default_days!r}）" not in route_parser
    assert "默认周期无效（{raw_default_days!r}）" not in route_parser

    external_group_service = _read("core/services/process/external_group_service.py")
    assert "系统先临时按 1 天保存" not in external_group_service
    assert "周期输入无效，本次会先按 1 天记录，请尽快补成真实周期。" in external_group_service
    assert "compatible mode" not in external_group_service.split("user_warning_text", 1)[-1]
    assert "append_unique_text_messages(user_warnings, user_warning_text)" in external_group_service
    assert "safe_warning(self.logger, log_warning_text)" in external_group_service

    batch_template_ops = _read("core/services/scheduler/batch_template_ops.py")
    assert "不支持“资料不完整就停下”" in batch_template_ops
    assert "不支持严格模式" not in batch_template_ops
    assert "不支持 strict_mode" not in batch_template_ops


def test_scheduler_analysis_hides_internal_schema_and_attempt_tags() -> None:
    analysis_vm = _read("web/viewmodels/scheduler_analysis_vm.py")
    analysis_compat = _read("web/viewmodels/scheduler_analysis_compat.py")
    assert "这个历史版本缺少新的分析字段，页面只展示能确认的内容。" in analysis_compat
    assert "新 schema 字段" not in analysis_vm + analysis_compat
    assert '"comparison_metric": "优化对比指标"' in analysis_compat
    assert '"best_score_schema": "系统比较顺序"' in analysis_compat

    analysis = _read_analysis_template()
    assert "完整候选比较摘要" in analysis and "整份候选与排产时的正式计划" in analysis
    assert "metric.value === null" in analysis and "metric.known_subtotal" in analysis
    assert "metric.reason.message" in analysis
    for term in ("compat_fallback.missing_fields | join", "方案 {{ loop.index }}", "/{{ dispatch_rule_zh", "{plan.source_table}", "{plan.scenario_id}"):
        assert term not in analysis


def test_reports_and_v2_batch_templates_match_public_manual_contracts() -> None:
    catalog = _read("core/services/workbench/report_catalog.py")
    assert '("utilization_percent", "整窗占用率（%）")' in catalog
    assert 'None if row.get("utilization") is None else round(row["utilization"] * 100, 2)' in catalog
    exporter = _read("core/services/report/exporters/xlsx.py")
    assert '["类别", "批次号", "图号", "名称", "数量", "交期", "完工/截至时间", "超期(天)", "超期(小时)"]' in exporter
    assert '"整窗占用率(%)"' in exporter and "_utilization_percent" in exporter
    batches = _read("frontend/workbench/app/BatchWorkspace.jsx")
    assert "删除所选" in batches and "preview('bulk', { action: 'delete', refs: selected" in batches
    assert "scope, token || snapshot" in batches
    assert "<BaseFields value={value}" in _read("frontend/workbench/app/BatchForms.jsx")
    gantt = _read("frontend/workbench/app/PlanGantt.jsx")
    assert "setZoom" in gantt and "selectedRef" in gantt
    assert "start_date=" not in gantt and "end_date=" not in gantt
    assert "base.write_context.write_token" in _read("frontend/workbench/app/SystemMaintenanceConfig.jsx")


@pytest.mark.parametrize(
    ("rel_path", "bad_tokens", "good_tokens"),
    (
        (
            "core/services/equipment/machine_service.py",
            ("璁惧",),
            ("设备编号不能为空", "设备名称不能为空"),
        ),
        (
            "core/services/process/op_type_service.py",
            ("鈥", "宸ョ"),
            ("“工种编号”不能为空", "“工种名称”不能为空"),
        ),
        (
            "core/services/equipment/machine_downtime_service.py",
            ("鍋滄満",),
            ("停机记录编号缺失，无法执行取消。",),
        ),
    ),
)
def test_known_garbled_error_messages_are_repaired(
    rel_path: str,
    bad_tokens: Tuple[str, ...],
    good_tokens: Tuple[str, ...],
) -> None:
    source = _read(rel_path)
    for token in bad_tokens:
        assert token not in source
    for token in good_tokens:
        assert token in source
