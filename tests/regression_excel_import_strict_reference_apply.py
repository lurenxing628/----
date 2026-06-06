"""回归测试：当 Excel 预览已通过但 apply 阶段引用的工种已被改名失效时，MachineExcelImportService.apply_preview_rows 整批抛 ValidationError（文案含「工种机加工不存在」）不写空设备记录；SupplierExcelImportService 则按行计 error_count=1、new_count/update_count 为 0 并给出错误样本，二者都不静默写入失效引用记录。"""

from core.infrastructure.database import get_connection
from core.infrastructure.errors import ValidationError
from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
from core.services.equipment.machine_excel_import_service import MachineExcelImportService
from core.services.process.op_type_service import OpTypeService
from core.services.process.supplier_excel_import_service import SupplierExcelImportService


def test_excel_import_strict_reference_apply(db_path) -> None:
    conn = get_connection(db_path)
    try:
        op_type_svc = OpTypeService(conn)
        op_type_svc.create("OT_M_STRICT", "机加工", "internal")
        op_type_svc.create("OT_S_STRICT", "外协工种", "external")
    finally:
        conn.close()

    # 1) 设备：apply 阶段工种失效，必须整批失败，且不得静默写空
    conn = get_connection(db_path)
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
    conn = get_connection(db_path)
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
