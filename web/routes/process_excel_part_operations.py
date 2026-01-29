from __future__ import annotations

import io
import time

from flask import g, send_file, url_for

from web.ui_mode import render_ui_template as render_template

from core.services.common.excel_audit import log_excel_export

from .process_bp import bp


# ============================================================
# Excel：零件工序模板导出（PartOperations）
# ============================================================


@bp.get("/excel/part-operations")
def excel_part_ops_page():
    return render_template(
        "process/excel_part_ops_export.html",
        title="零件工序模板 - Excel 导出",
        export_url=url_for("process.excel_part_ops_export"),
    )


@bp.get("/excel/part-operations/export")
def excel_part_ops_export():
    start = time.time()
    rows = g.db.execute(
        """
        SELECT
          p.part_no,
          po.seq,
          po.op_type_name,
          po.source,
          po.supplier_id,
          s.name AS supplier_name,
          po.ext_days,
          po.ext_group_id,
          eg.merge_mode,
          eg.total_days
        FROM PartOperations po
        JOIN Parts p ON p.part_no = po.part_no
        LEFT JOIN Suppliers s ON s.supplier_id = po.supplier_id
        LEFT JOIN ExternalGroups eg ON eg.group_id = po.ext_group_id
        WHERE po.status = 'active'
        ORDER BY p.part_no, po.seq
        """
    ).fetchall()

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["图号", "工序", "工种", "归属", "供应商", "周期"])
    for r in rows:
        supplier = r["supplier_name"] or ""
        days = None
        if r["source"] == "external":
            if r["merge_mode"] == "merged" and r["total_days"] is not None:
                days = r["total_days"]
            else:
                days = r["ext_days"]
        ws.append(
            [
                r["part_no"],
                r["seq"],
                r["op_type_name"],
                r["source"],
                supplier,
                days,
            ]
        )

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="part_operation",
        template_or_export_type="零件工序模板导出.xlsx",
        filters={},
        row_count=len(rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="零件工序模板.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

