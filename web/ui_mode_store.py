from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from flask import g, has_request_context

from web.ui_mode_request import UI_MODE_CONFIG_KEY, _log_warning, normalize_ui_mode

_G_KEY_INVALID_DB_UI_MODE_WARNED = "ui_mode_invalid_db_warned"


@dataclass(frozen=True)
class _UiModeDbReadResult:
    mode: Optional[str] = None
    missing: bool = False
    invalid_raw_value: Any = None


def _warn_invalid_db_ui_mode_once(raw_value: Any) -> None:
    if has_request_context():
        warned = bool(getattr(g, _G_KEY_INVALID_DB_UI_MODE_WARNED, False))
        if warned:
            return
        setattr(g, _G_KEY_INVALID_DB_UI_MODE_WARNED, True)
    _log_warning("UI 模式数据库配置非法，已回退默认值：%r", raw_value)


def _read_ui_mode_from_db() -> _UiModeDbReadResult:
    """
    从 SystemConfig 读取 ui_mode（v1/v2）。
    - 无请求上下文 / 无 DB / 无配置记录：返回缺失态
    - 非法值（包括空值）：返回非法态，由调用方决定如何告警并回退
    - 请求上下文结构损坏（已有 g.db，但缺少 g.services / system_config_service / 必需接口）：显式抛错
    - system_config_service 构造异常：显式抛错，避免把请求级容器损坏伪装成“配置缺失”
    - 配置读取异常：记录 warning，再回退默认值
    """
    if not has_request_context():
        return _UiModeDbReadResult(missing=True)
    conn = getattr(g, "db", None)
    if conn is None:
        return _UiModeDbReadResult(missing=True)
    services = getattr(g, "services", None)
    if services is None:
        raise RuntimeError("请求上下文已有 g.db，但缺少 g.services。")

    try:
        svc = services.system_config_service
    except AttributeError as exc:
        raise RuntimeError("g.services 缺少 system_config_service。") from exc
    except Exception as exc:
        raise RuntimeError("g.services.system_config_service 构造失败。") from exc

    if not callable(getattr(svc, "get_value_with_presence", None)):
        raise RuntimeError("g.services.system_config_service 缺少 get_value_with_presence 接口。")

    try:
        exists, raw_value = svc.get_value_with_presence(UI_MODE_CONFIG_KEY)
        if not exists:
            return _UiModeDbReadResult(missing=True)
    except Exception as exc:
        _log_warning("读取 UI 模式数据库配置失败，已回退默认值：%s", exc)
        return _UiModeDbReadResult(missing=True)
    if raw_value is None:
        return _UiModeDbReadResult(missing=False, invalid_raw_value=raw_value)

    mode = normalize_ui_mode(raw_value)
    if mode is None:
        return _UiModeDbReadResult(missing=False, invalid_raw_value=raw_value)
    return _UiModeDbReadResult(mode=mode)
