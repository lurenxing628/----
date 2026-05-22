from __future__ import annotations

import io
from pathlib import Path

import openpyxl
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _read_analysis_template() -> str:
    parts = (
        "templates/scheduler/analysis.html",
        "templates/scheduler/analysis_parts/_version_picker.html",
        "templates/scheduler/analysis_parts/_selected_overview.html",
        "templates/scheduler/analysis_parts/_candidate_comparison.html",
        "templates/scheduler/analysis_parts/_optimization_process.html",
    )
    return "\n".join(_read(path) for path in parts)


def test_scheduler_config_and_batch_hints_are_user_facing_chinese() -> None:
    expected_holiday_hint = "假期也安排生产且未单独填写效率时，系统会使用这里的效率值；请输入大于 0 的数字。"
    expected_batch_manage_hint = (
        "只在批次需要按零件路线生成工序时生效。勾选后：缺工种、缺供应商或外协周期不正确时，会停止创建并提示原因。"
        "不勾选：能确认的工序会先生成；缺少外协周期时会先按 1 天记录并提醒补正。"
    )
    expected_batch_schedule_hint = (
        "勾选后：系统会先检查两类内容。第一，高级设置里的选项必须是页面能选到的值，例如派工方式、智能派工策略、自动分配设备人员不能乱填。"
        "第二，工时、外协周期、权重、锁定天数这类数字必须是正常数字，不能空着、填负数或填文字。"
        "发现这些问题会停下，让你先修改。不勾选：为了兼容旧数据，系统会先按默认值继续排，例如空工时按 0 小时、外协周期缺失按 1 天、坏掉的高级设置按页面默认项，并在结果提醒里告诉你需要回去补哪项。"
    )

    for rel_path in ("templates/scheduler/config.html", "web_new_test/templates/scheduler/config.html"):
        source = _read(rel_path)
        assert expected_holiday_hint in source
        assert "假期安排生产但未单独设置效率时" not in source
        assert "&gt;0" not in source

    for rel_path in (
        "templates/scheduler/batches_manage.html",
        "web_new_test/templates/scheduler/batches_manage.html",
    ):
        source = _read(rel_path)
        assert expected_batch_manage_hint in source
        assert "解析器不支持 strict_mode" not in source

    run_panel = _read("templates/scheduler/_run_panel.html")
    assert expected_batch_schedule_hint in run_panel
    assert "配置不合法" not in run_panel
    assert "安全取值" not in run_panel
    assert "工时空着时可能按 0" not in run_panel
    for rel_path in ("templates/scheduler/batches.html", "web_new_test/templates/scheduler/batches.html"):
        source = _read(rel_path)
        assert '{% include "scheduler/_run_panel.html" %}' in source
        assert "dispatch_mode / dispatch_rule / auto_assign_enabled" not in source
        assert "设了截止日期的话，排不完会提示失败。" not in source


def test_scheduler_run_copy_avoids_vague_vocabulary_for_operators() -> None:
    forbidden_terms = (
        "配置不合法",
        "安全取值",
        "工时空着时可能",
        "可能按 0 小时",
        "当前配置无效",
        "配置无效",
        "格式不合法",
        "时间不合法",
        "外协周期缺失或不合法",
    )
    user_facing_sources = (
        "templates/scheduler/_run_panel.html",
        "web/viewmodels/scheduler_run_options.py",
        "web/viewmodels/page_manuals_scheduler.py",
        "web/viewmodels/page_manuals_scheduler_week_plan.py",
        "web/viewmodels/scheduler_degradation_presenter.py",
        "core/services/scheduler/summary/schedule_summary_degradation.py",
        "static/js/gantt_contract.js",
        "static/docs/scheduler_manual.md",
        "web_new_test/static/docs/scheduler_manual.md",
    )

    for rel_path in user_facing_sources:
        source = _read(rel_path)
        for term in forbidden_terms:
            assert term not in source, f"{rel_path} 仍包含含糊旧说法：{term}"


