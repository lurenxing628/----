from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from .excel_service import ImportMode, ImportPreviewRow, ImportResult, RowStatus


def _calc_stats_from_preview(preview_rows: List[ImportPreviewRow]) -> Dict[str, Any]:
    total_rows = len(preview_rows)
    new_count = sum(1 for r in preview_rows if r.status == RowStatus.NEW)
    update_count = sum(1 for r in preview_rows if r.status == RowStatus.UPDATE)
    skip_count = sum(1 for r in preview_rows if r.status == RowStatus.SKIP)
    error_count = sum(1 for r in preview_rows if r.status == RowStatus.ERROR)

    errors_sample = [
        {"row": r.row_num, "message": r.message}
        for r in preview_rows
        if r.status == RowStatus.ERROR and r.message
    ][:10]

    return {
        "total_rows": total_rows,
        "new_count": new_count,
        "update_count": update_count,
        "skip_count": skip_count,
        "error_count": error_count,
        "errors_sample": errors_sample,
    }


def log_excel_import(
    op_logger,
    module: str,
    target_type: str,
    filename: str,
    mode: Union[ImportMode, str],
    preview_or_result: Union[List[ImportPreviewRow], ImportResult, Dict[str, Any], None],
    time_cost_ms: int,
    errors_sample: Optional[List[Dict[str, Any]]] = None,
    file_hash: Optional[str] = None,
    target_id: Optional[str] = None,
) -> None:
    """
    Excel 导入留痕（OperationLogs.action=import）。

    注意：detail 字段键名必须按文档固定（英文键），便于后续统一报表/审计。
    """
    if op_logger is None:
        return

    if isinstance(mode, ImportMode):
        mode_value = mode.value
    else:
        mode_value = str(mode)

    detail: Dict[str, Any] = {
        "filename": filename,
        "mode": mode_value,
        "time_cost_ms": int(time_cost_ms) if time_cost_ms is not None else None,
    }
    if file_hash:
        detail["file_hash"] = file_hash

    if isinstance(preview_or_result, list):
        detail.update(_calc_stats_from_preview(preview_or_result))
    elif isinstance(preview_or_result, ImportResult):
        detail.update(
            {
                "total_rows": preview_or_result.total,
                "new_count": preview_or_result.new_count,
                "update_count": preview_or_result.update_count,
                "skip_count": preview_or_result.skip_count,
                "error_count": preview_or_result.error_count,
                "errors_sample": (preview_or_result.errors or [])[:10],
            }
        )
    elif isinstance(preview_or_result, dict):
        # 允许上层直接传入已计算的统计（需确保键名一致）
        detail.update(preview_or_result)

    if errors_sample is not None:
        # 明确传入优先，截断到前10条
        detail["errors_sample"] = errors_sample[:10]

    op_logger.info(
        module=module,
        action="import",
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )


def log_excel_export(
    op_logger,
    module: str,
    target_type: str,
    template_or_export_type: str,
    filters: Optional[Dict[str, Any]],
    row_count: int,
    time_range: Optional[Dict[str, Any]],
    time_cost_ms: int,
    target_id: Optional[str] = None,
) -> None:
    """
    Excel 导出留痕（OperationLogs.action=export）。
    """
    if op_logger is None:
        return

    detail: Dict[str, Any] = {
        "template_or_export_type": template_or_export_type,
        "filters": filters or {},
        "row_count": int(row_count) if row_count is not None else 0,
        "time_range": time_range or {},
        "time_cost_ms": int(time_cost_ms) if time_cost_ms is not None else None,
    }

    op_logger.info(
        module=module,
        action="export",
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )

