"""系统使用说明页：旧 ``/scheduler/config/manual`` 入口在工作台里继续作为帮助页使用。

2026-09-18 旧排产配置页随旧路由层删除，说明书页与原文下载从 scheduler_config 抽到这里，
端点名保持 ``scheduler.config_manual_page`` / ``scheduler.config_manual_download``。
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, flash, g, redirect, render_template, request, send_file, url_for

from core.services.workbench.messages import beijing_text
from web.manual_src_security import (
    get_full_manual_section_url,
    get_manual_url,
    normalize_manual_src_context,
)
from web.viewmodels.page_manuals import (
    MANUAL_ENTRY_ENDPOINTS,
    build_page_fallback_text,
    build_page_manual_bundle,
)

from .legacy_blueprints import scheduler_bp as bp


def _resolve_scheduler_manual_md_path() -> Tuple[Optional[str], List[str]]:
    """
    解析“系统使用说明”的 md 文件路径。

    说明：
    - 事实源固定为仓库根目录下的 static/docs/scheduler_manual.md
    - 只允许 BASE_DIR 推导出的唯一路径，不再在 static_folder 等位置做首个命中式猜测
    - 返回：(命中的路径 or None, 唯一路径候选)
    """
    base_dir = None
    try:
        base_dir = current_app.config.get("BASE_DIR")
    except Exception:
        base_dir = None

    base_dir = str(base_dir).strip() if base_dir is not None else ""
    if not base_dir:
        return None, []

    candidate = os.path.join(base_dir, "static", "docs", "scheduler_manual.md")
    normalized = [os.path.abspath(candidate)]

    if os.path.isfile(normalized[0]):
        return normalized[0], normalized

    return None, normalized


def _resolve_manual_back_url(raw_src: Optional[str]) -> Optional[str]:
    """
    输入应为已经过 normalize_manual_src() 过滤的站内相对地址。
    这里只负责把空值折叠为 None，不再重复制造 fallback 语义。
    """
    safe_src = (raw_src or "").strip()
    if not safe_src:
        return None
    return safe_src


def _build_manual_page_url(raw_src: Optional[str], raw_page: Optional[str]) -> str:
    values: Dict[str, Any] = {}
    if raw_src:
        values["src"] = raw_src
    if raw_page:
        values["page"] = raw_page
    return url_for("scheduler.config_manual_page", **values)


def _normalize_scheduler_manual_args(raw_src: Optional[str], raw_page: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    safe_src = normalize_manual_src_context(raw_src)
    bundle = build_page_manual_bundle(raw_page) if raw_page else None
    safe_page = raw_page if bundle else None
    page_warning = None
    if raw_page and safe_page is None:
        page_warning = "这一页还没有单独的说明，已经打开整本说明书。"
    return safe_src, safe_page, bundle, page_warning


def _resolve_manual_entry_endpoint(manual_id: Optional[str]) -> Optional[str]:
    target = str(manual_id or "").strip()
    if not target:
        return None
    return MANUAL_ENTRY_ENDPOINTS.get(target)


def _format_manual_mtime(manual_path: str) -> Optional[str]:
    try:
        stamp = datetime.fromtimestamp(os.path.getmtime(manual_path), timezone.utc)
    except OSError:
        return None
    return beijing_text(stamp.isoformat())


def _load_manual_text_and_mtime(manual_path: Optional[str], candidates: List[str]) -> Tuple[str, Optional[str]]:
    if not manual_path:
        if not candidates:
            try:
                current_app.logger.warning("scheduler manual path resolution failed: BASE_DIR missing or empty")
            except Exception:
                g._aps_scheduler_manual_warning_status = "log_warning_failed"
            return (
                "找不到说明书文件：本机安装信息不完整。请联系维护人员检查安装目录。",
                None,
            )

        try:
            current_app.logger.warning("系统使用说明文件不存在（candidates=%s）", candidates)
        except Exception:
            g._aps_scheduler_manual_warning_status = "log_warning_failed"
        return "找不到说明书文件，可能安装包里没带或文件被删了。请联系维护人员。", None

    try:
        with open(manual_path, encoding="utf-8") as f:
            manual_text = f.read()
        return manual_text, _format_manual_mtime(manual_path)
    except Exception:
        current_app.logger.exception("读取系统使用说明失败")
        return "说明书加载失败。请刷新重试；仍不行请联系维护人员。", None


def _build_manual_download_url(manual_path: Optional[str], safe_src: Optional[str], safe_page: Optional[str]) -> Optional[str]:
    if not manual_path:
        return None

    download_values: Dict[str, Any] = {}
    if safe_src:
        download_values["src"] = safe_src
    if safe_page:
        download_values["page"] = safe_page
    return url_for("scheduler.config_manual_download", **download_values)


def _build_related_manual_links(related_manuals: List[Dict[str, Any]], link_src: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in related_manuals:
        entry_endpoint = _resolve_manual_entry_endpoint(item.get("manual_id"))
        enriched = dict(item)
        enriched["entry_endpoint"] = entry_endpoint
        enriched["url"] = get_manual_url(endpoint=entry_endpoint, src=link_src) if entry_endpoint else None
        enriched["full_manual_section_url"] = (
            get_full_manual_section_url(endpoint=entry_endpoint, src=link_src) if entry_endpoint else ""
        )
        enriched["full_manual_section_url"] = enriched["full_manual_section_url"] or ""
        out.append(enriched)
    return out


def _resolve_page_back_action(raw_page: str, back_url: Optional[str]) -> Tuple[str, str]:
    if back_url:
        return back_url, "返回刚才页面"
    if raw_page.startswith("scheduler."):
        return url_for("scheduler.batches_page"), "返回排产首页"
    return url_for("dashboard.index"), "返回首页"


def _build_manual_page_view_state(
    *,
    raw_page: str,
    bundle: Optional[Dict[str, Any]],
    manual_text: str,
    link_src: str,
    back_url: Optional[str],
    show_scheduler_nav: bool,
) -> Dict[str, Any]:
    base_state: Dict[str, Any] = {
        "manual_mode": "full",
        "current_manual": None,
        "related_manuals": [],
        "fallback_text": manual_text,
        "full_manual_section_url": "",
        "page_title": "系统使用说明",
        "download_button_label": "下载说明书原文",
        "back_button_label": "返回刚才页面",
        "back_url": back_url,
        "show_scheduler_nav": show_scheduler_nav,
    }
    if not bundle:
        return base_state

    current_manual = bundle["current_manual"]
    resolved_back_url, back_button_label = _resolve_page_back_action(raw_page, back_url)
    return {
        "manual_mode": "page",
        "current_manual": current_manual,
        "related_manuals": _build_related_manual_links(bundle["related_manuals"], link_src),
        "fallback_text": build_page_fallback_text(raw_page, bundle=bundle) or manual_text,
        "full_manual_section_url": get_full_manual_section_url(endpoint=raw_page, src=link_src) or "",
        "page_title": f"本页说明 - {current_manual['title']}",
        "download_button_label": "下载整本说明书",
        "back_button_label": back_button_label,
        "back_url": resolved_back_url,
        "show_scheduler_nav": False,
    }


@bp.get("/scheduler/config/manual")
def config_manual_page():
    """
    系统使用说明（面向计划/工艺新手）。
    - 页内把 Markdown 转成 HTML 后展示（转换器在 legacy_presentation，不新增依赖）
    - 提供下载原始 md
    """
    raw_src = (request.args.get("src") or "").strip()
    raw_page = (request.args.get("page") or "").strip()
    safe_src, safe_page, bundle, page_warning = _normalize_scheduler_manual_args(raw_src, raw_page)
    if page_warning:
        flash(page_warning, "warning")
    link_src = safe_src or ""
    back_url = _resolve_manual_back_url(safe_src)
    show_scheduler_nav = not back_url or back_url.startswith("/scheduler")
    manual_path, candidates = _resolve_scheduler_manual_md_path()
    manual_text, manual_mtime = _load_manual_text_and_mtime(manual_path, candidates)
    download_url = _build_manual_download_url(manual_path, safe_src, safe_page)
    view_state = _build_manual_page_view_state(
        raw_page=raw_page,
        bundle=bundle,
        manual_text=manual_text,
        link_src=link_src,
        back_url=back_url,
        show_scheduler_nav=show_scheduler_nav,
    )

    return render_template(
        'workbench/manual.html',
        title=view_state["page_title"],
        manual_mode=view_state["manual_mode"],
        manual_text=manual_text,
        fallback_text=view_state["fallback_text"],
        manual_mtime=manual_mtime,
        download_url=download_url,
        back_url=view_state["back_url"],
        show_scheduler_nav=view_state["show_scheduler_nav"],
        current_manual=view_state["current_manual"],
        related_manuals=view_state["related_manuals"],
        full_manual_section_url=view_state["full_manual_section_url"],
        download_button_label=view_state["download_button_label"],
        back_button_label=view_state["back_button_label"],
    )


@bp.get("/scheduler/config/manual/download")
def config_manual_download():
    """
    下载原始说明书 Markdown。
    """
    raw_src = (request.args.get("src") or "").strip()
    raw_page = (request.args.get("page") or "").strip()
    safe_src, safe_page, _bundle, _page_warning = _normalize_scheduler_manual_args(raw_src, raw_page)
    manual_path, candidates = _resolve_scheduler_manual_md_path()
    if not manual_path:
        if not candidates:
            flash("找不到说明书文件：本机安装信息不完整。请联系维护人员检查安装目录。", "error")
            return redirect(_build_manual_page_url(safe_src, safe_page))
        flash("说明书文件不在了，下载不了。请联系维护人员。", "error")
        return redirect(_build_manual_page_url(safe_src, safe_page))
    try:
        return send_file(
            manual_path,
            as_attachment=True,
            download_name="系统使用说明.md",
            mimetype="text/markdown; charset=utf-8",
        )
    except Exception:
        current_app.logger.exception("下载系统使用说明失败")
        flash("下载说明书失败。请重试一次；仍不行请联系维护人员。", "error")
        return redirect(_build_manual_page_url(safe_src, safe_page))
