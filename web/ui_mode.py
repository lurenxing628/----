from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from flask import Blueprint, current_app, g, has_request_context, request, url_for
from jinja2 import ChoiceLoader, FileSystemLoader
from werkzeug.routing.exceptions import BuildError

from core.infrastructure.logging import safe_log
from web.bootstrap.static_versioning import EXT_KEY_TEMPLATE_URL_FOR
from web.viewmodels.page_manuals import build_manual_for_endpoint, resolve_manual_id

# -------------------------
# Constants
# -------------------------

UI_MODE_COOKIE_KEY = "aps_ui_mode"
UI_MODE_CONFIG_KEY = "ui_mode"  # stored in SystemConfig
# 默认 UI：优先启用 V2（新 UI）
DEFAULT_UI_MODE = "v2"
VALID_UI_MODES = ("v1", "v2")

_EXT_KEY_V2_ENV = "ui_mode.v2_env"
_EXT_KEY_V2_TEMPLATE_DIR = "ui_mode.v2_templates_dir"
_EXT_KEY_V2_RENDER_FALLBACK_WARNED = "ui_mode.v2_render_fallback_warned"
_BP_NAME_V2_STATIC = "ui_v2_static"

_G_KEY_INVALID_DB_UI_MODE_WARNED = "ui_mode_invalid_db_warned"


@dataclass(frozen=True)
class _UiModeDbReadResult:
    mode: Optional[str] = None
    missing: bool = False
    invalid_raw_value: Any = None


def normalize_ui_mode(value: Any) -> Optional[str]:
    v = ("" if value is None else str(value)).strip().lower()
    return v if v in VALID_UI_MODES else None


def _log_warning(message: str, *args: Any) -> None:
    try:
        current_app.logger.warning(message, *args)
    except Exception:
        pass


def _log_startup_warning(app, message: str, *args: Any) -> None:
    safe_log(getattr(app, "logger", None), "warning", message, *args)


def _warn_invalid_db_ui_mode_once(raw_value: Any) -> None:
    if has_request_context():
        warned = bool(getattr(g, _G_KEY_INVALID_DB_UI_MODE_WARNED, False))
        if warned:
            return
        setattr(g, _G_KEY_INVALID_DB_UI_MODE_WARNED, True)
    _log_warning("UI 模式数据库配置非法，已回退默认值：%r", raw_value)


def _resolve_manual_endpoint(endpoint: Any = None) -> str:
    if endpoint is not None:
        return str(endpoint).strip()
    if not has_request_context():
        return ""
    try:
        return str(request.endpoint or "").strip()
    except Exception:
        return ""


def _normalize_relative_manual_src(text: str) -> Optional[str]:
    if not text or not text.startswith("/") or text.startswith("//"):
        return None
    if any(ch in text for ch in ("\r", "\n", "\x00", "\\")):
        return None
    try:
        parts = urlsplit(text)
    except Exception:
        return None
    if parts.scheme or parts.netloc or not parts.path.startswith("/"):
        return None
    return text


def _same_origin_absolute_manual_src(raw: Any = None) -> Optional[str]:
    if not has_request_context():
        return None
    text = ("" if raw is None else str(raw)).strip()
    if not text or any(ch in text for ch in ("\r", "\n", "\x00", "\\")):
        return None
    try:
        parsed = urlsplit(text)
        current = urlsplit(str(request.host_url or ""))
    except Exception:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    if parsed.scheme != current.scheme or parsed.netloc != current.netloc:
        return None

    candidate = parsed.path or "/"
    if parsed.query:
        candidate = f"{candidate}?{parsed.query}"
    elif text.endswith("?"):
        candidate = f"{candidate}?"
    if parsed.fragment:
        candidate = f"{candidate}#{parsed.fragment}"
    return _normalize_relative_manual_src(candidate)


def normalize_manual_src(raw: Any = None) -> Optional[str]:
    text = ("" if raw is None else str(raw)).strip()
    return _normalize_relative_manual_src(text) or _same_origin_absolute_manual_src(text)


def _resolve_manual_src(src: Any = None) -> str:
    if src is not None:
        return str(src)
    if not has_request_context():
        return "/"
    try:
        full_path = getattr(request, "full_path", "") or ""
        if full_path:
            return str(full_path)
    except Exception:
        pass
    try:
        return str(getattr(request, "path", "") or "/")
    except Exception:
        return "/"


