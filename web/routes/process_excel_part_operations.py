from __future__ import annotations

import time

from flask import g, send_file, url_for

from core.models.enums import MergeMode, SourceType
from core.services.common.excel_audit import log_excel_export
from core.services.common.excel_templates import build_xlsx_bytes
from core.services.process.part_operation_query_service import PartOperationQueryService
from web.ui_mode import render_ui_template as render_template

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
    q = PartOperationQueryService(g.db, op_logger=getattr(g, "op_logger", None))
    rows = q.list_all_active_with_details()
    output = build_xlsx_bytes(
        ["图号", "工序", "工种", "归属", "供应商", "周期"],
        [
            [
                r["part_no"],
                r["seq"],
                r["op_type_name"],
                r["source"],
                r["supplier_name"] or "",
                r["total_days"] if r["source"] == SourceType.EXTERNAL.value and r["merge_mode"] == MergeMode.MERGED.value and r["total_days"] is not None else (r["ext_days"] if r["source"] == SourceType.EXTERNAL.value else None),
            ]
            for r in rows
        ],
        format_spec={
            "text_cols": [0, 2, 3, 4],
            "int_cols": [1],
            "float_cols": [5],
            "column_widths": {0: 14, 1: 10, 2: 14, 3: 12, 4: 16, 5: 10},
        },
        sanitize_formula=True,
    )

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