def test_scheduler_config_repair_notices_use_public_field_labels() -> None:
    for rel_path in ("templates/scheduler/config.html", "web_new_test/templates/scheduler/config.html"):
        source = _read(rel_path)
        assert "current_config_notice_items" in source
        assert "ui.details_notice(notice" in source
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
    analysis = _read_analysis_template()
    assert "dispatch_mode_zh" in analysis
    assert "dispatch_rule_zh" in analysis
    assert "attempts / 优化曲线 / 超期明细" not in analysis
    assert "r.dispatch_mode }}/{{ r.dispatch_rule" not in analysis
    assert "algo_config.get('algo_mode') or algo.mode" in analysis
    assert "mode_zh.get(algo.mode" not in analysis

    for rel_path in ("templates/scheduler/gantt.html", "web_new_test/templates/scheduler/gantt.html"):
        source = _read(rel_path)
        assert "排程数据" in source
        assert "Schedule 数据" not in source

    logs = _read("templates/system/logs.html")
    assert "按英文值筛选" not in logs
    assert "如：排产、备份、设备" in logs
    assert "如：新增、导入、删除" in logs
    assert "<code>{{ r.module }}</code>" not in logs
    assert "<code>{{ r.action }}</code>" not in logs
    assert "{{ r.module_label }}" in logs
    assert "{{ r.action_label }}" in logs
    assert "{{ r.module }}" not in logs
    assert "{{ r.action }}" not in logs
    assert 'title="{{ r.module }}"' not in logs
    assert 'title="{{ r.action }}"' not in logs
    assert 'title="{{ r.target_type }}"' not in logs


def test_debug_details_do_not_expose_flask_endpoint_names_to_users() -> None:
    rel_paths = (
        "templates/scheduler/config.html",
        "web_new_test/templates/scheduler/config.html",
        "templates/scheduler/batches.html",
        "web_new_test/templates/scheduler/batches.html",
        "templates/personnel/list.html",
        "templates/personnel/detail.html",
        "templates/personnel/calendar.html",
    )
    for rel_path in rel_paths:
        source = _read(rel_path)
        assert "后端接口未注册（endpoint" not in source
        assert "endpoint）" not in source
        assert "missing_preset_endpoints|join" not in source


def test_process_excel_current_tables_render_chinese_display_fields() -> None:
    operators = _read("templates/personnel/excel_import_operator.html")
    assert 'r["状态显示"]' in operators
    assert '<td>{{ r["状态"] }}</td>' not in operators

    machines = _read("templates/equipment/excel_import_machine.html")
    assert 'r["状态显示"]' in machines
    assert '<td>{{ r["状态"] }}</td>' not in machines

    batches = _read("templates/scheduler/excel_import_batches.html")
    assert 'r["优先级显示"]' in batches
    assert 'r["齐套显示"]' in batches
    assert '<td>{{ r["优先级"] }}</td>' not in batches
    assert '<td>{{ r["齐套"] }}</td>' not in batches

    calendar = _read("templates/scheduler/excel_import_calendar.html")
    assert 'r["类型显示"]' in calendar
    assert 'r["允许普通件显示"]' in calendar
    assert 'r["允许急件显示"]' in calendar
    assert '<td>{{ r["类型"] }}</td>' not in calendar
    assert '<td>{{ r["允许普通件"] }}</td>' not in calendar
    assert '<td>{{ r["允许急件"] }}</td>' not in calendar

    operator_calendar = _read("templates/personnel/excel_import_operator_calendar.html")
    assert 'r["类型显示"]' in operator_calendar
    assert 'r["允许普通件显示"]' in operator_calendar
    assert 'r["允许急件显示"]' in operator_calendar
    assert '<td>{{ r["类型"] }}</td>' not in operator_calendar
    assert '<td>{{ r["允许普通件"] }}</td>' not in operator_calendar
    assert '<td>{{ r["允许急件"] }}</td>' not in operator_calendar

    op_types = _read("templates/process/excel_import_op_types.html")
    assert 'r["归属显示"]' in op_types
    assert '<td>{{ r["归属"] }}</td>' not in op_types

    part_operation_hours = _read("templates/process/excel_import_part_operation_hours.html")
    assert 'r["归属显示"]' in part_operation_hours
    assert '<td>{{ r["归属"] }}</td>' not in part_operation_hours

    suppliers = _read("templates/process/excel_import_suppliers.html")
    assert 'r["状态显示"]' in suppliers
    assert 'r["备注"]' in suppliers
    assert '<td>{{ r["状态"] }}</td>' not in suppliers

    preview_component = _read("templates/components/excel_import.html")
    assert "r.display_data" in preview_component
    assert "r.data | tojson_zh" not in preview_component

    batch_preview_template = _read("templates/scheduler/excel_import_batches.html")
    assert "r.display_data" in batch_preview_template
    assert "r.data | tojson_zh" not in batch_preview_template
    assert "else r.data" not in batch_preview_template
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
    assert "主操设备填“是”" in operator_machine_service


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
    assert "智能派工策略" in static_manual
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
    gantt_boot = _read("static/js/gantt_boot.js")
    assert "页面脚本加载不完整" in gantt_boot
    assert "reportClientError" in gantt_boot
    assert "缺失：" not in gantt_boot
    assert "未找到数据接口 URL（data-url；兼容 data-data-url）" not in gantt_boot
    assert "dataUrl=" not in gantt_boot
    assert "甘特图数据请求超过" in gantt_boot
    assert ">${fetchTimeoutMs}ms" not in gantt_boot

    gantt_render = _read("static/js/gantt_render.js")
    assert "甘特图装饰刷新失败" in gantt_render
    assert "Gantt decorate failed" not in gantt_render
    assert "加工方式：" in gantt_render
    assert "前面影响它的工序编号：" in gantt_render
    assert "为什么影响总工期：" in gantt_render
    assert "中间等待：" in gantt_render
    assert "间隔（分钟）" not in gantt_render
    assert "间隔(分)" not in gantt_render
    assert "关键链前驱：" not in gantt_render
    assert "关键链依据：" not in gantt_render

    gantt_contract = _read("static/js/gantt_contract.js")
    for phrase in (
        "查看模式",
        "时间粒度：月/周/日",
        "短工序",
        "范围保护",
        "开始日从 00:00 开始",
    ):
        assert phrase in gantt_contract
    assert "透明点击区" not in gantt_contract

    manual = _read("static/docs/scheduler_manual.md")
    manual_mirror = _read("web_new_test/static/docs/scheduler_manual.md")
    manual_viewmodel = _read("web/viewmodels/page_manuals_scheduler_outputs.py")
    for phrase in (
        "甘特图当前是",
        "月、周、日",
        "12小时 / 6小时",
        "1分钟",
        "范围太大",
        "保留方便点击的区域",
    ):
        assert phrase in manual
        assert phrase in manual_mirror
    for phrase in (
        "查看模式",
        "时间粒度",
        "范围太大",
        "短工序",
    ):
        assert phrase in manual_viewmodel

    resource_dispatch = _read("static/js/resource_dispatch.js")
    assert "有一条排班提示没有完整说明" in resource_dispatch
    assert "parts.push(escapeHtml(code));" not in resource_dispatch


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
    assert '"best_score_schema": "评分顺序"' in analysis_compat

    analysis_template = _read_analysis_template()
    assert "compat_fallback.missing_field_labels" in analysis_template
    assert "compat_fallback.missing_fields | join" not in analysis_template
    assert 'data-col-key="source"' in analysis_template
    assert ">方案来源</th>" in analysis_template
    assert "<th>方案来源</th>" not in analysis_template
    assert "r.display_tag" in analysis_template or "{{ r.tag }}" in analysis_template
    assert "方案 {{ loop.index }}" not in analysis_template
    assert "row_dispatch_rule" in analysis_template
    assert "/{{ dispatch_rule_zh" not in analysis_template