def get_manual_url(endpoint: Any = None, src: Any = None) -> Optional[str]:
    current_endpoint = _resolve_manual_endpoint(endpoint)
    if not current_endpoint or resolve_manual_id(current_endpoint) is None:
        return None
    safe_src = normalize_manual_src(_resolve_manual_src(src))
    return safe_url_for("scheduler.config_manual_page", page=current_endpoint, src=safe_src)


def get_full_manual_section_url(endpoint: Any = None, src: Any = None) -> str:
    current_endpoint = _resolve_manual_endpoint(endpoint)
    if not current_endpoint:
        return ""
    manual = build_manual_for_endpoint(current_endpoint, include_sections=False)
    if not manual:
        return ""
    safe_src = normalize_manual_src(_resolve_manual_src(src))
    base_url = safe_url_for("scheduler.config_manual_page", src=safe_src)
    if not base_url:
        return ""
    anchor = str(manual.get("full_manual_anchor") or "").strip()
    return base_url + anchor if anchor else base_url


def get_help_card(endpoint: Any = None, src: Any = None) -> Optional[Dict[str, Any]]:
    current_endpoint = _resolve_manual_endpoint(endpoint)
    if not current_endpoint:
        return None
    manual = build_manual_for_endpoint(current_endpoint, include_sections=False)
    if not manual:
        return None
    help_card = manual.get("help_card")
    if not help_card:
        return None
    return {
        "title": str(help_card.get("title") or "").strip(),
        "items": list(help_card.get("items") or []),
        "manual_url": get_manual_url(endpoint=current_endpoint, src=src),
    }


def init_ui_mode(app, base_dir: str) -> None:
    """
    初始化 UI 模式能力：
    - 注册 V2 静态资源：/static-v2 -> web_new_test/static
    - 创建 V2 Jinja overlay env：优先 web_new_test/templates，其次回退到现有 loader

    约束：只使用现有 Flask/Jinja2（Win7/Python3.8 兼容），不引入新依赖。
    """
    # ---- V2 static blueprint ----
    v2_static_dir = os.path.join(str(base_dir), "web_new_test", "static")
    if _BP_NAME_V2_STATIC not in app.blueprints:
        bp_static = Blueprint(
            _BP_NAME_V2_STATIC,
            __name__,
            # 说明：即使目录缺失也要注册 endpoint，避免模板 url_for() 直接 BuildError；
            # 缺文件时静态请求会自然返回 404（更易排障/更温和的失败方式）。
            static_folder=v2_static_dir,
            static_url_path="/static-v2",
        )
        app.register_blueprint(bp_static)
        if not os.path.isdir(v2_static_dir):
            _log_startup_warning(app, "V2 静态目录不存在：%s（/static-v2 将返回 404；请检查打包 add-data）", v2_static_dir)

    # ---- V2 jinja overlay ----
    v2_templates_dir = os.path.join(str(base_dir), "web_new_test", "templates")
    app.extensions[_EXT_KEY_V2_TEMPLATE_DIR] = os.path.normcase(os.path.abspath(v2_templates_dir))
    try:
        base_loader = app.jinja_loader
        v2_loader = FileSystemLoader(v2_templates_dir)
        # V2 优先，其次回退现有 loader（V1 + 蓝图 templates）
        overlay_loader = ChoiceLoader([v2_loader, base_loader] if base_loader is not None else [v2_loader])
        v2_env = app.jinja_env.overlay(loader=overlay_loader)
        app.extensions[_EXT_KEY_V2_ENV] = v2_env
    except Exception as e:
        # 不阻断启动：V2 env 创建失败则回退到 V1
        _log_startup_warning(app, "初始化 V2 Jinja 环境失败（将回退 V1）：%s", e)
        app.extensions[_EXT_KEY_V2_ENV] = None
    app.extensions.setdefault(_EXT_KEY_V2_RENDER_FALLBACK_WARNED, False)

    # 启动期即向 V1/V2 两套模板环境注入 safe_url_for，
    # 兼容直接使用 Flask render_template 的路径以及 import 宏场景。
    try:
        app.jinja_env.globals.setdefault("safe_url_for", safe_url_for)
        app.jinja_env.globals["get_help_card"] = get_help_card
        app.jinja_env.globals["get_manual_url"] = get_manual_url
        app.jinja_env.globals["get_full_manual_section_url"] = get_full_manual_section_url
    except Exception as exc:
        _log_startup_warning(
            app, "初始化主模板环境全局函数注入失败：%s；不带 with context 的模板宏将依赖后续渲染期二次注入。", exc
        )
    try:
        v2_env = app.extensions.get(_EXT_KEY_V2_ENV)
        if v2_env is not None:
            v2_env.globals.setdefault("safe_url_for", safe_url_for)
            v2_env.globals["get_help_card"] = get_help_card
            v2_env.globals["get_manual_url"] = get_manual_url
            v2_env.globals["get_full_manual_section_url"] = get_full_manual_section_url
    except Exception as exc:
        _log_startup_warning(app, "初始化 V2 模板环境全局函数注入失败：%s；V2 overlay 将依赖后续渲染期桥接继续工作。", exc)


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


