from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import AppError, ValidationError
from core.services.scheduler import ConfigService
from web.ui_mode import (
    get_full_manual_section_url,
    get_manual_url,
    normalize_manual_src,
)
from web.ui_mode import (
    render_ui_template as render_template,
)
from web.viewmodels.page_manuals import (
    MANUAL_ENTRY_ENDPOINTS,
    build_page_fallback_text,
    build_page_manual_bundle,
    resolve_manual_id,
)

from .scheduler_bp import bp
from .system_utils import _safe_next_url


def _resolve_scheduler_manual_md_path() -> Tuple[Optional[str], List[str]]:
    """
    解析“系统使用说明”的 md 文件路径。

    说明：
    - 事实源固定为仓库根目录下的 static/docs/scheduler_manual.md
    - current_app.static_folder 仅作为同路径兼容兜底，不再读取 v2 镜像副本
    - 返回：(命中的路径 or None, 所有候选路径)
    """
    candidates: List[str] = []
    base_dir = None
    try:
        base_dir = current_app.config.get("BASE_DIR")
    except Exception:
        base_dir = None

    if base_dir:
        candidates.append(os.path.join(str(base_dir), "static", "docs", "scheduler_manual.md"))

    static_folder = getattr(current_app, "static_folder", None)
    if static_folder:
        candidates.append(os.path.join(str(static_folder), "docs", "scheduler_manual.md"))

    # 去重 + 绝对化
    normalized: List[str] = []
    seen = set()
    for p in candidates:
        if not p:
            continue
        try:
            ap = os.path.abspath(p)
        except Exception:
            ap = p
        if ap in seen:
            continue
        seen.add(ap)
        normalized.append(ap)

    for p in normalized:
        try:
            if os.path.isfile(p):
                return p, normalized
        except Exception:
            continue

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


def _resolve_manual_entry_endpoint(manual_id: Optional[str]) -> Optional[str]:
    target = str(manual_id or "").strip()
    if not target:
        return None
    return MANUAL_ENTRY_ENDPOINTS.get(target)


