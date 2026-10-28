"""BytesIO fixtures and explicit CommandService integration for material files."""

import csv
from datetime import datetime, timedelta
from io import BytesIO, StringIO

import openpyxl

from core.models.workbench_material_file import COLUMNS, HEADERS, MATERIAL_COLUMNS
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.material.bulk import WorkbenchMaterialBulkService
from core.services.workbench.material.files import WorkbenchMaterialFileService

KEY = "material-file-test-000001"


def file_bytes(rows, file_format, headers=HEADERS, *, formulas=False):
    if file_format == "csv":
        output = StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)
        return output.getvalue().encode("utf-8-sig")
    wb = openpyxl.Workbook()
    try:
        ws = wb.active
        ws.append(headers)
        for number, row in enumerate(rows, 2):
            for column, value in enumerate(row, 1):
                cell = ws.cell(number, column, value)
                if type(value) is str and not formulas:
                    cell.data_type = "s"
        output = BytesIO()
        wb.save(output)
        return output.getvalue()
    finally:
        wb.close()


def confirm_import(conn, preview, content, file_format, *, key=KEY, guard=None, command=None):
    return (command or WorkbenchCommandService(conn)).execute(
        request_key=key, action="material.import", context_ref="material.collection",
        normalized_input=preview.intent(), guard=guard or (lambda: None),
        mutate=lambda _: WorkbenchMaterialFileService(conn).confirm_import(preview, content, file_format=file_format, scope={}),
    )


def confirm_delete(conn, preview, refs, *, key=KEY, scope=None, guard=None, command=None):
    return (command or WorkbenchCommandService(conn)).execute(
        request_key=key, action="material.bulk_delete", context_ref="material.collection",
        normalized_input=preview.intent(), guard=guard or (lambda: None),
        mutate=lambda _: WorkbenchMaterialBulkService(conn).confirm_delete(preview, refs, scope=scope or {}),
    )


def _local_created_at(value):
    """独立预期：Materials.created_at 由数据库按 UTC 写入，导出文件里显示的是加 8 小时后的时刻。"""
    if value is None:
        return None
    return (datetime.strptime(str(value)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
            + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")


def codec_rows(rows):
    """编码器拿到的 created_at 已经由服务层换算过，直接喂编码器时要照同一口径准备。"""
    return (dict(zip(COLUMNS, (_local_created_at(row[key]) if key == "created_at" else row[key]
                               for key in MATERIAL_COLUMNS))) for row in rows)
