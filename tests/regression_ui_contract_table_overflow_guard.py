from __future__ import annotations

import os
import re


def _find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _assert_regex(text: str, pattern: str, msg: str) -> None:
    if re.search(pattern, text, flags=re.MULTILINE | re.DOTALL) is None:
        raise RuntimeError(msg + f"（pattern: {pattern}）")


def main() -> None:
    repo_root = _find_repo_root()
    css_path = os.path.join(repo_root, "static", "css", "ui_contract.css")
    css = _read(css_path)
    table_resize = _read(os.path.join(repo_root, "static", "js", "table_resize.js"))

    # 1) 全局兜底：所有表格单元格遇到超长 token 时可断词，避免跨列溢出
    _assert_regex(
        css,
        r"table\s+th\s*,\s*table\s+td\s*\{[^}]*overflow-wrap\s*:\s*anywhere\s*;",
        "ui_contract.css 缺少全局表格断词兜底（table th/td overflow-wrap:anywhere）",
    )

    # 2) 固定布局表格：强制单行 + 省略号，确保列表页列宽稳定、不串列
    _assert_regex(
        css,
        r"\.table-layout-fixed\s+th\s*,\s*\.table-layout-fixed\s+td\s*\{"
        r"[^}]*overflow\s*:\s*hidden\s*;"
        r"[^}]*text-overflow\s*:\s*ellipsis\s*;"
        r"[^}]*white-space\s*:\s*nowrap\s*;",
        "ui_contract.css 缺少 fixed 表格省略号契约（.table-layout-fixed th/td overflow hidden + ellipsis + nowrap）",
    )

    # 3) Excel 预览详情默认折叠，展开后也不能把整页撑宽
    _assert_regex(
        css,
        r"\.aps-row-detail\s+pre\s*\{"
        r"[^}]*max-width\s*:\s*100%\s*;"
        r"[^}]*overflow\s*:\s*auto\s*;"
        r"[^}]*white-space\s*:\s*pre-wrap\s*;"
        r"[^}]*overflow-wrap\s*:\s*anywhere\s*;",
        "ui_contract.css 缺少 Excel 预览详情防撑宽契约（.aps-row-detail pre）",
    )

    page_guards = (
        ("templates/material/materials.html", "物料列表"),
        ("templates/material/batch_materials.html", "物料需求列表"),
        ("templates/personnel/teams.html", "班组列表"),
        ("templates/personnel/excel_import_operator_calendar.html", "当前个人日历数据"),
        ("templates/scheduler/week_plan.html", "预览（前 50 行"),
    )
    for rel_path, marker in page_guards:
        source = _read(os.path.join(repo_root, rel_path))
        if marker not in source:
            raise RuntimeError(f"{rel_path} 缺少表格区域标记：{marker}")
        block = source[source.index(marker) :]
        if "aps-table-scroll" not in block:
            raise RuntimeError(f"{rel_path} 的宽表格缺少 aps-table-scroll 横向滚动保护")

    for token in (
        "data-default-w",
        "data-col-w",
        "w-",
        "cell.style && cell.style.width",
        "buildWidthSig",
        "applyTableMinWidthFromColgroup",
        "APS_InitResizableTables",
        "scope.matches",
    ):
        if token not in table_resize:
            raise RuntimeError(f"table_resize.js 缺少模板声明列宽支持：{token}")

    table_contracts = (
        ("templates/scheduler/batches.html", 'id="batchesTable"', "v3_batchesTable"),
        ("web_new_test/templates/scheduler/batches.html", 'id="batchesTable"', "v3_batchesTable"),
        ("templates/scheduler/batches_manage.html", 'id="batchesManageTable"', "v3_batchesManageTable"),
        ("web_new_test/templates/scheduler/batches_manage.html", 'id="batchesManageTable"', "v3_batchesManageTable"),
        ("templates/scheduler/batch_detail.html", 'id="batchOpsTable"', "v3_batchOpsTable"),
        ("templates/scheduler/analysis.html", 'id="analysisAttemptsTable"', "v3_analysisAttemptsTable"),
        ("templates/scheduler/week_plan.html", 'id="weekPlanPreviewTable"', "v2_weekPlanPreviewTable"),
        ("templates/scheduler/calendar.html", 'id="workCalendarTable"', "v2_workCalendarTable"),
        ("templates/scheduler/excel_import_calendar.html", 'id="excelCalendarExistingTable"', "v2_excelCalendarExistingTable"),
        ("templates/components/excel_import.html", 'id="excelPreviewTable"', "v2_excelPreviewTable"),
        ("templates/scheduler/excel_import_batches.html", 'id="excelBatchPreviewTable"', "v2_excelBatchPreviewTable"),
        ("templates/scheduler/excel_import_batches.html", 'id="excelBatchesExistingTable"', "v2_excelBatchesExistingTable"),
        ("templates/scheduler/resource_dispatch.html", 'id="rdDetailTable"', "v1_resourceDispatchDetail"),
        ("templates/equipment/list.html", 'id="equipmentTable"', "v2_equipmentTable"),
        ("templates/equipment/excel_import_machine.html", 'id="excelMachineExistingTable"', "v2_excelMachineExistingTable"),
        (
            "templates/equipment/excel_import_machine_operator.html",
            'id="excelMachineOperatorExistingTable"',
            "v2_excelMachineOperatorExistingTable",
        ),
        ("templates/equipment/detail.html", 'id="machineLinkedOperatorsTable"', "v2_machineLinkedOperatorsTable"),
        ("templates/equipment/detail.html", 'id="machineDowntimeTable"', "v2_machineDowntimeTable"),
        ("templates/personnel/list.html", 'id="personnelTable"', "v2_personnelTable"),
        ("templates/personnel/excel_import_operator.html", 'id="excelOperatorExistingTable"', "v2_excelOperatorExistingTable"),
        (
            "templates/personnel/excel_import_operator_machine.html",
            'id="excelOperatorMachineExistingTable"',
            "v2_excelOperatorMachineExistingTable",
        ),
        (
            "templates/personnel/excel_import_operator_calendar.html",
            'id="excelOperatorCalendarExistingTable"',
            "v2_excelOperatorCalendarExistingTable",
        ),
        ("templates/personnel/detail.html", 'id="operatorLinkedMachinesTable"', "v2_operatorLinkedMachinesTable"),
        ("templates/personnel/teams.html", 'id="teamsTable"', "v2_teamsTable"),
        ("templates/personnel/calendar.html", 'id="operatorCalendarTable"', "v2_operatorCalendarTable"),
        ("templates/process/list.html", 'id="partsTable"', "v2_partsTable"),
        ("templates/process/suppliers_list.html", 'id="suppliersTable"', "v2_suppliersTable"),
        ("templates/process/detail.html", 'id="partOperationsTable"', "v2_partOperationsTable"),
        ("templates/process/op_types_list.html", 'id="opTypesTable"', "v2_opTypesTable"),
        (
            "templates/process/excel_import_part_operation_hours.html",
            'id="excelPartHoursExistingTable"',
            "v2_excelPartHoursExistingTable",
        ),
        ("templates/process/excel_import_routes.html", 'id="excelRoutesExistingTable"', "v2_excelRoutesExistingTable"),
        ("templates/process/excel_import_suppliers.html", 'id="excelSuppliersExistingTable"', "v2_excelSuppliersExistingTable"),
        ("templates/process/excel_import_op_types.html", 'id="excelOpTypesExistingTable"', "v2_excelOpTypesExistingTable"),
        ("templates/material/materials.html", 'id="materialsTable"', "v2_materialsTable"),
        ("templates/material/batch_materials.html", 'id="batchMaterialsTable"', "v2_batchMaterialsTable"),
        ("templates/reports/overdue.html", 'id="overdueTable"', "v2_overdueTable"),
        ("templates/reports/utilization.html", 'id="utilizationMachineTable"', "v2_utilizationMachineTable"),
        ("templates/reports/utilization.html", 'id="utilizationOperatorTable"', "v2_utilizationOperatorTable"),
        ("templates/reports/downtime.html", 'id="downtimeTable"', "v2_downtimeTable"),
        ("templates/system/backup.html", 'id="pluginStatusTable"', "v2_pluginStatusTable"),
        ("templates/system/history.html", 'id="systemHistoryTable"', "v2_systemHistoryTable"),
        ("templates/system/logs.html", 'id="systemLogsTable"', "v2_systemLogsTable"),
    )
    for rel_path, table_marker, table_key in table_contracts:
        source = _read(os.path.join(repo_root, rel_path))
        if table_marker not in source:
            raise RuntimeError(f"{rel_path} 缺少目标表格：{table_marker}")
        table_start = source.index(table_marker)
        wrapper_start = source.rfind("aps-table-scroll", 0, table_start)
        previous_table_end = source.rfind("</table>", 0, table_start)
        if wrapper_start < 0 or wrapper_start < previous_table_end:
            raise RuntimeError(f"{rel_path} 的 {table_marker} 没有被 aps-table-scroll 包住")
        table_block = source[table_start : source.index("</table>", table_start)]
        for token in ('data-col-resize="1"', f'data-table-key="{table_key}"', "data-default-w=", "data-min-w="):
            if token not in table_block:
                raise RuntimeError(f"{rel_path} 的 {table_marker} 缺少表格列宽合同：{token}")

    print("OK")


if __name__ == "__main__":
    main()
