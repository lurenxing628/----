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

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_excel_strict_ref_")
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
    from core.services.process.op_type_service import OpTypeService
    from core.services.process.supplier_excel_import_service import SupplierExcelImportService

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=None)

    conn = get_connection(test_db)
    try:
        op_type_svc = OpTypeService(conn)
        op_type_svc.create("OT_M_STRICT", "机加工", "internal")
        op_type_svc.create("OT_S_STRICT", "外协工种", "external")
    finally:
        conn.close()

    # 1) 设备：apply 阶段工种失效，必须整批失败，且不得静默写空
    conn = get_connection(test_db)
    try:
        OpTypeService(conn).update("OT_M_STRICT", name="机加工-已改名")
        svc = MachineExcelImportService(conn)
        try:
            svc.apply_preview_rows(
                [
                    ImportPreviewRow(
                        row_num=2,
                        status=RowStatus.NEW,
                        data={
                            "设备编号": "MC_STRICT",
                            "设备名称": "严格设备",
                            "工种": "机加工",
                            "状态": "active",
                        },
                        message="preview-passed",
                    )
                ],
                mode=ImportMode.OVERWRITE,
                existing_ids=set(),
            )
            raise RuntimeError("设备 apply 阶段在工种失效后应抛出 ValidationError")
        except ValidationError as e:
            if "工种机加工不存在" not in e.message:
                raise RuntimeError(f"设备错误文案不符合预期：{e.message}")

        cnt = conn.execute("SELECT COUNT(1) FROM Machines WHERE machine_id=?", ("MC_STRICT",)).fetchone()[0]
        if int(cnt) != 0:
            raise RuntimeError(f"设备严格引用失效后不应写入记录，实际数量={cnt}")
    finally:
        conn.close()

    # 2) 供应商：apply 阶段工种失效，应按行计错继续，但不得静默写空
    conn = get_connection(test_db)
    try:
        OpTypeService(conn).update("OT_S_STRICT", name="外协工种-已改名")
        svc = SupplierExcelImportService(conn)
        stats = svc.apply_preview_rows(
            [
                ImportPreviewRow(
                    row_num=2,
                    status=RowStatus.NEW,
                    data={
                        "供应商ID": "SUP_STRICT",
                        "名称": "严格供应商",
                        "对应工种": "外协工种",
                        "默认周期": 2.5,
                        "状态": "active",
                        "备注": "stale-preview",
                    },
                    message="preview-passed",
                )
            ],
            mode=ImportMode.OVERWRITE,
            existing_ids=set(),
        )
        if int(stats.get("error_count", 0)) != 1:
            raise RuntimeError(f"供应商严格引用失效后应计入 1 条错误，实际={stats}")
        if int(stats.get("new_count", 0)) != 0 or int(stats.get("update_count", 0)) != 0:
            raise RuntimeError(f"供应商严格引用失效后不应写入新增/更新，实际={stats}")
        sample = list(stats.get("errors_sample") or [])
        if not sample or "工种“外协工种”不存在" not in str(sample[0].get("message") or ""):
            raise RuntimeError(f"供应商错误样本不符合预期：{sample}")

        cnt = conn.execute("SELECT COUNT(1) FROM Suppliers WHERE supplier_id=?", ("SUP_STRICT",)).fetchone()[0]
        if int(cnt) != 0:
            raise RuntimeError(f"供应商严格引用失效后不应写入记录，实际数量={cnt}")
    finally:
        conn.close()

    print("OK")


if __name__ == "__main__":
    main()
