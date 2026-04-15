from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

from flask import current_app, g, request, url_for

from core.infrastructure.backup import BackupManager
from core.infrastructure.errors import ValidationError
from core.infrastructure.logging import safe_log
from core.services.system.system_maintenance_service import _parse_db_dt


def _warn_invalid_next_url_once(*, raw: Optional[str], reason: str) -> None:
    warned = bool(getattr(g, "_aps_invalid_next_url_warned", False))
    if warned:
        return
    g._aps_invalid_next_url_warned = True
    path = str(request.path or "")
    safe_log(
        current_app.logger,
        "warning",
        "检测到非法 next 跳转参数，已回退到首页：reason=%s raw=%r path=%s",
        str(reason or "unknown"),
        raw,
        path,
    )


def _safe_next_url(raw: Optional[str]) -> str:
    """
    安全重定向：
    - 仅允许站内相对路径（禁止 http(s):// 或 //host 形式）
    - 兼容 request.full_path 末尾的 '?'（无查询时）
    - 空值统一回退到 dashboard 首页；非空非法值会记录 warning 后回退
    """
    s = (raw or "").strip()
    if not s:
        return url_for("dashboard.index")
    if s.endswith("?"):
        s = s[:-1]
    if s.startswith("//"):
        _warn_invalid_next_url_once(raw=raw, reason="protocol_relative")
        return url_for("dashboard.index")
    if any(ch in s for ch in ("\r", "\n", "\x00", "\\")):
        _warn_invalid_next_url_once(raw=raw, reason="control_or_backslash")
        return url_for("dashboard.index")
    try:
        p = urlparse(s)
        if p.scheme or p.netloc:
            _warn_invalid_next_url_once(raw=raw, reason="absolute_url")
            return url_for("dashboard.index")
    except Exception:
        _warn_invalid_next_url_once(raw=raw, reason="parse_failed")
        return url_for("dashboard.index")
    if not s.startswith("/"):
        s = "/" + s
    return s


def _parse_dt(value: str, field: str) -> Tuple[datetime, bool]:
    """
    解析时间参数：
    - 支持 YYYY-MM-DD / YYYY/MM/DD
    - 支持 YYYY-MM-DD HH:MM(:SS)
    - 支持 HTML datetime-local：YYYY-MM-DDTHH:MM(:SS)
    - 支持中文冒号：08：00
    返回：(dt, is_date_only)
    """
    v = (value or "").strip()
    if not v:
        raise ValidationError("时间不能为空", field=field)

    v = v.replace("/", "-").replace("T", " ").replace("：", ":")
    try:
        # 日期（允许月/日不补零）
        if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", v):
            return datetime.strptime(v, "%Y-%m-%d"), True
        # 时间（允许 HH:MM 或 HH:MM:SS，小时允许不补零）
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(v, fmt), False
            except Exception:
                continue
        raise ValueError("no fmt")
    except Exception as e:
        raise ValidationError("时间格式不正确，请按 2026-03-13、2026/03/13 或 2026-03-13 08:00:00 这样的格式填写。", field=field) from e


