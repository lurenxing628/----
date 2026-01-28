from __future__ import annotations

import os
from typing import Any, Dict, Optional

from flask import Blueprint, current_app, g, has_request_context, request
from jinja2 import ChoiceLoader, FileSystemLoader

from data.repositories import SystemConfigRepository

# -------------------------
# Constants
# -------------------------

UI_MODE_COOKIE_KEY = "aps_ui_mode"
UI_MODE_CONFIG_KEY = "ui_mode"  # stored in SystemConfig
DEFAULT_UI_MODE = "v1"
VALID_UI_MODES = ("v1", "v2")

_EXT_KEY_V2_ENV = "ui_mode.v2_env"
_BP_NAME_V2_STATIC = "ui_v2_static"


def normalize_ui_mode(value: Any) -> Optional[str]:
    v = ("" if value is None else str(value)).strip().lower()
    return v if v in VALID_UI_MODES else None


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
        repo = SystemConfigRepository(conn, logger=getattr(current_app, "logger", None))
        return normalize_ui_mode(repo.get_value(UI_MODE_CONFIG_KEY, default=None))
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
        setattr(g, "ui_mode", mode)
    except Exception:
        pass

    # 复用 Flask 的上下文处理器（request/g/session/url_for 等）
    app.update_template_context(context)

    if mode == "v2":
        env = _get_v2_env(app) or app.jinja_env
    else:
        env = app.jinja_env

    template = env.get_or_select_template(template_name_or_list)
    return template.render(context)

