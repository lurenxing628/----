from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from flask import flash, g

from core.infrastructure.errors import AppError, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode, ImportPreviewRow, RowStatus
from core.services.process import PartService
from core.services.scheduler.batch_query_service import BatchQueryService

from .excel_utils import extract_import_stats, flash_import_result

RouteRowValidator = Callable[[Dict[str, Any]], Optional[str]]


@dataclass
class RouteImportApplyResult:
    total_rows: int
    new_count: int
    update_count: int
    skip_count: int
    error_count: int
    errors_sample: List[Dict[str, Any]]
    route_warnings_sample: List[Dict[str, Any]]
    route_warning_total: int

    def to_import_result(self) -> Dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "new_count": self.new_count,
            "update_count": self.update_count,
            "skip_count": self.skip_count,
            "error_count": self.error_count,
            "errors_sample": self.errors_sample,
        }


def preview_excel_route_rows(
    *,
    rows: List[Dict[str, Any]],
    existing: Dict[str, Dict[str, Any]],
    mode: ImportMode,
    validate_row: RouteRowValidator,
) -> List[ImportPreviewRow]:
    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    return excel_svc.preview_import(
        rows=rows,
        id_column="图号",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )


def _preview_row_location(pr: ImportPreviewRow) -> Dict[str, Any]:
    return {
        "row": getattr(pr, "source_row_num", None) or pr.row_num,
        "source_row_num": getattr(pr, "source_row_num", None),
        "source_sheet_name": getattr(pr, "source_sheet_name", None),
    }


def _append_error_sample(
    errors_sample: List[Dict[str, Any]],
    pr: ImportPreviewRow,
    message: str,
    *,
    limit: int = 10,
) -> None:
    if len(errors_sample) >= limit:
        return
    sample = _preview_row_location(pr)
    sample["message"] = message
    errors_sample.append(sample)


def _append_route_warning_sample(
    route_warnings_sample: List[Dict[str, Any]],
    pr: ImportPreviewRow,
    warning: Any,
    *,
    limit: int = 5,
) -> None:
    if len(route_warnings_sample) >= limit:
        return
    route_warnings_sample.append(
        {
            "row": getattr(pr, "source_row_num", None) or pr.row_num,
            "message": str(warning),
        }
    )


def apply_excel_route_preview_rows(
    *,
    part_svc: PartService,
    preview_rows: List[ImportPreviewRow],
    mode: ImportMode,
    strict_mode: bool,
    existing: Dict[str, Dict[str, Any]],
) -> RouteImportApplyResult:
    tx = TransactionManager(g.db)
    new_count = update_count = skip_count = error_count = 0
    errors_sample: List[Dict[str, Any]] = []
    route_warnings_sample: List[Dict[str, Any]] = []
    route_warning_total = 0

    with tx.transaction():
        if mode == ImportMode.REPLACE:
            batch_q = BatchQueryService(g.db, op_logger=getattr(g, "op_logger", None))
            if batch_q.has_any():
                raise ValidationError("已存在批次数据，不能执行“清空本类数据后重导”。请改用“更新已有，新增缺少”或“只导入新编号”。")
            part_svc.delete_all_no_tx()
            existing = {}

        for pr in preview_rows:
            if pr.status == RowStatus.ERROR:
                error_count += 1
                if pr.message:
                    _append_error_sample(errors_sample, pr, pr.message)
                continue
            if pr.status == RowStatus.SKIP:
                skip_count += 1
                continue
            if pr.status == RowStatus.UNCHANGED and mode != ImportMode.REPLACE:
                skip_count += 1
                continue

            pn = str(pr.data.get("图号")).strip()
            name = str(pr.data.get("名称")).strip()
            route_raw = str(pr.data.get("工艺路线字符串")).strip()

            if mode == ImportMode.APPEND and pn in existing:
                skip_count += 1
                continue

            try:
                existed = pn in existing
                parse_result = part_svc.upsert_and_parse_no_tx(
                    part_no=pn,
                    part_name=name,
                    route_raw=route_raw,
                    strict_mode=strict_mode,
                )
                for warning in getattr(parse_result, "warnings", None) or []:
                    route_warning_total += 1
                    _append_route_warning_sample(route_warnings_sample, pr, warning)
                if existed:
                    update_count += 1
                else:
                    new_count += 1
            except AppError as e:
                error_count += 1
                _append_error_sample(errors_sample, pr, e.message)
                continue

    return RouteImportApplyResult(
        total_rows=len(preview_rows),
        new_count=new_count,
        update_count=update_count,
        skip_count=skip_count,
        error_count=error_count,
        errors_sample=errors_sample,
        route_warnings_sample=route_warnings_sample,
        route_warning_total=route_warning_total,
    )


def flash_route_import_outcome(result: RouteImportApplyResult) -> None:
    new_count, update_count, skip_count, error_count = extract_import_stats(result.to_import_result())
    flash_import_result(
        new_count=new_count,
        update_count=update_count,
        skip_count=skip_count,
        error_count=error_count,
        errors_sample=result.errors_sample,
    )
    if result.route_warnings_sample:
        warning_text = "；".join(f"第 {item['row']} 行：{item['message']}" for item in result.route_warnings_sample)
        if result.route_warning_total > len(result.route_warnings_sample):
            warning_text += f"；还有 {result.route_warning_total - len(result.route_warnings_sample)} 条提示未显示"
        flash(f"导入完成，但有些工艺路线先按临时规则处理：{warning_text}。请补齐资料后重新导入，或让系统重新检查工艺路线。", "warning")
