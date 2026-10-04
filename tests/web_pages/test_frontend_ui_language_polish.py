"""回归测试：面向用户的文案必须是规范中文，不得泄露内部术语。

只读源文件，不起浏览器——真机那半在同名的 *_browser.py 里。2026-09-21 拆开：
浏览器车道按文件判定，两者放在一起会让纯读文件的用例也被标 perf、退出所有门禁。

守的是：甘特与日志展示字段用中文 label、错误文案中文优先而英文仅作兼容别名、
调试细节不外泄、以及若干已知乱码错误消息已被修复。
2026-09-18 旧路由层退役后，本文件里指向已删文件的断言已在 2026-09-21 逐条裁决：
对象还在的剪掉死路径继续守，对象整体消失的整条退役并写明由谁接手。
"""

from __future__ import annotations

import io
from typing import Tuple

import openpyxl
import pytest

from tests._support.paths import REPO_ROOT


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _read_analysis_template() -> str:
    """Read current analysis presenters; do not restore removed templates."""
    return "\n".join(_read(path) for path in (
        "frontend/workbench/app/PlanCatalogUI.jsx", "frontend/workbench/app/PlanDetailsUI.jsx",
        "frontend/workbench/app/RunHistoryControls.jsx", "frontend/workbench/app/RunCandidateControls.jsx",
        "frontend/workbench/app/RunCandidateAnalysis.jsx",
    ))


def test_scheduler_run_copy_avoids_vague_vocabulary_for_operators() -> None:
    forbidden_terms = ("配置不合法", "安全取值", "工时空着时可能", "可能按 0 小时", "当前配置无效",
                       "配置无效", "格式不合法", "时间不合法", "外协周期缺失或不合法")
    for path in (
        "frontend/workbench/app/PreflightControls.jsx", "frontend/workbench/app/RunJobControls.jsx",
        "frontend/workbench/app/PlanGantt.jsx", "frontend/workbench/app/PlanWorkspace.jsx",
        # scheduler_run_options.py 与 scheduler_degradation_presenter.py 随 2026-09-18
        # 旧路由层退役删除，降级展示在工作台无后继；其余 8 个源仍然要守这批含糊词。
        "web/viewmodels/page_manuals_scheduler.py",
        "web/viewmodels/page_manuals_scheduler_week_plan.py",
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

    # scheduler_config_panel.py 随旧路由层退役删除，工作台改由 SystemMaintenanceConfig.jsx
    # 直接渲染 field.label；上面三条断言已经覆盖前端这一侧。
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

    from core.services.workbench.facts.system_reads import log_records

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
    # legacy_result.html 随旧路由层退役删除；其余 5 个仍然要守。
    for path in ("frontend/workbench/app/main.jsx", "frontend/workbench/app/ResourceForms.jsx",
                 "frontend/workbench/app/BatchForms.jsx", "frontend/workbench/app/SystemMaintenanceConfig.jsx",
                 "frontend/workbench/app/PlanWorkspace.jsx"):
        source = _read(path)
        for term in ("后端接口未注册（endpoint", "endpoint）", "missing_preset_endpoints|join"):
            assert term not in source


def test_source_and_primary_machine_labels_stay_chinese_for_users() -> None:
    """工艺归属与主操设备在用户面前是中文。

    这条原来叫 test_process_excel_current_tables_render_chinese_display_fields，守的是
    旧 Excel 预览页按 display_data 渲染中文、隐藏 op_id。那一整套页面、legacy_presentation
    的 preview_fields、以及 8 个旧路由都随 2026-09-18 退役删除，对象整体消失。工作台的
    同类口径已由 tests/workbench/test_*_files.py 逐表接手（自制/外协、是/否 都在那边锁着），
    这里只留三个仍然活着、别处没覆盖的碎片。

    顺带记一笔：op_type_service.py 的「归属显示」与 supplier_service.py 的「状态显示」
    两个字段在全仓已经没有消费方，原来只被这条测试钉着活。它们的去留是独立裁决，
    不在这里继续替它们站岗。
    """
    detail = _read("frontend/workbench/app/ProcessDetail.jsx")
    assert "P = window.APSProcessContract" in detail and "P.sourceLabel(row.source)" in detail

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

    scheduler_manuals = "\n".join(
        (
            _read("web/viewmodels/page_manuals_scheduler.py"),
            _read("web/viewmodels/page_manuals_scheduler_admin.py"),
            _read("web/viewmodels/page_manuals_scheduler_outputs.py"),
            _read("web/viewmodels/page_manuals_scheduler_week_plan.py"),
        )
    )
    full_manual = _read("static/docs/scheduler_manual.md")
    manual_sources = "\n".join((
        _read("web/viewmodels/page_manuals_process.py"),
        scheduler_manuals,
        _read("web/viewmodels/page_manuals_personnel.py"),
        _read("web/viewmodels/page_manuals_equipment.py"),
        full_manual,
    ))

    # 工作台模板使用中文业务值，旧英文文件仍兼容；说明书跟随真实文件合同。
    assert "固定选项直接使用模板中的中文" in full_manual
    assert "以前导出的英文代号仍然兼容" in full_manual
    assert "归属和外协周期策略使用与页面相同的中文" in full_manual
    assert "初级 / 普通 / 熟练" in full_manual
    assert "只填代号：internal 自制 / external 外协" not in full_manual
    assert "兼容英文标准值" not in manual_sources
    assert "`locked`" not in full_manual
    assert "`unlocked`" not in full_manual

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
    assert "只要预检里有一行被拒绝，确认按钮就点不下去" in static_manual
    # 文件导入侧的"资料不完整就停下"开关随第 1 章重写退役：工作台的导入对话框没有这个勾选项，
    # 缺工种/缺供应商由预检逐行指出。排产面板那一个参数开关仍在，见第 6 章。
    assert "预检会指出是哪一道工序对不上，先把工种补齐再导" in static_manual
    assert "route_raw 自动补建模板" not in static_manual
    # 2026-09-21 起自动分配是“本次排产规则”里的缺资源工序选项，说明书按页面控件写。
    assert "缺资源工序" in static_manual
    assert "自动分配 / 暂不排" in static_manual
    assert "dispatch_mode / dispatch_rule / auto_assign_enabled" not in static_manual


def test_supplier_manual_matches_required_default_days_and_template_columns() -> None:
    manual_sources = "\n".join(
        _read(rel_path)
        for rel_path in (
            "web/viewmodels/page_manuals_process.py",
            "static/docs/scheduler_manual.md",
        )
    )
    # 新增供应商时域层要求大于 0 的默认周期，已有供应商留空表示保持原样——两件事都要说清楚，
    # 尤其不能再出现"不填按 1 天"这类旧兜底说法：那是历史读取的兼容回退，不是写入行为。
    assert "默认周期天数，填大于 0 的数字；新增供应商必须填，已有的留空保持原样" in manual_sources
    assert "新增供应商时留空、不大于 0、不是数字" in manual_sources
    assert "模板只有4列" not in manual_sources
    assert "不填默认1天" not in manual_sources
    assert "不填默认 1 天" not in manual_sources
    assert "留空默认 1 天" not in manual_sources
    assert "周期默认1天" not in manual_sources


def test_material_status_and_delete_messages_match_user_page_labels() -> None:
    material_page = _read("web/viewmodels/page_manuals_material.py")
    material_service = _read("core/services/material/material_service.py")

    # 工作台物料页和物料文件都把 active 叫「启用」，物料导入也不认「可用」，说明书跟着页面说。
    assert "状态为启用" in material_page and "可用" not in material_page
    assert "删除可能失败；这时先去处理引用它的批次物料需求" in material_page
    assert "请选择：可用 / 停用" in material_service
    assert "请选择：启用 / 停用" not in material_service

    # web/routes/material.py 随旧路由层退役删除，删除受阻的提示改由工作台的批量删除给出。
    material_bulk = _read("core/services/workbench/material/bulk.py")
    assert "这个物料还挂在批次的物料需求上，不能删除。" in material_bulk
    assert "请稍后重试" not in material_bulk


def test_import_errors_present_chinese_first_and_english_as_compatible_aliases() -> None:
    # 四个旧路由随 2026-09-18 退役删除；剩下这两个源仍在工作台的链路上
    # （excel_validators 被批次 codec 与日历 codec 消费）。
    sources = "\n".join(
        _read(rel_path)
        for rel_path in (
            "core/services/common/excel_validators.py",
            "core/services/personnel/operator_machine_normalizers.py",
            "core/services/scheduler/calendar/admin.py",
        )
    )
    assert "允许：normal/urgent/critical；或中文" not in sources
    assert "允许：yes/no/partial；或中文" not in sources
    assert "允许：workday/holiday；或中文" not in sources
    assert "允许：yes/no/true/false/1/0；或中文" not in sources
    # 工种归属与供应商状态这两条随资源四表改填英文代号而失效（见 workbench_resource_file.py
    # 的 value_hint 与 tests/workbench/test_resource_file_codec.py），不再在这里守。
    assert "可填写：普通 / 急件 / 特急。以前的 Excel 如果写过英文，系统会尽量按中文意思读取；新文件请直接填中文" in sources
    assert "新文件请填写：齐套 / 未齐套 / 部分齐套。以前的 Excel 如果写过 是 / 否 或英文，系统会尽量按中文意思读取；新文件请直接填中文推荐值" in sources
    assert "新文件请填写：工作日 / 假期。以前的 Excel 如果写过周末 / 节假日或英文，系统会尽量按中文意思读取；新文件请直接填中文推荐值" in sources
    assert "可填写：是 / 否。以前的 Excel 如果写过英文，系统会尽量按中文意思读取；新文件请直接填中文" in sources
    assert "以前的 Excel 如果写过英文，系统会尽量按中文意思读取；新文件请直接填中文" in sources


# test_excel_exports_use_chinese_labels_for_enum_columns 已退役（2026-09-21）。
# 它守的 10 个旧 Excel 路由随 2026-09-18 退役全部删除，而且"导出枚举列一律用中文"
# 这条口径本身已被产品决策部分反转：工作台的资源四表导出英文代号（见
# core/models/workbench_resource_file.py 的 value_hint 与
# tests/workbench/test_resource_file_codec.py），日历、可操作设备、批次导出中文
# （由 tests/workbench/test_calendar_files.py、test_relation_files.py、
# test_batch_files.py 逐表锁住）。按表守比按"全都中文"守准确。


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
    assert "没有结束时间的记录按点表示" in manual
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
    assert "现场报工导出.xlsx" in manual


def test_process_and_scheduler_errors_use_chinese_terms() -> None:
    route_parser = _read("core/services/process/route_parser_errors.py")
    assert "当前要求先把工种资料补完整" in route_parser
    assert "严格模式已拒绝" not in route_parser
    assert "strict_mode 已拒绝" not in route_parser
    assert "默认周期无法解析（{raw_default_days!r}）" not in route_parser
    assert "默认周期无效（{raw_default_days!r}）" not in route_parser

    batch_template_ops = _read("core/services/batch/template_ops.py")
    assert "不支持“资料不完整就停下”" in batch_template_ops
    assert "不支持严格模式" not in batch_template_ops
    assert "不支持 strict_mode" not in batch_template_ops


def test_scheduler_analysis_hides_internal_schema_and_attempt_tags() -> None:
    # scheduler_analysis_vm.py 与 scheduler_analysis_compat.py 随 2026-09-18 退役删除
    # （那一批"只测旧视图模型"的测试也一并删了）；分析页本身还在，这半条继续守。
    analysis = _read_analysis_template()
    assert "完整候选比较摘要" in analysis and "整份候选与排产时的正式计划" in analysis
    assert "metric.value === null" in analysis and "metric.known_subtotal" in analysis
    assert "metric.reason.message" in analysis
    for term in ("compat_fallback.missing_fields | join", "方案 {{ loop.index }}", "/{{ dispatch_rule_zh", "{plan.source_table}", "{plan.scenario_id}"):
        assert term not in analysis


def test_reports_and_v2_batch_templates_match_public_manual_contracts() -> None:
    catalog = _read("core/services/workbench/report/catalog.py")
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
