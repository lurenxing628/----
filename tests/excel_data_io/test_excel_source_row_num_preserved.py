"""回归测试：OperatorMachineService 人员设备关联导入在 preview_import_links/apply_import_links 全程保留源行号与源工作表名（__source_row_num=9、__source_sheet_name），缺工号时报 ERROR 并给出"工号不能为空"提示，且预览行 data 不泄漏 __source_* 保留元数据键。"""


def test_excel_source_row_num_preserved(db_path) -> None:


    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.common.excel_service import ImportMode, RowStatus
    from core.services.personnel.operator_machine_service import OperatorMachineService

    conn = get_connection(db_path)
    try:
        svc = OperatorMachineService(conn)
        preview_rows = svc.preview_import_links(
            [
                {
                    "__source_row_num": 9,
                    "__source_sheet_name": "人员设备关联",
                    "工号": "",
                    "设备编号": "MC_MISSING",
                    "技能等级": "熟练",
                    "主操设备": "主操",
                }
            ],
            mode=ImportMode.OVERWRITE,
        )

        if len(preview_rows) != 1:
            raise RuntimeError(f"人员设备关联预览行数量异常：{len(preview_rows)}")

        pr = preview_rows[0]
        if pr.status != RowStatus.ERROR:
            raise RuntimeError(f"人员设备关联缺少工号时应为 ERROR，实际：{pr.status!r}")
        if pr.row_num != 9 or pr.source_row_num != 9:
            raise RuntimeError(f"人员设备关联预览未保留源行号：row_num={pr.row_num!r} source_row_num={pr.source_row_num!r}")
        if pr.source_sheet_name != "人员设备关联":
            raise RuntimeError(f"人员设备关联预览未保留源工作表：{pr.source_sheet_name!r}")
        if "__source_row_num" in pr.data or "__source_sheet_name" in pr.data:
            raise RuntimeError(f"人员设备关联预览 data 不应暴露保留元数据键：{pr.data!r}")
        if pr.message != "“工号”不能为空":
            raise RuntimeError(f"人员设备关联缺少工号提示异常：{pr.message!r}")

        result = svc.apply_import_links(preview_rows, ImportMode.OVERWRITE)
        if int(result.get("error_count") or 0) != 1:
            raise RuntimeError(f"人员设备关联确认导入错误计数异常：{result!r}")
        errors_sample = list(result.get("errors_sample") or [])
        if len(errors_sample) != 1:
            raise RuntimeError(f"人员设备关联确认导入错误样本数量异常：{errors_sample!r}")

        sample = errors_sample[0]
        if sample.get("row") != 9:
            raise RuntimeError(f"人员设备关联确认导入错误样本 row 未保持源行号：{sample!r}")
        if sample.get("source_row_num") != 9:
            raise RuntimeError(f"人员设备关联确认导入错误样本 source_row_num 异常：{sample!r}")
        if sample.get("source_sheet_name") != "人员设备关联":
            raise RuntimeError(f"人员设备关联确认导入错误样本 source_sheet_name 异常：{sample!r}")
        if sample.get("message") != "“工号”不能为空":
            raise RuntimeError(f"人员设备关联确认导入错误样本文案异常：{sample!r}")
    finally:
        conn.close()