def get_ui_mode(default: str = DEFAULT_UI_MODE) -> str:
    """
    获取当前 UI 模式：
    - Cookie 优先（浏览器级）
    - 其次 DB SystemConfig（全局默认）
    - 最后 default（兜底）
    """
    d = normalize_ui_mode(default) or DEFAULT_UI_MODE
    if not has_request_context():
        return d

    # 1) Cookie
    try:
        cookie_mode = normalize_ui_mode(request.cookies.get(UI_MODE_COOKIE_KEY))
        if cookie_mode:
            return cookie_mode
    except Exception as exc:
        _log_warning("读取 UI 模式 cookie 失败，已回退到数据库/默认值：%s", exc)

    # 2) DB
    db_read = _read_ui_mode_from_db()
    if db_read.mode:
        return db_read.mode
    if not db_read.missing:
        _warn_invalid_db_ui_mode_once(db_read.invalid_raw_value)

    return d


def _get_v2_env(app) -> Any:
    env = app.extensions.get(_EXT_KEY_V2_ENV)
    return env


def _describe_template_name(template_name_or_list: Any) -> str:
    if isinstance(template_name_or_list, str):
        return template_name_or_list
    try:
        return ", ".join([str(item) for item in list(template_name_or_list)])
    except Exception:
        return str(template_name_or_list)


def _warn_v2_render_fallback_once(app, *, template_name_or_list: Any, reason: str) -> None:
    warned = bool(app.extensions.get(_EXT_KEY_V2_RENDER_FALLBACK_WARNED))
    if warned:
        return
    app.extensions[_EXT_KEY_V2_RENDER_FALLBACK_WARNED] = True
    try:
        path = str(getattr(request, "path", "") or "") if has_request_context() else ""
    except Exception:
        path = ""
    try:
        app.logger.warning(
            "检测到 V2 模板运行期回退：%s（template=%s, path=%s）。"
            "可能原因：未重新打包 / overlay 创建失败 / V2 单页模板缺失 / 运行旧版本。",
            str(reason or "").strip() or "mode=v2 but v2 fallback triggered",
            _describe_template_name(template_name_or_list),
            path,
        )
    except Exception:
        pass


def _resolve_template_source(app, *, mode: str, template: Any, v2_env_missing: bool) -> str:
    if str(mode or "").strip().lower() != "v2":
        return "base"
    if v2_env_missing:
        return "base_fallback"

    filename = str(getattr(template, "filename", "") or "").strip()
    if not filename:
        return "v2"

    try:
        normalized_filename = os.path.normcase(os.path.abspath(filename))
    except Exception:
        return "v2"

    v2_root = str(app.extensions.get(_EXT_KEY_V2_TEMPLATE_DIR) or "").strip()
    if v2_root and (normalized_filename == v2_root or normalized_filename.startswith(v2_root + os.sep)):
        return "v2"
    return "base_fallback"


