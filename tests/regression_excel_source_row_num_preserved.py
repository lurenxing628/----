import os
import sys
import tempfile


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_source_row_num_")
    test_db = os.path.join(tmpdir, "aps_test.db")

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=None)

    from core.services.common.excel_service import ImportMode, RowStatus
    from core.services.personnel.operator_machine_service import OperatorMachineService

    conn = get_connection(test_db)
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

    print("OK")


if __name__ == "__main__":
    main()
