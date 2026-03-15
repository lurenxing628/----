from __future__ import annotations

import os
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from flask import Blueprint, current_app, g, has_request_context, request, url_for
from jinja2 import ChoiceLoader, FileSystemLoader
from werkzeug.routing.exceptions import BuildError

from core.services.system import SystemConfigService
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
_BP_NAME_V2_STATIC = "ui_v2_static"


def normalize_ui_mode(value: Any) -> Optional[str]:
    v = ("" if value is None else str(value)).strip().lower()
    return v if v in VALID_UI_MODES else None


def _resolve_manual_endpoint(endpoint: Any = None) -> str:
    if endpoint is not None:
        return str(endpoint).strip()
    if not has_request_context():
        return ""
    try:
        return str(request.endpoint or "").strip()
    except Exception:
        return ""


def normalize_manual_src(raw: Any = None) -> Optional[str]:
    text = ("" if raw is None else str(raw)).strip()
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


def get_full_manual_section_url(endpoint: Any = None, src: Any = None) -> Optional[str]:
    current_endpoint = _resolve_manual_endpoint(endpoint)
    if not current_endpoint:
        return None
    manual = build_manual_for_endpoint(current_endpoint, include_sections=False)
    if not manual:
        return None
    safe_src = normalize_manual_src(_resolve_manual_src(src))
    base_url = safe_url_for("scheduler.config_manual_page", src=safe_src)
    if not base_url:
        return None
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
            try:
                app.logger.warning(f"V2 静态目录不存在：{v2_static_dir}（/static-v2 将返回 404；请检查打包 add-data）")
            except Exception:
                pass

    # ---- V2 jinja overlay ----
    v2_templates_dir = os.path.join(str(base_dir), "web_new_test", "templates")
    try:
        base_loader = app.jinja_loader
        v2_loader = FileSystemLoader(v2_templates_dir)
        # V2 优先，其次回退现有 loader（V1 + 蓝图 templates）
        overlay_loader = ChoiceLoader([v2_loader, base_loader] if base_loader is not None else [v2_loader])
        v2_env = app.jinja_env.overlay(loader=overlay_loader)
        app.extensions[_EXT_KEY_V2_ENV] = v2_env
    except Exception as e:
        # 不阻断启动：V2 env 创建失败则回退到 V1
        try:
            app.logger.warning(f"初始化 V2 Jinja 环境失败（将回退 V1）：{e}")
        except Exception:
            pass
        app.extensions[_EXT_KEY_V2_ENV] = None

    # 启动期即向 V1/V2 两套模板环境注入 safe_url_for，
    # 兼容直接使用 Flask render_template 的路径以及 import 宏场景。
    try:
        app.jinja_env.globals.setdefault("safe_url_for", safe_url_for)
        app.jinja_env.globals["get_help_card"] = get_help_card
        app.jinja_env.globals["get_manual_url"] = get_manual_url
        app.jinja_env.globals["get_full_manual_section_url"] = get_full_manual_section_url
    except Exception:
        pass
    try:
        v2_env = app.extensions.get(_EXT_KEY_V2_ENV)
        if v2_env is not None:
            v2_env.globals.setdefault("safe_url_for", safe_url_for)
            v2_env.globals["get_help_card"] = get_help_card
            v2_env.globals["get_manual_url"] = get_manual_url
            v2_env.globals["get_full_manual_section_url"] = get_full_manual_section_url
    except Exception:
        pass


def _read_ui_mode_from_db() -> Optional[str]:
    """
    从 SystemConfig 读取 ui_mode（v1/v2）。
    - 依赖 g.db；无 DB 时返回 None
    - 任何异常都吞掉（保持页面可用）
    """
    try:
        conn = getattr(g, "db", None)
        if conn is None:
            return None
        svc = SystemConfigService(conn, logger=getattr(current_app, "logger", None))
        return normalize_ui_mode(svc.get_value(UI_MODE_CONFIG_KEY, default=None))
    except Exception:
        return None


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
    except Exception:
        pass

    # 2) DB
    db_mode = _read_ui_mode_from_db()
    if db_mode:
        return db_mode

    return d


def _get_v2_env(app) -> Any:
    env = app.extensions.get(_EXT_KEY_V2_ENV)
    return env


def safe_url_for(endpoint: str, **values: Any) -> Optional[str]:
    """
    url_for 的安全封装：
    - endpoint 不存在（BuildError）时返回 None（而不是抛异常导致整页 500）
    - 其他异常同样吞掉并返回 None（保持页面可用，便于排障/渐进发布）
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
                try:
                    path = getattr(request, "path", "") or ""
                except Exception:
                    path = ""
                try:
                    # values 里可能包含 id 等，便于定位；但避免超长
                    current_app.logger.warning(
                        f"模板链接不可用：endpoint 未注册（{endpoint}），path={path}。"
                        "可能原因：运行旧版本/未重启/未重新打包。"
                    )
                except Exception:
                    pass
        except Exception:
            pass
        return None
    except Exception:
        return None


def _resolve_template_url_for():
    try:
        app = current_app._get_current_object()
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
    app = current_app._get_current_object()
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
        env = _get_v2_env(app) or app.jinja_env
    else:
        env = app.jinja_env

    # 同时写入 env.globals：避免某些模板渲染路径不走 context 注入
    try:
        env.globals.setdefault("safe_url_for", safe_url_for)
        env.globals["url_for"] = template_url_for
        env.globals["get_help_card"] = get_help_card
        env.globals["get_manual_url"] = get_manual_url
        env.globals["get_full_manual_section_url"] = get_full_manual_section_url
    except Exception:
        pass

    template = env.get_or_select_template(template_name_or_list)
    return template.render(context)

