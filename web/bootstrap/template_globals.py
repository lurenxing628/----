from __future__ import annotations

from web.manual_src_security import (
    get_full_manual_section_url,
    get_help_card,
    get_manual_url,
    safe_url_for,
)
from web.navigation_context import (
    build_report_navigation_links,
    build_scheduler_navigation_links,
    build_workbench_navigation_links,
    current_public_return_url,
    preserved_report_context_fields,
    workbench_plan_capsule,
)


def install_template_globals(app) -> None:
    """启动期把跨页模板全局一次性装进 app.jinja_env。

    前 8 个全局原由双轨机器 render_bridge.init_ui_mode 注入（2026-06 双轨退役后
    本函数是唯一安装点），第 9 个 workbench_plan_capsule 是壳层胶囊（4.2）。
    base.html 的导航宏 / 帮助卡 / 手册链接 / 胶囊全靠它们——
    安装失败必须让启动失败：宏断供是页面级灾难，启动期暴露优于运行期 UndefinedError。
    """
    env = app.jinja_env
    env.globals.setdefault("safe_url_for", safe_url_for)
    env.globals["get_help_card"] = get_help_card
    env.globals["get_manual_url"] = get_manual_url
    env.globals["get_full_manual_section_url"] = get_full_manual_section_url
    env.globals["build_workbench_navigation_links"] = build_workbench_navigation_links
    env.globals["build_report_navigation_links"] = build_report_navigation_links
    env.globals["build_scheduler_navigation_links"] = build_scheduler_navigation_links
    env.globals["current_public_return_url"] = current_public_return_url
    env.globals["preserved_report_context_fields"] = preserved_report_context_fields
    env.globals["workbench_plan_capsule"] = workbench_plan_capsule
