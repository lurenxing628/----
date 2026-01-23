from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.services.common.excel_service import ImportMode


def _parse_mode(value: str) -> ImportMode:
    try:
        return ImportMode(value)
    except Exception:
        raise ValidationError("导入模式不合法", field="mode")


def _ensure_unique_ids(rows: List[Dict[str, Any]], id_column: str) -> None:
    seen = set()
    dup = set()
    for r in rows:
        v = r.get(id_column)
        if v is None:
            continue
        key = str(v).strip()
        if not key:
            continue
        if key in seen:
            dup.add(key)
        seen.add(key)
    if dup:
        sample = ", ".join(list(sorted(dup))[:10])
        raise ValidationError(f"Excel 中存在重复的“{id_column}”：{sample}。请去重后再导入。", field=id_column)


def _read_uploaded_xlsx(file_storage) -> List[Dict[str, Any]]:
    """
    把上传的 Excel（.xlsx）解析为 List[Dict]（key 为表头字符串）。
    - 跳过空行
    - 单元格字符串自动 strip；空串视为 None
    """
    data = file_storage.read()
    if not data:
        raise AppError(ErrorCode.EXCEL_FORMAT_ERROR, "上传文件为空，请重新选择。")

    import openpyxl

    tmp = io.BytesIO(data)
    tmp.seek(0)

    try:
        wb = openpyxl.load_workbook(tmp, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []

        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        parsed_rows: List[Dict[str, Any]] = []
        for raw in rows[1:]:
            if raw is None or all(v is None or str(v).strip() == "" for v in raw):
                continue
            item: Dict[str, Any] = {}
            for idx, key in enumerate(headers):
                if not key:
                    continue
                val = raw[idx] if idx < len(raw) else None
                if isinstance(val, str):
                    val = val.strip()
                    if val == "":
                        val = None
                item[key] = val
            parsed_rows.append(item)
        return parsed_rows
    except AppError:
        raise
    except Exception as e:
        raise AppError(ErrorCode.EXCEL_READ_ERROR, "读取 Excel 失败，请确认文件未损坏且未被占用。", cause=e)


# -------------------------
# 批次 Excel 标准化
# -------------------------


def _normalize_batch_priority(value: Any) -> str:
    v = "" if value is None else str(value).strip()
    if v in ("普通", "normal"):
        return "normal"
    if v in ("急", "急件", "urgent"):
        return "urgent"
    if v in ("特急", "critical"):
        return "critical"
    return v or "normal"


def _normalize_ready_status(value: Any) -> str:
    v = "" if value is None else str(value).strip()
    if v in ("齐套", "是", "yes"):
        return "yes"
    if v in ("部分齐套", "partial"):
        return "partial"
    if v in ("未齐套", "否", "no"):
        return "no"
    # V1.1：齐套默认视为 yes（可缺省）
    return v or "yes"


def _normalize_due_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip().replace("/", "-")
        return v if v else None
    # datetime/date
    try:
        return value.date().isoformat() if hasattr(value, "date") else str(value)
    except Exception:
        return str(value)


# -------------------------
# 日历 Excel 标准化
# -------------------------


def _normalize_day_type(value: Any) -> str:
    v = "" if value is None else str(value).strip()
    if v in ("工作日", "workday"):
        return "workday"
    if v in ("周末", "weekend"):
        return "weekend"
    if v in ("节假日", "假期", "holiday"):
        return "holiday"
    return v or "workday"


def _normalize_yesno(value: Any) -> str:
    v = "" if value is None else str(value).strip()
    if v in ("是", "y", "Y", "yes", "YES"):
        return "yes"
    if v in ("否", "n", "N", "no", "NO"):
        return "no"
    return v or "yes"


def _normalize_calendar_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip().replace("/", "-")
    try:
        # datetime/date
        return value.date().isoformat() if hasattr(value, "date") else str(value)
    except Exception:
        return str(value)

