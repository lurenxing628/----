from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, flash, send_file

from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ImportMode, RowStatus

XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def parse_import_mode(value: str) -> ImportMode:
    """
    解析导入模式（字符串 -> ImportMode）。
    - 保持与各模块历史行为一致：非法值统一抛 ValidationError
    """
    try:
        return ImportMode(value)
    except Exception as e:
        raise ValidationError("导入模式不合法", field="mode") from e


def build_preview_baseline_token(
    *,
    existing_data: Dict[str, Dict[str, Any]],
    mode: ImportMode,
    id_column: str,
    extra_state: Any = None,
) -> str:
    """
    生成预览基线签名：
    - 绑定导入模式 + 主键列 + 当前 existing 快照
    - confirm 阶段若签名不一致，说明 preview 基线已变化，必须重新预览
    """
    payload = {
        "mode": str(getattr(mode, "value", mode) or "").strip(),
        "id_column": str(id_column or "").strip(),
        "existing_data": existing_data or {},
        "extra_state": extra_state if extra_state is not None else {},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def preview_baseline_matches(
    token: str,
    *,
    existing_data: Dict[str, Dict[str, Any]],
    mode: ImportMode,
    id_column: str,
    extra_state: Any = None,
) -> bool:
    """
    校验客户端回传的预览基线签名是否与当前数据库快照一致。
    """
    provided = (token or "").strip()
    if not provided:
        return False
    expected = build_preview_baseline_token(
        existing_data=existing_data,
        mode=mode,
        id_column=id_column,
        extra_state=extra_state,
    )
    try:
        return hmac.compare_digest(provided, expected)
    except Exception:
        current_app.logger.exception("预览基线签名比较失败")
        return False


@dataclass(frozen=True)
class ConfirmPayload:
    rows: List[Dict[str, Any]]
    preview_baseline: str


def parse_preview_rows_json(raw_rows_json: str) -> List[Dict[str, Any]]:
    try:
        rows = json.loads(raw_rows_json)
        if not isinstance(rows, list):
            raise ValueError("rows not list")
        return rows
    except Exception as e:
        raise ValidationError("预览数据解析失败，请重新上传并预览。") from e


def _extract_error_rows(preview_rows: List[Any]) -> List[Any]:
    return [pr for pr in (preview_rows or []) if getattr(pr, "status", None) == RowStatus.ERROR]


def _format_error_sample(error_rows: List[Any]) -> str:
    items = [
        f"第{(getattr(pr, 'source_row_num', None) or pr.row_num)}行：{pr.message}"
        for pr in (error_rows or [])[:5]
        if pr and getattr(pr, "message", None)
    ]
    return "；".join(items)


def strict_mode_enabled(raw_value: Any) -> bool:
    return str(raw_value or "").strip().lower() in {"1", "y", "yes", "true", "on"}


def load_confirm_payload(
    raw_rows_json: Optional[str],
    preview_baseline: Optional[str],
) -> ConfirmPayload:
    if not raw_rows_json:
        raise ValidationError("缺少预览数据，请重新上传并预览后再确认导入。")
    token = str(preview_baseline or "").strip()
    if not token:
        raise ValidationError("缺少预览基线，请重新上传并预览后再确认导入。")
    return ConfirmPayload(rows=parse_preview_rows_json(raw_rows_json), preview_baseline=token)


def preview_baseline_is_stale(
    preview_baseline: str,
    *,
    existing_data: Dict[str, Dict[str, Any]],
    mode: ImportMode,
    id_column: str,
    extra_state: Any = None,
) -> bool:
    return not preview_baseline_matches(
        preview_baseline,
        existing_data=existing_data,
        mode=mode,
        id_column=id_column,
        extra_state=extra_state,
    )


def collect_error_rows(preview_rows: List[Any]) -> List[Any]:
    return _extract_error_rows(preview_rows)


def build_error_rows_message(error_rows: List[Any]) -> str:
    message = f"导入被拒绝：Excel 存在 {len(error_rows)} 行错误。请修正后重新预览并确认。"
    sample = _format_error_sample(error_rows)
    if sample:
        message += f"错误示例：{sample}"
    return message


def extract_import_stats(import_stats: Dict[str, Any]) -> Tuple[int, int, int, int]:
    return (
        int(import_stats.get("new_count", 0) or 0),
        int(import_stats.get("update_count", 0) or 0),
        int(import_stats.get("skip_count", 0) or 0),
        int(import_stats.get("error_count", 0) or 0),
    )


def flash_import_result(
    *,
    new_count: int,
    update_count: int,
    skip_count: int,
    error_count: int,
    errors_sample: Optional[List[Dict[str, Any]]] = None,
    suffix: str = "",
) -> None:
    """统一导入完成提示：有错误用 warning，无错误用 success。"""
    if int(error_count or 0) > 0:
        sample = "；".join(
            [
                f"第{item.get('row')}行：{item.get('message')}"
                for item in list(errors_sample or [])[:3]
                if item and item.get("message")
            ]
        )
        message = f"导入部分完成：新增 {new_count}，更新 {update_count}，跳过 {skip_count}，错误 {error_count}。"
        if sample:
            message += f"错误示例：{sample}"
        if suffix:
            message += suffix
        flash(message, "warning")
        return
    message = f"导入完成：新增 {new_count}，更新 {update_count}，跳过 {skip_count}，错误 {error_count}。"
    if suffix:
        message += suffix
    flash(message, "success")


def ensure_unique_ids(rows: List[Dict[str, Any]], id_column: str) -> None:
    """
    Excel 主键去重校验：
    - 行内该列为空则跳过
    - 存在重复则抛 ValidationError（文案保持稳定）
    """
    seen = set()
    dup = set()
    for r in rows:
        v = r.get(id_column)
        if v is None:
            continue
        if isinstance(v, float) and v.is_integer():
            key = str(int(v)).strip()
        else:
            key = str(v).strip()
        if not key:
            continue
        if key in seen:
            dup.add(key)
        seen.add(key)
    if dup:
        sample = ", ".join(list(sorted(dup))[:10])
        raise ValidationError(f"Excel 中存在重复的“{id_column}”：{sample}。请去重后再导入。", field=id_column)


def read_uploaded_xlsx(file_storage) -> List[Dict[str, Any]]:
    """
    把上传的 Excel（.xlsx）解析为 List[Dict]（key 为表头字符串）。
    - 跳过空行
    - 单元格字符串自动 strip；空串视为 None
    - 统一走 backend.read(file_path)，以支持可选 pandas 后端
    """
    data = file_storage.read()
    if not data:
        raise AppError(ErrorCode.EXCEL_FORMAT_ERROR, "上传文件为空，请重新选择。")
    max_bytes = int(current_app.config.get("EXCEL_MAX_UPLOAD_BYTES") or current_app.config.get("MAX_CONTENT_LENGTH") or 0)
    if max_bytes > 0 and len(data) > max_bytes:
        raise AppError(
            ErrorCode.FILE_TOO_LARGE,
            f"上传文件超过 {max_bytes // (1024 * 1024)}MB，请缩小文件后重试。",
        )

    fd, tmp_path = tempfile.mkstemp(prefix="aps_upload_", suffix=".xlsx")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        backend = get_excel_backend()
        return backend.read(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def send_excel_template_file(
    template_path: str,
    *,
    download_name: str,
    mimetype: str = XLSX_MIMETYPE,
):
    return send_file(
        io.BytesIO(Path(template_path).read_bytes()),
        as_attachment=True,
        download_name=download_name,
        mimetype=mimetype,
    )