def _normalize_time_range(start_raw: Optional[str], end_raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    把查询参数标准化为 SQLite 兼容的字符串格式：
    - start：日期则取 00:00:00
    - end：日期则取 23:59:59
    """
    start_s = (start_raw or "").strip() or None
    end_s = (end_raw or "").strip() or None

    start_norm = None
    end_norm = None

    if start_s:
        dt, is_date_only = _parse_dt(start_s, field="开始时间")
        if is_date_only:
            dt = dt.replace(hour=0, minute=0, second=0)
        start_norm = dt.strftime("%Y-%m-%d %H:%M:%S")

    if end_s:
        dt, is_date_only = _parse_dt(end_s, field="结束时间")
        if is_date_only:
            dt = dt.replace(hour=23, minute=59, second=59)
        end_norm = dt.strftime("%Y-%m-%d %H:%M:%S")

    # 若两者都存在，校验 start <= end
    if start_norm and end_norm:
        try:
            if datetime.strptime(start_norm, "%Y-%m-%d %H:%M:%S") > datetime.strptime(end_norm, "%Y-%m-%d %H:%M:%S"):
                raise ValidationError("开始时间不能晚于结束时间。", field="开始时间")
        except ValidationError:
            raise
        except Exception:
            _ = None

    return start_norm, end_norm


def _safe_int(value: Optional[str], field: str, default: int, min_v: int, max_v: int) -> int:
    raw = (value or "").strip()
    if raw == "":
        return int(default)
    try:
        v = int(raw)
    except Exception as e:
        raise ValidationError(f"{field} 不合法（期望整数）", field=field) from e
    if v < min_v:
        return int(min_v)
    if v > max_v:
        return int(max_v)
    return v


_MISSING = object()


def _get_request_service(service_attr: str) -> Any:
    services = getattr(g, "services", None)
    if services is None:
        raise RuntimeError("请求上下文缺少 g.services。")
    attr_name = str(service_attr or "").strip()
    if not attr_name:
        raise RuntimeError("请求级服务名不能为空。")
    class_attr = getattr(type(services), attr_name, _MISSING)
    instance_attrs = getattr(services, "__dict__", {}) or {}
    if class_attr is _MISSING and attr_name not in instance_attrs:
        raise RuntimeError(f"g.services 缺少 {attr_name}。")
    try:
        svc = getattr(services, attr_name)
    except AttributeError as exc:
        raise RuntimeError(f"g.services 缺少 {attr_name}。") from exc
    if svc is None:
        raise RuntimeError(f"g.services 缺少 {attr_name}。")
    return svc


def _get_system_config_service():
    return _get_request_service("system_config_service")


def _get_schedule_history_query_service():
    return _get_request_service("schedule_history_query_service")


def _get_system_job_state_query_service():
    return _get_request_service("system_job_state_query_service")


def _get_operation_log_service():
    return _get_request_service("operation_log_service")


__all__ = [
    "_get_operation_log_service",
    "_get_request_service",
    "_get_schedule_history_query_service",
    "_get_system_config_service",
    "_get_system_job_state_query_service",
]


def _get_backup_manager(keep_days: Optional[int] = None) -> BackupManager:
    return BackupManager(
        db_path=current_app.config["DATABASE_PATH"],
        backup_dir=current_app.config["BACKUP_DIR"],
        keep_days=int(keep_days) if keep_days is not None else int(current_app.config.get("BACKUP_KEEP_DAYS", 7)),
        logger=current_app.logger,
    )


def _get_system_cfg_snapshot():
    svc = _get_system_config_service()
    return svc.get_snapshot(backup_keep_days_default=int(current_app.config.get("BACKUP_KEEP_DAYS", 7)))


def _get_job_state_map() -> Dict[str, Any]:
    q = _get_system_job_state_query_service()

    def _get(key: str) -> Optional[Dict[str, Any]]:
        it = q.get(key)
        if not it:
            return None
        d = it.to_dict()
        parsed = _parse_db_dt(d.get("last_run_time"))
        d["last_run_state"] = parsed.state
        d["last_run_raw"] = parsed.raw
        raw = d.get("last_run_detail")
        try:
            d["last_run_detail_obj"] = json.loads(raw) if raw else None
        except Exception:
            d["last_run_detail_obj"] = None
        return d

    return {
        "auto_backup": _get("auto_backup"),
        "auto_backup_cleanup": _get("auto_backup_cleanup"),
        "auto_log_cleanup": _get("auto_log_cleanup"),
    }


def _validate_backup_filename(filename: str) -> str:
    fn = (filename or "").strip()
    if not fn:
        raise ValidationError("请选择要恢复的备份文件。", field="filename")

    base = os.path.basename(fn)
    if base != fn:
        raise ValidationError("备份文件名不合法。", field="filename")

    if not base.startswith("aps_backup_") or not base.endswith(".db"):
        raise ValidationError("备份文件名不合法（仅允许 aps_backup_*.db）。", field="filename")

    return base

