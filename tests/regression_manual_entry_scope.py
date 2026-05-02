"""
回归测试：系统使用说明页面级入口、悬浮速览 popover 结构、整本模式回退、页面模式上下文和下载链路。

验证点：
1) 代表页面在 v1 / v2 下都能看到不遮挡业务按钮的说明入口，并跳到 `?page=<endpoint>&src=...`。
2) 有 help_card 的页面会在 HTML 中直接渲染速览 popover，关键提示片段仍从 page_manuals 事实源派生。
3) 说明书页支持双模式：无 `page` 时整本模式；有 `page` 时页面模式。
4) 页面模式下无论来源页是否属于 scheduler，都不显示排产子导航。
5) 说明书下载文件名保持为“系统使用说明.md”，且页面模式下载保留 `page/src` 上下文。
6) 页面模式无 `src` 时，提供明确的兜底返回入口。
"""

from __future__ import annotations

import html as html_module
import importlib
import os
import re
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from flask import url_for


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _prepare_env(tmpdir: str) -> None:
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(Path(tmpdir) / "aps_test.db")
    os.environ["APS_LOG_DIR"] = str(Path(tmpdir) / "logs")
    os.environ["APS_BACKUP_DIR"] = str(Path(tmpdir) / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(Path(tmpdir) / "templates_excel")
    os.environ["SECRET_KEY"] = "aps-manual-entry-scope"


def _load_app(repo_root: str):
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def _mode_headers(ui_mode: str) -> dict[str, str]:
    return {"Cookie": f"aps_ui_mode={ui_mode}"}


def _encode_src(path: str) -> str:
    return path if "?" in path else f"{path}?"


def _build_url(app, endpoint: str, **values: str) -> str:
    with app.test_request_context():
        return url_for(endpoint, **values)


def _assert_contains(content: str, needle: str, message: str) -> None:
    if needle not in content:
        raise RuntimeError(f"{message}（缺少片段：{needle}）")


def _assert_not_contains(content: str, needle: str, message: str) -> None:
    if needle in content:
        raise RuntimeError(f"{message}（出现了不应存在的片段：{needle}）")


def _extract_href_by_class(content: str, class_name: str) -> str | None:
    exact_pattern = rf'<a href="([^"]+)" class="{re.escape(class_name)}(?:\s[^"]*)?"'
    m = re.search(exact_pattern, content)
    if not m:
        fallback_pattern = rf'<a href="([^"]+)" class="[^"]*{re.escape(class_name)}[^"]*"'
        m = re.search(fallback_pattern, content)
    if not m:
        return None
    return html_module.unescape(m.group(1))


def _extract_link_href_by_text(content: str, label: str) -> str | None:
    pattern = r'<a href="([^"]+)"[^>]*>(.*?)</a>'
    for href, inner in re.findall(pattern, content, flags=re.S):
        if f"<span>{label}</span>" in inner:
            return html_module.unescape(href)
    return None


def _extract_template_content_by_id(content: str, template_id: str) -> str | None:
    pattern = rf'<template[^>]*id="{re.escape(template_id)}"[^>]*>(.*?)</template>'
    m = re.search(pattern, content, flags=re.S)
    if not m:
        return None
    return html_module.unescape(m.group(1)).strip()


def _collect_renderable_manual_endpoints(app, manual_endpoints: set[str]) -> list[str]:
    renderable = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint not in manual_endpoints:
            continue
        if "GET" not in (rule.methods or set()):
            continue
        if rule.arguments:
            continue
        renderable.add(rule.endpoint)
    return sorted(renderable)


def main() -> None:
    repo_root = find_repo_root()
    tmpdir = tempfile.mkdtemp(prefix="aps_regression_manual_entry_")
    _prepare_env(tmpdir)
    app = _load_app(repo_root)
    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    client = app.test_client()

    renderable_pages = _collect_renderable_manual_endpoints(app, set(page_manuals.ENDPOINT_TO_MANUAL_ID))

    material_path = _build_url(app, "material.materials_page")
    material_src = _encode_src(material_path)
    scheduler_config_path = _build_url(app, "scheduler.config_page")
    scheduler_src = _encode_src(scheduler_config_path)

    for ui_mode in ("v1", "v2"):
        for endpoint in renderable_pages:
            path = _build_url(app, endpoint)
            resp = client.get(path, headers=_mode_headers(ui_mode))
            if resp.status_code != 200:
                raise RuntimeError(f"{ui_mode} 模式访问 {endpoint}({path}) 返回非 200：{resp.status_code}")
            content = resp.get_data(as_text=True)
            manual = page_manuals.build_manual_for_endpoint(endpoint, include_sections=False)
            help_card = (manual or {}).get("help_card") or {}
            help_items = list(help_card.get("items") or [])
            help_snippet = str(help_card.get("title") or (help_items[0] if help_items else "")).strip()
            expect_help_card = bool(help_snippet)

            expected_href = _build_url(
                app,
                "scheduler.config_manual_page",
                page=endpoint,
                src=_encode_src(path),
            )
            expected_href_html = expected_href.replace("&", "&amp;")
            expected_popover_id = f'manual-popover-{endpoint.replace(".", "-").replace("_", "-")}'
            expected_title_id = f"{expected_popover_id}-title"
            _assert_contains(content, "floating-manual-btn", f"{ui_mode} 模式下复杂页面未显示悬浮说明入口：{endpoint}")
            _assert_contains(content, "本页说明", f"{ui_mode} 模式下说明入口文案未更新：{endpoint}")
            _assert_contains(content, expected_href_html, f"{ui_mode} 模式下说明入口链接不正确：{endpoint}")
            if ui_mode == "v2":
                sidebar_idx = content.find('class="sidebar"')
                manual_idx = content.find("floating-manual-wrapper")
                footnote_idx = content.find("sidebar-footnote")
                if not (0 <= sidebar_idx < manual_idx < footnote_idx):
                    raise RuntimeError(f"v2 模式下说明入口应渲染在侧边栏脚注前，避免覆盖主内容区：{endpoint}")

            if expect_help_card:
                _assert_contains(content, 'data-manual-popover="1"', f"{ui_mode} 模式下缺少 popover 触发标记：{endpoint}")
                _assert_contains(content, f'aria-controls="{expected_popover_id}"', f"{ui_mode} 模式下缺少 aria-controls：{endpoint}")
                _assert_contains(content, f'id="{expected_popover_id}"', f"{ui_mode} 模式下缺少 popover 容器：{endpoint}")
                _assert_contains(content, f'aria-labelledby="{expected_title_id}"', f"{ui_mode} 模式下缺少 aria-labelledby：{endpoint}")
                _assert_contains(content, 'aria-expanded="false"', f"{ui_mode} 模式下 popover 初始状态不正确：{endpoint}")
                _assert_contains(content, 'role="dialog"', f"{ui_mode} 模式下 popover 缺少 dialog 语义：{endpoint}")
                _assert_contains(content, "manual-popover", f"{ui_mode} 模式下未渲染速览 popover：{endpoint}")
                _assert_contains(content, help_snippet, f"{ui_mode} 模式下页面内关键提示缺失：{endpoint}")
                _assert_contains(content, "查看本页详细说明", f"{ui_mode} 模式下帮助卡文案未更新：{endpoint}")

        home_resp = client.get("/", headers=_mode_headers(ui_mode))
        if home_resp.status_code != 200:
            raise RuntimeError(f"{ui_mode} 模式访问首页返回非 200：{home_resp.status_code}")
        home_html = home_resp.get_data(as_text=True)
        _assert_not_contains(home_html, "floating-manual-btn", f"{ui_mode} 模式下首页不应显示悬浮说明入口")

        full_material_url = _build_url(app, "scheduler.config_manual_page", src=material_src)
        manual_resp = client.get(full_material_url, headers=_mode_headers(ui_mode))
        if manual_resp.status_code != 200:
            raise RuntimeError(f"{ui_mode} 模式访问整本说明书页返回非 200：{manual_resp.status_code}")
        manual_html = manual_resp.get_data(as_text=True)
        _assert_contains(manual_html, "系统使用说明", f"{ui_mode} 模式下整本说明书页标题缺失")
        _assert_contains(manual_html, "返回刚才页面", f"{ui_mode} 模式下整本说明书页未保留来源页返回入口")
        _assert_contains(manual_html, 'id="aps-config-manual-fallback"', f"{ui_mode} 模式下整本说明书页缺少服务端 fallback 模板")
        full_fallback_text = _extract_template_content_by_id(manual_html, "aps-config-manual-fallback")
        if not full_fallback_text or len(full_fallback_text) < 100:
            raise RuntimeError(f"{ui_mode} 模式下整本说明书页 fallback 正文为空或过短")
        _assert_not_contains(manual_html, "floating-manual-btn", f"{ui_mode} 模式下说明书页不应显示悬浮入口")
        _assert_not_contains(manual_html, "当前页面主题：", f"{ui_mode} 模式下整本说明书页不应出现页面模式标识")
        _assert_not_contains(manual_html, "相关模块说明", f"{ui_mode} 模式下整本说明书页不应显示相关模块列表")
        _assert_not_contains(manual_html, "manual-main-column", f"{ui_mode} 模式下整本说明书页不应渲染页面级右列容器")
        _assert_not_contains(manual_html, "manual-related-panel", f"{ui_mode} 模式下整本说明书页不应渲染相关模块面板")
        _assert_not_contains(manual_html, "scheduler-subnav-main", f"{ui_mode} 模式下来自非 scheduler 页面时应隐藏排产子导航")

        full_scheduler_url = _build_url(app, "scheduler.config_manual_page", src=scheduler_src)
        manual_scheduler_resp = client.get(full_scheduler_url, headers=_mode_headers(ui_mode))
        if manual_scheduler_resp.status_code != 200:
            raise RuntimeError(f"{ui_mode} 模式访问 scheduler 来源整本说明书页返回非 200：{manual_scheduler_resp.status_code}")
        manual_scheduler_html = manual_scheduler_resp.get_data(as_text=True)
        _assert_contains(manual_scheduler_html, "scheduler-subnav-main", f"{ui_mode} 模式下整本说明书页应保留排产子导航")

        page_material_url = _build_url(
            app,
            "scheduler.config_manual_page",
            page="material.materials_page",
            src=material_src,
        )
        page_material_resp = client.get(page_material_url, headers=_mode_headers(ui_mode))
        if page_material_resp.status_code != 200:
            raise RuntimeError(f"{ui_mode} 模式访问页面级说明书返回非 200：{page_material_resp.status_code}")
        page_material_html = page_material_resp.get_data(as_text=True)
        _assert_contains(page_material_html, "本页说明 - 物料主数据", f"{ui_mode} 模式下页面级说明标题不正确")
        _assert_contains(page_material_html, '<div class="aps-summary-label">当前页面主题</div>', f"{ui_mode} 模式下页面级说明缺少当前页主题标签")
        _assert_contains(page_material_html, '<div class="aps-summary-value">物料主数据</div>', f"{ui_mode} 模式下页面级说明缺少当前页主题值")
        _assert_contains(page_material_html, '<div class="aps-summary-label">对应整本章节</div>', f"{ui_mode} 模式下页面级说明缺少整本章节标签")
        _assert_contains(page_material_html, "相关模块说明", f"{ui_mode} 模式下页面级说明缺少相关模块列表")
        _assert_contains(page_material_html, "查看完整原文对应章节", f"{ui_mode} 模式下页面级说明缺少原文章节入口")
        _assert_contains(page_material_html, "下载整本说明书", f"{ui_mode} 模式下页面级说明下载按钮文案不正确")
        _assert_contains(page_material_html, '<div class="aps-summary-label">整本说明书更新时间</div>', f"{ui_mode} 模式下页面级说明更新时间文案不正确")
        _assert_contains(page_material_html, "维护顺序建议", f"{ui_mode} 模式下 related 模块未渲染关键说明段落")
        _assert_contains(page_material_html, 'id="aps-config-manual-fallback"', f"{ui_mode} 模式下页面级说明缺少服务端 fallback 模板")
        material_fallback_text = _extract_template_content_by_id(page_material_html, "aps-config-manual-fallback")
        if not material_fallback_text:
            raise RuntimeError(f"{ui_mode} 模式下页面级说明 fallback 正文为空")
        _assert_contains(material_fallback_text, "物料主数据", f"{ui_mode} 模式下页面级说明 fallback 未保留当前主题")
        _assert_contains(material_fallback_text, "齐套", f"{ui_mode} 模式下页面级说明 fallback 未注入当前页正文")
        _assert_contains(page_material_html, "manual-main-column", f"{ui_mode} 模式下页面级说明缺少右列容器")
        _assert_contains(page_material_html, "manual-related-panel", f"{ui_mode} 模式下页面级说明缺少相关模块面板类")
        if page_material_html.count('id="content"') != 1:
            raise RuntimeError(f"{ui_mode} 模式下页面级说明应只保留一个 #content")
        content_idx = page_material_html.index('id="content"')
        main_col_idx = page_material_html.index("manual-main-column")
        related_panel_idx = page_material_html.index("manual-related-panel")
        if not (main_col_idx < content_idx < related_panel_idx):
            raise RuntimeError(f"{ui_mode} 模式下页面级说明右列结构顺序异常")
        _assert_not_contains(page_material_html, "scheduler-subnav-main", f"{ui_mode} 模式下页面级说明不应显示排产子导航")
        _assert_not_contains(page_material_html, "floating-manual-btn", f"{ui_mode} 模式下页面级说明页不应显示悬浮入口")
        expected_download_href = _build_url(
            app,
            "scheduler.config_manual_download",
            src=material_src,
            page="material.materials_page",
        )
        expected_download_href_html = expected_download_href.replace("&", "&amp;")
        _assert_contains(page_material_html, expected_download_href_html, f"{ui_mode} 模式下页面级说明下载链接未保留上下文")

        page_material_external_url = _build_url(
            app,
            "scheduler.config_manual_page",
            page="material.materials_page",
            src="http://evil.example/x",
        )
        page_material_external_resp = client.get(page_material_external_url, headers=_mode_headers(ui_mode))
        if page_material_external_resp.status_code != 200:
            raise RuntimeError(f"{ui_mode} 模式访问外部来源页面级说明返回非 200：{page_material_external_resp.status_code}")
        page_material_external_html = page_material_external_resp.get_data(as_text=True)
        _assert_contains(page_material_external_html, "返回首页", f"{ui_mode} 模式下外部来源页面级说明缺少首页兜底返回入口")
        external_download_href = _extract_link_href_by_text(page_material_external_html, "下载整本说明书")
        if not external_download_href:
            raise RuntimeError(f"{ui_mode} 模式下外部来源页面级说明缺少下载链接")
        _assert_not_contains(external_download_href, "src=", f"{ui_mode} 模式下外部来源不应继续写入下载链接")
        _assert_contains(external_download_href, "page=material.materials_page", f"{ui_mode} 模式下合法 page 应继续保留在下载链接")
        external_full_href = _extract_link_href_by_text(page_material_external_html, "查看完整原文对应章节")
        if not external_full_href:
            raise RuntimeError(f"{ui_mode} 模式下外部来源页面级说明缺少完整原文跳转链接")
        _assert_not_contains(external_full_href, "src=", f"{ui_mode} 模式下外部来源不应继续写入完整原文链接")
        external_related_href = _extract_link_href_by_text(page_material_external_html, "查看该页说明")
        if not external_related_href:
            raise RuntimeError(f"{ui_mode} 模式下外部来源页面级说明缺少 related 说明链接")
        _assert_not_contains(external_related_href, "src=", f"{ui_mode} 模式下外部来源不应继续写入 related 说明链接")

        page_material_protocol_url = _build_url(
            app,
            "scheduler.config_manual_page",
            page="material.materials_page",
            src="//evil.example/x",
        )
        page_material_protocol_resp = client.get(page_material_protocol_url, headers=_mode_headers(ui_mode))
        if page_material_protocol_resp.status_code != 200:
            raise RuntimeError(f"{ui_mode} 模式访问协议相对来源页面级说明返回非 200：{page_material_protocol_resp.status_code}")
        page_material_protocol_html = page_material_protocol_resp.get_data(as_text=True)
        protocol_download_href = _extract_link_href_by_text(page_material_protocol_html, "下载整本说明书")
        if not protocol_download_href:
            raise RuntimeError(f"{ui_mode} 模式下协议相对来源页面级说明缺少下载链接")
        _assert_not_contains(protocol_download_href, "src=", f"{ui_mode} 模式下协议相对来源不应继续写入下载链接")

        page_scheduler_url = _build_url(
            app,
            "scheduler.config_manual_page",
            page="scheduler.config_page",
            src=scheduler_src,
        )
        page_scheduler_resp = client.get(page_scheduler_url, headers=_mode_headers(ui_mode))
        if page_scheduler_resp.status_code != 200:
            raise RuntimeError(f"{ui_mode} 模式访问 scheduler 来源页面级说明返回非 200：{page_scheduler_resp.status_code}")
        page_scheduler_html = page_scheduler_resp.get_data(as_text=True)
        _assert_not_contains(page_scheduler_html, "scheduler-subnav-main", f"{ui_mode} 模式下页面级说明应统一隐藏排产子导航")

        page_material_no_src_url = _build_url(app, "scheduler.config_manual_page", page="material.materials_page")
        page_material_no_src_resp = client.get(page_material_no_src_url, headers=_mode_headers(ui_mode))
        if page_material_no_src_resp.status_code != 200:
            raise RuntimeError(f"{ui_mode} 模式访问无来源页面级说明返回非 200：{page_material_no_src_resp.status_code}")
        page_material_no_src_html = page_material_no_src_resp.get_data(as_text=True)
        _assert_contains(page_material_no_src_html, "返回首页", f"{ui_mode} 模式下非 scheduler 页面说明缺少首页兜底返回入口")

        page_scheduler_no_src_url = _build_url(app, "scheduler.config_manual_page", page="scheduler.config_page")
        page_scheduler_no_src_resp = client.get(page_scheduler_no_src_url, headers=_mode_headers(ui_mode))
        if page_scheduler_no_src_resp.status_code != 200:
            raise RuntimeError(f"{ui_mode} 模式访问无来源 scheduler 页面级说明返回非 200：{page_scheduler_no_src_resp.status_code}")
        page_scheduler_no_src_html = page_scheduler_no_src_resp.get_data(as_text=True)
        _assert_contains(page_scheduler_no_src_html, "返回排产首页", f"{ui_mode} 模式下 scheduler 页面说明缺少排产首页兜底返回入口")

        invalid_page_url = _build_url(app, "scheduler.config_manual_page", page="unknown.endpoint", src=material_src)
        invalid_page_resp = client.get(invalid_page_url, headers=_mode_headers(ui_mode))
        if invalid_page_resp.status_code != 200:
            raise RuntimeError(f"{ui_mode} 模式访问非法 page 参数返回非 200：{invalid_page_resp.status_code}")
        invalid_page_html = invalid_page_resp.get_data(as_text=True)
        _assert_contains(invalid_page_html, "系统使用说明", f"{ui_mode} 模式下非法 page 应回退到整本说明页")
        _assert_not_contains(invalid_page_html, "当前页面主题：", f"{ui_mode} 模式下非法 page 不应保留页面模式主题")
        invalid_download_href = _extract_link_href_by_text(invalid_page_html, "下载说明书原文")
        if not invalid_download_href:
            raise RuntimeError(f"{ui_mode} 模式下非法 page 整本说明书缺少下载链接")
        _assert_not_contains(invalid_download_href, "page=unknown.endpoint", f"{ui_mode} 模式下非法 page 不应继续写入下载链接")

    download_resp = client.get(
        _build_url(
            app,
            "scheduler.config_manual_download",
            page="material.materials_page",
            src=material_src,
        ),
        headers=_mode_headers("v1"),
    )
    if download_resp.status_code != 200:
        raise RuntimeError(f"说明书下载接口返回非 200：{download_resp.status_code}")
    content_disposition = download_resp.headers.get("Content-Disposition", "")
    expected_filename = quote("系统使用说明.md", safe="")
    _assert_contains(content_disposition, expected_filename, "说明书下载文件名未更新为“系统使用说明.md”")

    with ExitStack() as stack:
        stack.enter_context(patch("web.routes.scheduler_config._resolve_scheduler_manual_md_path", return_value=(None, [])))
        stack.enter_context(
            patch("web.routes.domains.scheduler.scheduler_config._resolve_scheduler_manual_md_path", return_value=(None, []))
        )
        dirty_download_resp = client.get(
            _build_url(
                app,
                "scheduler.config_manual_download",
                page="unknown.endpoint",
                src="http://evil.example/x",
            ),
            headers=_mode_headers("v1"),
            follow_redirects=False,
        )
    if dirty_download_resp.status_code not in (302, 303):
        raise RuntimeError(f"说明书缺失时下载接口应重定向，实际返回：{dirty_download_resp.status_code}")
    redirect_location = dirty_download_resp.headers.get("Location", "")
    _assert_not_contains(redirect_location, "evil.example", "下载失败回跳不应回写外部来源 src")
    _assert_not_contains(redirect_location, "unknown.endpoint", "下载失败回跳不应回写非法 page")

    ui_contract_css = (Path(repo_root) / "static" / "css" / "ui_contract.css").read_text(encoding="utf-8")
    _assert_contains(
        ui_contract_css,
        ".sidebar .floating-manual-wrapper",
        "现代界面的说明入口应放在左侧导航栏，不应覆盖主内容区操作按钮",
    )
    _assert_contains(ui_contract_css, "position: relative;", "说明入口不应继续固定悬浮覆盖业务按钮")
    _assert_contains(ui_contract_css, ".manual-popover", "说明速览弹窗样式缺失")
    _assert_contains(ui_contract_css, "left: calc(100% + 12px);", "现代界面说明速览应从侧边栏向内容区展开")

    print("OK")


def test_manual_entry_scope_contract() -> None:
    main()


if __name__ == "__main__":
    main()