def test_gantt_contract_frontend_preserves_reason_code_and_deduplicates_unavailable_tooltip() -> None:
    gantt_contract = _read("static/js/gantt_contract.js")
    assert "reason_code" in gantt_contract
    assert "critical.reason_code" in gantt_contract or "raw.reason_code" in gantt_contract
    assert "dedupeCriticalReason" in gantt_contract
    assert "关键链暂不可用（关键链暂不可用）" not in gantt_contract
    assert "reasonText, unavailableMessage" not in gantt_contract


def test_reports_and_v2_batch_templates_match_public_manual_contracts() -> None:
    utilization = _read("templates/reports/utilization.html")
    assert "利用率(%)" in utilization
    assert "utilization_percent" in utilization
    assert "r.utilization if r.utilization is not none" not in utilization

    exporter = _read("core/services/report/exporters/xlsx.py")
    assert '["类别", "批次号", "图号", "名称", "数量", "交期", "完工/截至时间", "超期(天)", "超期(小时)"]' in exporter
    assert '"利用率(%)"' in exporter
    assert "_utilization_percent" in exporter

    for rel_path in ("web_new_test/templates/scheduler/batches.html", "web_new_test/templates/scheduler/batches_manage.html"):
        source = _read(rel_path)
        assert "scheduler.delete_batch" in source
        assert "确认删除该批次" in source
        assert 'name="next"' in source

    gantt_v2 = _read("web_new_test/templates/scheduler/gantt.html")
    for line in gantt_v2.splitlines():
        if "上周" in line or "回到本周" in line or "下周" in line:
            assert "start_date=" not in line
            assert "end_date=" not in line


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
    bad_tokens: tuple[str, ...],
    good_tokens: tuple[str, ...],
) -> None:
    source = _read(rel_path)
    for token in bad_tokens:
        assert token not in source
    for token in good_tokens:
        assert token in source