def _format_manual_mtime(manual_path: str) -> Optional[str]:
    try:
        return datetime.fromtimestamp(os.path.getmtime(manual_path)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _load_manual_text_and_mtime(manual_path: Optional[str], candidates: List[str]) -> Tuple[str, Optional[str]]:
    if not manual_path:
        try:
            current_app.logger.warning("系统使用说明文件不存在（candidates=%s）", candidates)
        except Exception:
            pass
        return "说明书文件缺失（可能是安装包未包含或文件被误删）。请联系管理员。", None

    try:
        with open(manual_path, encoding="utf-8") as f:
            manual_text = f.read()
        return manual_text, _format_manual_mtime(manual_path)
    except Exception:
        current_app.logger.exception("读取系统使用说明失败")
        return "说明书加载失败，请稍后重试或联系管理员。", None


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


@bp.get("/config/manual")
def config_manual_page():
    """
    系统使用说明（面向计划/工艺新手）。
    - 原样展示 Markdown（不做渲染，避免新增依赖）
    - 提供下载原始 md
    """
    raw_src = (request.args.get("src") or "").strip()
    raw_page = (request.args.get("page") or "").strip()
    safe_src = normalize_manual_src(raw_src)
    bundle = build_page_manual_bundle(raw_page) if raw_page else None
    safe_page = raw_page if bundle else None
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
        "scheduler/config_manual.html",
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


@bp.get("/config/manual/download")
def config_manual_download():
    """
    下载原始说明书 Markdown。
    """
    raw_src = (request.args.get("src") or "").strip()
    raw_page = (request.args.get("page") or "").strip()
    safe_src = normalize_manual_src(raw_src)
    safe_page = raw_page if raw_page and resolve_manual_id(raw_page) is not None else None
    manual_path, _candidates = _resolve_scheduler_manual_md_path()
    if not manual_path:
        flash("说明书文件不存在，无法下载。", "error")
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
        flash("下载说明书失败，请稍后重试。", "error")
        return redirect(_build_manual_page_url(safe_src, safe_page))


@bp.get("/config")
def config_page():
    """
    排产高级设置（二级页）：
    - 解释说明更充分
    - 后续承载“配置模板/方案”
    """
    cfg_svc = g.services.config_service
    cfg = cfg_svc.get_snapshot()
    strategies = cfg_svc.get_available_strategies()

    presets = cfg_svc.list_presets()
    active_preset = cfg_svc.get_active_preset()
    active_preset_reason = cfg_svc.get_active_preset_reason()
    builtin_presets = [
        ConfigService.BUILTIN_PRESET_DEFAULT,
        ConfigService.BUILTIN_PRESET_DUE_FIRST,
        ConfigService.BUILTIN_PRESET_MIN_CHANGEOVER,
        ConfigService.BUILTIN_PRESET_IMPROVE_SLOW,
    ]

    return render_template(
        "scheduler/config.html",
        title="排产高级设置",
        cfg=cfg,
        strategies=strategies,
        presets=presets,
        active_preset=active_preset,
        active_preset_reason=active_preset_reason,
        builtin_presets=builtin_presets,
    )


@bp.post("/config/preset/apply")
def preset_apply():
    """
    应用模板/方案：
    - 可从主页面/高级设置页触发
    - 支持 next 回跳
    """
    cfg_svc = g.services.config_service
    name = request.form.get("preset_name") or request.form.get("name")
    next_url = _safe_next_url(request.form.get("next") or url_for("scheduler.config_page"))
    try:
        # 允许显式切回“自定义”（不改变任何参数，仅更新 active_preset）
        name_text = ("" if name is None else str(name)).strip()
        if name_text == "" or name_text.lower() == str(ConfigService.ACTIVE_PRESET_CUSTOM).lower():
            cfg_svc.mark_active_preset_custom()
            flash("已切换为：当前手动设置。", "success")
            return redirect(next_url)
        applied = cfg_svc.apply_preset(name)
        flash(f"已应用方案：{applied}", "success")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("应用排产模板失败")
        flash("应用方案失败，请稍后重试。", "error")
    return redirect(next_url)


@bp.post("/config/preset/save")
def preset_save():
    """
    将当前配置保存为新模板（不允许覆盖内置模板）。
    """
    cfg_svc = g.services.config_service
    name = request.form.get("preset_name") or request.form.get("name")
    try:
        saved = cfg_svc.save_preset(name)
        flash(f"已保存为方案：{saved}", "success")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("保存排产模板失败")
        flash("保存方案失败，请稍后重试。", "error")
    return redirect(url_for("scheduler.config_page"))


@bp.post("/config/preset/delete")
def preset_delete():
    cfg_svc = g.services.config_service
    name = request.form.get("preset_name") or request.form.get("name")
    try:
        cfg_svc.delete_preset(name)
        flash(f"已删除方案：{name}", "success")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("删除排产模板失败")
        flash("删除方案失败，请稍后重试。", "error")
    return redirect(url_for("scheduler.config_page"))


def _apply_basic_scheduler_config(cfg_svc: ConfigService, form) -> None:
    cfg_svc.set_strategy(form.get("sort_strategy"))
    cfg_svc.set_holiday_default_efficiency(form.get("holiday_default_efficiency"))
    cfg_svc.set_prefer_primary_skill(form.get("prefer_primary_skill"))
    cfg_svc.set_enforce_ready_default(form.get("enforce_ready_default"))
    cfg_svc.set_dispatch(form.get("dispatch_mode"), form.get("dispatch_rule"))
    cfg_svc.set_auto_assign_enabled(form.get("auto_assign_enabled"))
    cfg_svc.set_ortools(form.get("ortools_enabled"), form.get("ortools_time_limit_seconds"))

    algo_mode = form.get("algo_mode")
    if algo_mode is not None:
        cfg_svc.set_algo_mode(algo_mode)

    objective = form.get("objective")
    if objective is not None:
        cfg_svc.set_objective(objective)

    tb = form.get("time_budget_seconds")
    if tb is not None and str(tb).strip():
        cfg_svc.set_time_budget_seconds(tb)

    cfg_svc.set_freeze_window(form.get("freeze_window_enabled"), form.get("freeze_window_days"))


def _apply_weight_settings_if_present(cfg_svc: ConfigService, form) -> None:
    pw = form.get("priority_weight")
    dw = form.get("due_weight")
    if not ((pw is not None and str(pw).strip()) or (dw is not None and str(dw).strip())):
        return

    cur = cfg_svc.get_snapshot()
    pw_v = str(pw).strip() if pw is not None and str(pw).strip() else str(cur.priority_weight)
    dw_v = str(dw).strip() if dw is not None and str(dw).strip() else str(cur.due_weight)
    pw_f = cfg_svc.normalize_weight(pw_v, field="优先级权重")
    dw_f = cfg_svc.normalize_weight(dw_v, field="交期权重")
    rw_f = 1.0 - pw_f - dw_f
    if rw_f < -1e-9:
        raise ValidationError("优先级权重 + 交期权重 之和不能超过 1（或 100%）。", field="权重")
    cfg_svc.set_weights(pw_f, dw_f, max(0.0, float(rw_f)), require_sum_1=True)


@bp.post("/config")
def update_config():
    cfg_svc = g.services.config_service
    try:
        form = request.form
        _apply_basic_scheduler_config(cfg_svc, form)
        _apply_weight_settings_if_present(cfg_svc, form)
        flash("排产策略配置已保存。", "success")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("保存排产配置失败")
        flash("保存排产配置失败，请稍后重试。", "error")
    return redirect(url_for("scheduler.config_page"))


@bp.post("/config/default")
def restore_config_default():
    cfg_svc = g.services.config_service
    cfg_svc.restore_default()
    flash("已恢复默认设置。", "success")
    return redirect(url_for("scheduler.config_page"))

