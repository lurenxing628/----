"""系统使用说明页：旧 ``/scheduler/config/manual`` 入口在工作台里继续作为帮助页使用。

2026-09-18 旧排产配置页随旧路由层删除，说明书页与原文下载从 scheduler_config 抽到这里，
端点名保持 ``scheduler.config_manual_page`` / ``scheduler.config_manual_download``。

2026-09-21 “本页说明”通道改为按工作台视图 id 工作：顶栏「帮助」带 ``page=<视图 id>`` 和
``src=<返回地址>`` 打开本页时，先按 ``page_manuals_registry`` 登记的标题在说明书原文里截取对应
章节（标题到下一个同级或更高级标题之间的正文），并给出整本说明书的锚点链接；``page`` 没登记或
章节读不到时退化为整本说明书并用页面提示说明，不报错。
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, flash, g, redirect, render_template, request, send_file, url_for

from core.services.workbench.messages import beijing_text
from web.manual_src_security import normalize_manual_src_context
from web.viewmodels.page_manuals_registry import manual_entry

from .legacy_blueprints import scheduler_bp as bp
from .legacy_presentation import manual_blocks

PAGE_NOT_REGISTERED_WARNING = "这一页还没有单独的说明，已经打开整本说明书。"
PAGE_SECTION_MISSING_WARNING = "这一页的说明章节暂时读不到，已经打开整本说明书。"
FULL_MANUAL_LABEL = "阅读整本说明书"
FULL_MANUAL_TITLE = "系统使用说明"


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


def _build_full_manual_section_url(link_src: str, anchor: str) -> str:
    """整本说明书里对应章节的锚点链接；没有锚点时返回空串，模板据此不显示链接。"""
    if not anchor:
        return ""
    return _build_manual_page_url(link_src, None) + "#" + anchor


def _normalize_scheduler_manual_args(
    raw_src: Optional[str], raw_page: Optional[str]
) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """返回 (安全的返回地址, 已登记的视图 id, 登记条目, 页面提示)；未登记的 page 不回显原文。"""
    safe_src = normalize_manual_src_context(raw_src)
    entry = manual_entry(raw_page) if raw_page else None
    safe_page = entry["view"] if entry else None
    page_warning = None
    if raw_page and entry is None:
        page_warning = PAGE_NOT_REGISTERED_WARNING
    return safe_src, safe_page, entry, page_warning


def _workbench_view_url(view_id: str) -> str:
    """视图 id 对应的工作台地址：试调是独立路径，其余都是 ``/workbench?view=<id>``。"""
    if view_id == "trial":
        return url_for("workbench.trial")
    return url_for("workbench.index", view=view_id)


def _format_manual_mtime(manual_path: str) -> Optional[str]:
    try:
        stamp = datetime.fromtimestamp(os.path.getmtime(manual_path), timezone.utc)
    except OSError:
        return None
    return beijing_text(stamp.isoformat())


def _load_manual_text_and_mtime(manual_path: Optional[str], candidates: List[str]) -> Tuple[str, Optional[str]]:
    """旧签名：只返回 (正文或错误提示, 文件时间)。路由用 ``_load_manual_source``，这里留给既有调用方。"""
    manual_text, manual_mtime, _available = _load_manual_source(manual_path, candidates)
    return manual_text, manual_mtime


def _load_manual_source(manual_path: Optional[str], candidates: List[str]) -> Tuple[str, Optional[str], bool]:
    """返回 (正文或错误提示, 文件时间, 说明书是否可用)；不可用时正文就是给用户看的提示句。"""
    if not manual_path:
        if not candidates:
            try:
                current_app.logger.warning("scheduler manual path resolution failed: BASE_DIR missing or empty")
            except Exception:
                g._aps_scheduler_manual_warning_status = "log_warning_failed"
            return (
                "找不到说明书文件：本机安装信息不完整。请联系维护人员检查安装目录。",
                None,
                False,
            )

        try:
            current_app.logger.warning("系统使用说明文件不存在（candidates=%s）", candidates)
        except Exception:
            g._aps_scheduler_manual_warning_status = "log_warning_failed"
        return "找不到说明书文件，可能安装包里没带或文件被删了。请联系维护人员。", None, False

    try:
        with open(manual_path, encoding="utf-8") as f:
            manual_text = f.read()
        return manual_text, _format_manual_mtime(manual_path), True
    except Exception:
        current_app.logger.exception("读取系统使用说明失败")
        return "说明书加载失败。请刷新重试；仍不行请联系维护人员。", None, False


def _build_manual_download_url(manual_path: Optional[str], safe_src: Optional[str], safe_page: Optional[str]) -> Optional[str]:
    if not manual_path:
        return None

    download_values: Dict[str, Any] = {}
    if safe_src:
        download_values["src"] = safe_src
    if safe_page:
        download_values["page"] = safe_page
    return url_for("scheduler.config_manual_download", **download_values)


def _manual_section_map(manual_text: str) -> Dict[str, Dict[str, Any]]:
    """把说明书按标题切块：{标题文字: {"anchor", "level", "source"}}。

    每一段的 source 从该标题起，一直收到下一个同级或更高级标题之前，所以子标题会跟着父章节一起
    显示。同名标题只认第一个；注册表测试保证登记的标题在说明书里唯一。
    """
    blocks = manual_blocks(manual_text)
    sections: Dict[str, Dict[str, Any]] = {}
    for index, block in enumerate(blocks):
        title = block["title"]
        if not title or title in sections:
            continue
        parts = [block["source"]]
        for follower in blocks[index + 1:]:
            if follower["level"] <= block["level"]:
                break
            parts.append(follower["source"])
        sections[title] = {"anchor": block["anchor"], "level": block["level"], "source": "".join(parts)}
    return sections


def _build_related_manual_links(
    entry: Dict[str, Any], link_src: str, sections: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for view_id in entry.get("related", ()):
        related = manual_entry(view_id)
        if related is None:
            raise ValueError(f"page_manuals_registry related view is not registered: {view_id!r}")
        section = sections.get(related["heading"])
        out.append({
            "view": view_id,
            "manual_id": view_id,
            "title": related["title"],
            "summary": related["summary"],
            "url": _build_manual_page_url(link_src, view_id),
            "full_manual_section_url": _build_full_manual_section_url(link_src, section["anchor"]) if section else "",
            "preview_sections": [],
        })
    return out


def _resolve_page_back_action(entry: Dict[str, Any], back_url: Optional[str]) -> Tuple[str, str]:
    """有站内 src 就回刚才页面；没有就回这个视图本身，按钮文字带视图名。"""
    if back_url:
        return back_url, "返回刚才页面"
    return _workbench_view_url(entry["view"]), "返回" + entry["title"]


def _build_manual_page_view_state(
    *,
    entry: Optional[Dict[str, Any]],
    manual_text: str,
    manual_available: bool,
    link_src: str,
    back_url: Optional[str],
) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "manual_mode": "full",
        "current_manual": None,
        "related_manuals": [],
        "fallback_text": manual_text,
        "full_manual_section_url": "",
        "page_title": FULL_MANUAL_TITLE,
        "download_button_label": "下载说明书原文",
        "back_button_label": "返回刚才页面",
        "back_url": back_url,
        "page_warning": None,
    }
    if entry is None:
        return state

    state["back_url"], state["back_button_label"] = _resolve_page_back_action(entry, back_url)
    sections = _manual_section_map(manual_text) if manual_available else {}
    section = sections.get(entry["heading"])
    if section is None:
        # 说明书读不到时正文已经是错误提示，不再叠加提示；能读到却找不到标题说明注册表和原文脱节，
        # 记日志并退化为整本，让用户至少能看到全文。
        if manual_available:
            current_app.logger.warning(
                "page manual heading %r for view %r not found in scheduler manual", entry["heading"], entry["view"]
            )
            state["page_warning"] = PAGE_SECTION_MISSING_WARNING
        return state

    state.update({
        "manual_mode": "page",
        "current_manual": {
            "view": entry["view"],
            "manual_id": entry["view"],
            "title": entry["title"],
            "summary": entry["summary"],
            "heading": entry["heading"],
            "anchor": section["anchor"],
            "full_manual_label": FULL_MANUAL_LABEL,
        },
        "related_manuals": _build_related_manual_links(entry, link_src, sections),
        "fallback_text": section["source"],
        "full_manual_section_url": _build_full_manual_section_url(link_src, section["anchor"]),
        "page_title": "本页说明 - " + entry["title"],
        "download_button_label": "下载整本说明书",
    })
    return state


@bp.get("/scheduler/config/manual")
def config_manual_page():
    """
    系统使用说明（面向计划/工艺新手）。
    - 页内把 Markdown 转成 HTML 后展示（转换器在 legacy_presentation，不新增依赖）
    - ``page=<视图 id>`` 时先显示该视图的章节，并给整本说明书的锚点
    - 提供下载原始 md
    """
    raw_src = (request.args.get("src") or "").strip()
    raw_page = (request.args.get("page") or "").strip()
    safe_src, safe_page, entry, page_warning = _normalize_scheduler_manual_args(raw_src, raw_page)
    link_src = safe_src or ""
    back_url = _resolve_manual_back_url(safe_src)
    manual_path, candidates = _resolve_scheduler_manual_md_path()
    manual_text, manual_mtime, manual_available = _load_manual_source(manual_path, candidates)
    download_url = _build_manual_download_url(manual_path, safe_src, safe_page)
    view_state = _build_manual_page_view_state(
        entry=entry,
        manual_text=manual_text,
        manual_available=manual_available,
        link_src=link_src,
        back_url=back_url,
    )
    for warning in (page_warning, view_state["page_warning"]):
        if warning:
            flash(warning, "warning")

    return render_template(
        'workbench/manual.html',
        title=view_state["page_title"],
        manual_mode=view_state["manual_mode"],
        manual_text=manual_text,
        manual_available=manual_available,
        fallback_text=view_state["fallback_text"],
        manual_mtime=manual_mtime,
        download_url=download_url,
        back_url=view_state["back_url"],
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
    safe_src, safe_page, _entry, _page_warning = _normalize_scheduler_manual_args(raw_src, raw_page)
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