def safe_url_for(endpoint: str, **values: Any) -> Optional[str]:
    """
    url_for 的安全封装：
    - endpoint 不存在（BuildError）时返回 None（而不是抛异常导致整页 500）
    - 其他异常记录 warning 后返回 None（保持页面可用，便于排障/渐进发布）
    """
    if not has_request_context():
        return None
    try:
        return url_for(endpoint, **values)
    except BuildError:
        # 可观测性：记录 warning，但不要让整页 500
        try:
            # 每请求每 endpoint 仅记录一次，避免日志刷屏
            logged = getattr(g, "_safe_url_for_missing_eps", None)
            if logged is None:
                logged = set()
                g._safe_url_for_missing_eps = logged
            if endpoint not in logged:
                logged.add(endpoint)
                path = ""
                try:
                    path = getattr(request, "path", "") or ""
                except Exception:
                    path = ""
                _log_warning(
                    "模板链接不可用：endpoint 未注册（%s），path=%s。可能原因：运行旧版本/未重启/未重新打包。",
                    endpoint,
                    path,
                )
        except Exception:
            pass
        return None
    except Exception as exc:
        path = ""
        try:
            path = getattr(request, "path", "") or ""
        except Exception:
            path = ""
        _log_warning("模板链接构建失败：endpoint=%s，path=%s，error=%s", endpoint, path, exc)
        return None


def _resolve_template_url_for():
    try:
        app = current_app
        custom = app.extensions.get(EXT_KEY_TEMPLATE_URL_FOR)
        if callable(custom):
            return custom
    except Exception:
        pass
    return url_for


def render_ui_template(template_name_or_list, **context: Any) -> str:
    """
    render_template 的兼容封装：
    - 根据 ui_mode 选择 V1/V2 的 Jinja env
    - 注入 ui_mode 到模板上下文
    """
    app = current_app
    mode = get_ui_mode()

    # 保证模板里能直接用 ui_mode
    context.setdefault("ui_mode", mode)
    try:
        g.ui_mode = mode
    except Exception:
        pass

    # 复用 Flask 的上下文处理器（request/g/session/url_for 等）
    app.update_template_context(context)
    template_url_for = _resolve_template_url_for()
    context["url_for"] = template_url_for

    # 注入：模板可用的安全 url_for（可用于可选功能链接/灰度发布）
    context.setdefault("safe_url_for", safe_url_for)
    context.setdefault("get_help_card", get_help_card)
    context.setdefault("get_manual_url", get_manual_url)
    context.setdefault("get_full_manual_section_url", get_full_manual_section_url)

    if mode == "v2":
        v2_env = _get_v2_env(app)
        if v2_env is None:
            env = app.jinja_env
            ui_template_env = "v1_fallback"
            ui_template_env_degraded = True
            v2_env_missing = True
        else:
            env = v2_env
            ui_template_env = "v2"
            ui_template_env_degraded = False
            v2_env_missing = False
    else:
        env = app.jinja_env
        ui_template_env = "v1"
        ui_template_env_degraded = False
        v2_env_missing = False

    # 同时写入 env.globals：避免某些模板渲染路径不走 context 注入
    try:
        env.globals.setdefault("safe_url_for", safe_url_for)
        env.globals["url_for"] = template_url_for
        env.globals["get_help_card"] = get_help_card
        env.globals["get_manual_url"] = get_manual_url
        env.globals["get_full_manual_section_url"] = get_full_manual_section_url
    except Exception as exc:
        path = str(getattr(request, "path", "") or "") if has_request_context() else ""
        _log_warning(
            "模板环境全局函数注入失败：template=%s，path=%s，ui_template_env=%s，error=%s",
            _describe_template_name(template_name_or_list),
            path,
            str(ui_template_env or ""),
            exc,
        )

    template = env.get_or_select_template(template_name_or_list)
    ui_template_source = _resolve_template_source(
        app,
        mode=mode,
        template=template,
        v2_env_missing=bool(v2_env_missing),
    )
    if mode == "v2" and ui_template_source == "base_fallback":
        ui_template_env_degraded = True
        fallback_reason = "mode=v2 but v2_env missing" if v2_env_missing else "mode=v2 but template resolved via base loader"
        _warn_v2_render_fallback_once(
            app,
            template_name_or_list=template_name_or_list,
            reason=fallback_reason,
        )

    context.setdefault("ui_template_env", ui_template_env)
    context.setdefault("ui_template_env_degraded", ui_template_env_degraded)
    context.setdefault("ui_template_source", ui_template_source)
    try:
        g.ui_template_env = context.get("ui_template_env")
        g.ui_template_env_degraded = bool(context.get("ui_template_env_degraded"))
        g.ui_template_source = context.get("ui_template_source")
    except Exception:
        pass
    return template.render(context)

