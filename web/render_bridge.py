from __future__ import annotations

import os
from typing import Any

from flask import Blueprint, current_app, g, has_request_context, request, url_for
from jinja2 import ChoiceLoader, FileSystemLoader

from core.infrastructure.logging import safe_log
from web.bootstrap.static_versioning import EXT_KEY_TEMPLATE_URL_FOR
from web.manual_src_security import (
    get_full_manual_section_url,
    get_help_card,
    get_manual_url,
    safe_url_for,
)
from web.ui_mode_request import get_ui_mode

_EXT_KEY_V2_ENV = "ui_mode.v2_env"
_EXT_KEY_V2_TEMPLATE_DIR = "ui_mode.v2_templates_dir"
_EXT_KEY_V2_RENDER_FALLBACK_WARNED = "ui_mode.v2_render_fallback_warned"
_BP_NAME_V2_STATIC = "ui_v2_static"


def _log_startup_warning(app, message: str, *args: Any) -> None:
    safe_log(getattr(app, "logger", None), "warning", message, *args)


def init_ui_mode(app, base_dir: str) -> None:
    """
    初始化 UI 模式能力：
    - 注册 V2 静态资源：/static-v2 -> web_new_test/static
    - 创建 V2 Jinja overlay env：优先 web_new_test/templates，其次回退到现有 loader

    约束：只使用现有 Flask/Jinja2（Win7/Python3.8 兼容），不引入新依赖。
    """
    v2_static_dir = os.path.join(str(base_dir), "web_new_test", "static")
    if _BP_NAME_V2_STATIC not in app.blueprints:
        bp_static = Blueprint(
            _BP_NAME_V2_STATIC,
            __name__,
            static_folder=v2_static_dir,
            static_url_path="/static-v2",
        )
        app.register_blueprint(bp_static)
        if not os.path.isdir(v2_static_dir):
            _log_startup_warning(app, "V2 静态目录不存在：%s（/static-v2 将返回 404；请检查打包 add-data）", v2_static_dir)

    v2_templates_dir = os.path.join(str(base_dir), "web_new_test", "templates")
    app.extensions[_EXT_KEY_V2_TEMPLATE_DIR] = os.path.normcase(os.path.abspath(v2_templates_dir))
    try:
        base_loader = app.jinja_loader
        v2_loader = FileSystemLoader(v2_templates_dir)
        overlay_loader = ChoiceLoader([v2_loader, base_loader] if base_loader is not None else [v2_loader])
        v2_env = app.jinja_env.overlay(loader=overlay_loader)
        app.extensions[_EXT_KEY_V2_ENV] = v2_env
    except Exception as e:
        _log_startup_warning(app, "初始化 V2 Jinja 环境失败（将回退 V1）：%s", e)
        app.extensions[_EXT_KEY_V2_ENV] = None
    app.extensions.setdefault(_EXT_KEY_V2_RENDER_FALLBACK_WARNED, False)

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


def _get_v2_env(app) -> Any:
    return app.extensions.get(_EXT_KEY_V2_ENV)


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
    except Exception as exc:
        path = ""
        safe_log(getattr(app, "logger", None), "warning", "读取当前请求路径失败，仍会记录 V2 模板回退：%s", exc)
    safe_log(
        getattr(app, "logger", None),
        "warning",
        "检测到 V2 模板运行期回退：%s（template=%s, path=%s）。可能原因：未重新打包 / overlay 创建失败 / V2 单页模板缺失 / 运行旧版本。",
        str(reason or "").strip() or "mode=v2 but v2 fallback triggered",
        _describe_template_name(template_name_or_list),
        path,
    )


def _resolve_template_source(app, *, mode: str, template: Any, v2_env_missing: bool) -> str:
    if str(mode or "").strip().lower() != "v2":
        return "base"
    if v2_env_missing:
        return "base_fallback"

    filename = str(getattr(template, "filename", "") or "").strip()
    if not filename:
        return "v2"

    normalized_filename = os.path.normcase(os.path.abspath(filename))

    v2_root = str(app.extensions.get(_EXT_KEY_V2_TEMPLATE_DIR) or "").strip()
    if v2_root and (normalized_filename == v2_root or normalized_filename.startswith(v2_root + os.sep)):
        return "v2"
    return "base_fallback"


def _resolve_template_url_for():
    try:
        app = current_app
        custom = app.extensions.get(EXT_KEY_TEMPLATE_URL_FOR)
        if callable(custom):
            return custom
    except Exception as exc:
        safe_log(None, "warning", "读取模板 url_for 扩展失败，已回退 Flask url_for：%s", exc)
    return url_for


def render_ui_template(template_name_or_list, **context: Any) -> str:
    """
    render_template 的兼容封装：
    - 根据 ui_mode 选择 V1/V2 的 Jinja env
    - 注入 ui_mode 到模板上下文
    """
    app = current_app
    mode = get_ui_mode()

    context.setdefault("ui_mode", mode)
    try:
        g.ui_mode = mode
    except Exception as exc:
        safe_log(getattr(app, "logger", None), "warning", "写入请求 UI 模式状态失败，已继续渲染：%s", exc)

    app.update_template_context(context)
    template_url_for = _resolve_template_url_for()
    context["url_for"] = template_url_for

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

    try:
        env.globals.setdefault("safe_url_for", safe_url_for)
        env.globals["url_for"] = template_url_for
        env.globals["get_help_card"] = get_help_card
        env.globals["get_manual_url"] = get_manual_url
        env.globals["get_full_manual_section_url"] = get_full_manual_section_url
    except Exception as exc:
        path = str(getattr(request, "path", "") or "") if has_request_context() else ""
        safe_log(
            getattr(app, "logger", None),
            "warning",
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
    except Exception as exc:
        safe_log(getattr(app, "logger", None), "warning", "写入请求模板环境状态失败，已继续渲染：%s", exc)
    return template.render(context)
