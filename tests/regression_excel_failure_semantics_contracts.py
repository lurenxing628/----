import os
import sys
import tempfile
from unittest.mock import patch


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _assert_count(conn, sql: str, params, expected: int, name: str) -> None:
    actual = int(conn.execute(sql, params).fetchone()[0])
    if actual != expected:
        raise RuntimeError(f"{name} 数量异常：expected={expected} actual={actual}")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_excel_failure_semantics_")
    test_db = os.path.join(tmpdir, "aps_test.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.errors import ValidationError
    from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
    from core.services.equipment.machine_excel_import_service import MachineExcelImportService
    from core.services.personnel.operator_excel_import_service import OperatorExcelImportService
    from core.services.personnel.operator_machine_service import OperatorMachineService
    from core.services.process.op_type_excel_import_service import OpTypeExcelImportService
    from core.services.process.op_type_service import OpTypeService
    from core.services.process.part_operation_hours_excel_import_service import PartOperationHoursExcelImportService
    from core.services.process.part_service import PartService
    from core.services.process.supplier_excel_import_service import SupplierExcelImportService
    from core.services.scheduler import BatchService, CalendarService

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=None)

    conn = get_connection(test_db)
    try:
        op_type_svc = OpTypeService(conn)
        part_svc = PartService(conn)
        batch_svc = BatchService(conn)
        calendar_svc = CalendarService(conn)

        op_type_svc.create("OT_KEEP", "数车", "internal")
        part_svc.create("P001", "测试零件")
        part_svc.upsert_and_parse_no_tx("P_HOURS", "工时零件", "5数车")

        machine_import = MachineExcelImportService(conn)
        try:
            machine_import.apply_preview_rows(
                [
                    ImportPreviewRow(
                        row_num=2,
                        status=RowStatus.NEW,
                        data={"设备编号": "MC_FAIL", "设备名称": "失败设备", "工种": "不存在工种", "状态": "active"},
                        message="将新增",
                    )
                ],
                mode=ImportMode.OVERWRITE,
                existing_ids=set(),
            )
            raise RuntimeError("machine 应为硬失败整批回滚，但未抛出异常")
        except ValidationError:
            pass
        _assert_count(conn, "SELECT COUNT(1) FROM Machines WHERE machine_id = ?", ("MC_FAIL",), 0, "machine hard-fail")

        operator_import = OperatorExcelImportService(conn)
        try:
            operator_import.apply_preview_rows(
                [
                    ImportPreviewRow(
                        row_num=2,
                        status=RowStatus.NEW,
                        data={"工号": "OP_FAIL", "姓名": "失败人员", "状态": "在岗", "班组": "不存在班组"},
                        message="将新增",
                    )
                ],
                mode=ImportMode.OVERWRITE,
                existing_ids=set(),
            )
            raise RuntimeError("operator 应为硬失败整批回滚，但未抛出异常")
        except ValidationError:
            pass
        _assert_count(conn, "SELECT COUNT(1) FROM Operators WHERE operator_id = ?", ("OP_FAIL",), 0, "operator hard-fail")

        supplier_import = SupplierExcelImportService(conn)
        supplier_stats = supplier_import.apply_preview_rows(
            [
                ImportPreviewRow(
                    row_num=2,
                    status=RowStatus.NEW,
                    data={"供应商ID": "SUP_ROWERR", "名称": "按行计错供应商", "对应工种": "不存在工种", "默认周期": 2.0, "状态": "active"},
                    message="将新增",
                )
            ],
            mode=ImportMode.OVERWRITE,
            existing_ids=set(),
        )
        if int(supplier_stats.get("error_count", 0)) != 1 or int(supplier_stats.get("new_count", 0)) != 0:
            raise RuntimeError(f"supplier 应按行计错继续：{supplier_stats}")
        _assert_count(conn, "SELECT COUNT(1) FROM Suppliers WHERE supplier_id = ?", ("SUP_ROWERR",), 0, "supplier row-error")

        op_type_import = OpTypeExcelImportService(conn)
        op_type_stats = op_type_import.apply_preview_rows(
            [
                ImportPreviewRow(
                    row_num=2,
                    status=RowStatus.NEW,
                    data={"工种ID": "OT_BAD", "工种名称": "坏工种", "归属": "bad"},
                    message="将新增",
                )
            ],
            mode=ImportMode.OVERWRITE,
            existing_ids=set(),
        )
        if int(op_type_stats.get("error_count", 0)) != 1 or int(op_type_stats.get("new_count", 0)) != 0:
            raise RuntimeError(f"op_type 应按行计错继续：{op_type_stats}")
        _assert_count(conn, "SELECT COUNT(1) FROM OpTypes WHERE op_type_id = ?", ("OT_BAD",), 0, "op_type row-error")

        with patch.object(batch_svc, "create_no_tx", side_effect=ValidationError("模拟批次失败")):
            try:
                batch_svc.import_from_preview_rows(
                    preview_rows=[
                        ImportPreviewRow(
                            row_num=2,
                            status=RowStatus.NEW,
                            data={
                                "批次号": "B_FAIL",
                                "图号": "P001",
                                "数量": 1,
                                "交期": "2026-06-01",
                                "优先级": "normal",
                                "齐套": "yes",
                                "齐套日期": None,
                                "备注": "模拟批次失败",
                            },
                            message="将新增",
                        )
                    ],
                    mode=ImportMode.OVERWRITE,
                    parts_cache={"P001": part_svc.get("P001")},
                    auto_generate_ops=False,
                    existing_ids=set(),
                )
                raise RuntimeError("batch 当前合同应为硬失败，但未抛出异常")
            except ValidationError:
                pass
        _assert_count(conn, "SELECT COUNT(1) FROM Batches WHERE batch_id = ?", ("B_FAIL",), 0, "batch hard-fail")

        with patch.object(calendar_svc, "upsert_operator_calendar_no_tx", side_effect=ValidationError("模拟人员日历失败")):
            try:
                calendar_svc.import_operator_calendar_from_preview_rows(
                    preview_rows=[
                        ImportPreviewRow(
                            row_num=2,
                            status=RowStatus.NEW,
                            data={
                                "__id": "OPX|2026-06-01",
                                "工号": "OPX",
                                "日期": "2026-06-01",
                                "类型": "workday",
                                "班次开始": "08:00",
                                "班次结束": "17:00",
                                "可用工时": 8.0,
                                "效率": 1.0,
                                "允许普通件": "yes",
                                "允许急件": "yes",
                                "说明": "模拟人员日历失败",
                            },
                            message="将新增",
                        )
                    ],
                    mode=ImportMode.OVERWRITE,
                    existing_ids=set(),
                )
                raise RuntimeError("operator_calendar 当前合同应为硬失败，但未抛出异常")
            except ValidationError:
                pass

        part_hours_import = PartOperationHoursExcelImportService(conn)
        with patch.object(part_hours_import.part_svc, "update_internal_hours", side_effect=ValidationError("模拟工时失败")):
            part_hours_stats = part_hours_import.apply_preview_rows(
                [
                    ImportPreviewRow(
                        row_num=2,
                        status=RowStatus.UPDATE,
                        data={"图号": "P_HOURS", "工序": 5, "换型时间(h)": 1.0, "单件工时(h)": 0.5},
                        message="将更新",
                    )
                ]
            )
        if int(part_hours_stats.get("error_count", 0)) != 1 or int(part_hours_stats.get("update_count", 0)) != 0:
            raise RuntimeError(f"part_operation_hours 应按行计错继续：{part_hours_stats}")

        operator_machine_svc = OperatorMachineService(conn)
        operator_machine_stats = operator_machine_svc.apply_import_links(
            preview_rows=[
                ImportPreviewRow(
                    row_num=2,
                    status=RowStatus.NEW,
                    data={"工号": "OP_LINK", "设备编号": "MC_LINK", "技能等级": "bad", "主操设备": "yes"},
                    message="将新增",
                )
            ],
            mode=ImportMode.OVERWRITE,
        )
        if int(operator_machine_stats.get("error_count", 0)) != 1 or int(operator_machine_stats.get("new_count", 0)) != 0:
            raise RuntimeError(f"operator_machine 应按行计错继续：{operator_machine_stats}")
        _assert_count(
            conn,
            "SELECT COUNT(1) FROM OperatorMachine WHERE operator_id = ? AND machine_id = ?",
            ("OP_LINK", "MC_LINK"),
            0,
            "operator_machine row-error",
        )
    finally:
        conn.close()

    print("OK")


if __name__ == "__main__":
    main()
