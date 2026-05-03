from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import AppError
from core.services.scheduler import ConfigService
from web.error_boundary import user_visible_app_error_message
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
)

from ...navigation_utils import _safe_next_url
from .scheduler_bp import bp
from .scheduler_config_display_state import (
    build_auto_assign_persist_display_state,
    build_config_degraded_display_state,
    get_scheduler_visible_config_field_metadata,
)
from .scheduler_config_feedback import (
    _flash_config_save_outcome,
    _flash_preset_apply_feedback,
    _format_preset_error_flash,
)


def _warn_scheduler_config_degraded_once(fields: List[str], *, hidden_warnings: Optional[List[str]] = None) -> None:
    normalized = [str(field).strip() for field in fields if str(field).strip()]
    normalized.extend(str(item).strip() for item in (hidden_warnings or []) if str(item).strip())
    if not normalized or getattr(g, "_aps_scheduler_config_degraded_warned", False):
        return
    g._aps_scheduler_config_degraded_warned = True
    current_app.logger.warning("scheduler config page rendering degraded snapshot fields=%s", normalized)


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
    safe_src = normalize_manual_src(raw_src)
    bundle = build_page_manual_bundle(raw_page) if raw_page else None
    safe_page = raw_page if bundle else None
    page_warning = None
    if raw_page and safe_page is None:
        page_warning = f"未找到页面说明：{raw_page}，已改为打开整本说明。"
    return safe_src, safe_page, bundle, page_warning


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
        if not candidates:
            try:
                current_app.logger.warning("scheduler manual path resolution failed: BASE_DIR missing or empty")
            except Exception:
                g._aps_scheduler_manual_warning_status = "log_warning_failed"
            return (
                "系统找不到使用说明文件：BASE_DIR 未配置或为空，请联系管理员检查软件安装目录。",
                None,
            )

        try:
            current_app.logger.warning("系统使用说明文件不存在（candidates=%s）", candidates)
        except Exception:
            g._aps_scheduler_manual_warning_status = "log_warning_failed"
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
    safe_src, safe_page, _bundle, _page_warning = _normalize_scheduler_manual_args(raw_src, raw_page)
    manual_path, candidates = _resolve_scheduler_manual_md_path()
    if not manual_path:
        if not candidates:
            flash("系统找不到使用说明文件：BASE_DIR 未配置或为空，请联系管理员检查软件安装目录。", "error")
            return redirect(_build_manual_page_url(safe_src, safe_page))
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
    cfg = cfg_svc.get_snapshot(strict_mode=False)
    strategies = cfg_svc.get_available_strategies()
    config_field_metadata = get_scheduler_visible_config_field_metadata()
    config_field_warnings, config_degraded_fields, config_hidden_warnings = build_config_degraded_display_state(
        cfg,
        config_field_metadata=config_field_metadata,
    )
    _warn_scheduler_config_degraded_once(config_degraded_fields, hidden_warnings=config_hidden_warnings)
    holiday_default_efficiency_display_value = float(cfg.holiday_default_efficiency)
    holiday_default_efficiency_degraded = "holiday_default_efficiency" in config_field_warnings
    holiday_default_efficiency_warning = config_field_warnings.get("holiday_default_efficiency")

    preset_display_state = cfg_svc.get_preset_display_state(readonly=True, current_snapshot=cfg)
    presets = list(preset_display_state.get("presets") or [])
    active_preset = preset_display_state.get("active_preset")
    builtin_presets = [
        ConfigService.BUILTIN_PRESET_DEFAULT,
        ConfigService.BUILTIN_PRESET_DUE_FIRST,
        ConfigService.BUILTIN_PRESET_MIN_CHANGEOVER,
        ConfigService.BUILTIN_PRESET_IMPROVE_SLOW,
    ]
    current_config_state = dict(preset_display_state.get("current_config_state") or {})
    auto_assign_persist_state = build_auto_assign_persist_display_state(getattr(cfg, "auto_assign_persist", None))

    return render_template(
        "scheduler/config.html",
        title="排产高级设置",
        cfg=cfg,
        strategies=strategies,
        config_field_metadata=config_field_metadata,
        config_field_warnings=config_field_warnings,
        config_degraded_fields=config_degraded_fields,
        config_hidden_warnings=config_hidden_warnings,
        holiday_default_efficiency_display_value=holiday_default_efficiency_display_value,
        holiday_default_efficiency_degraded=holiday_default_efficiency_degraded,
        holiday_default_efficiency_warning=holiday_default_efficiency_warning,
        presets=presets,
        active_preset=active_preset,
        builtin_presets=builtin_presets,
        current_config_state=current_config_state,
        auto_assign_persist_state=auto_assign_persist_state,
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
    next_url = _safe_next_url(request.form.get("next")) or url_for("scheduler.config_page")
    try:
        # 允许显式切回“自定义”（不改变任何参数，仅更新 active_preset）
        name_text = _normalize_requested_preset_name(name)
        if _is_custom_preset_name(name_text):
            cfg_svc.mark_active_preset_custom()
            flash("已切换为：当前手动设置。", "success")
            return redirect(next_url)
        applied = cfg_svc.apply_preset(name)
        _flash_preset_apply_feedback(applied)
    except AppError as e:
        flash(user_visible_app_error_message(e), "error")
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
        if str(saved.get("status") or "").strip() == "rejected":
            error_field = str(saved.get("error_field") or "").strip()
            error_fields = list(saved.get("error_fields") or [])
            error_message = str(saved.get("error_message") or "当前配置未保存为方案。").strip()
            flash(
                _format_preset_error_flash(error_field=error_field, error_fields=error_fields, error_message=error_message),
                "error",
            )
        else:
            flash(
                f"已保存为方案：{saved.get('effective_active_preset') or saved.get('requested_preset')}",
                "success",
            )
    except AppError as e:
        flash(user_visible_app_error_message(e), "error")
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
        flash(user_visible_app_error_message(e), "error")
    except Exception:
        current_app.logger.exception("删除排产模板失败")
        flash("删除方案失败，请稍后重试。", "error")
    return redirect(url_for("scheduler.config_page"))


def _collect_scheduler_config_form_payload(form) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key in (
        "sort_strategy",
        "priority_weight",
        "due_weight",
        "holiday_default_efficiency",
        "prefer_primary_skill",
        "enforce_ready_default",
        "dispatch_mode",
        "dispatch_rule",
        "auto_assign_enabled",
        "ortools_enabled",
        "ortools_time_limit_seconds",
        "algo_mode",
        "objective",
        "time_budget_seconds",
        "freeze_window_enabled",
        "freeze_window_days",
    ):
        if key not in form:
            continue
        payload[key] = form.get(key)
    return payload


def _normalize_requested_preset_name(name: Optional[str]) -> str:
    return ("" if name is None else str(name)).strip()


def _is_custom_preset_name(name_text: str) -> bool:
    return name_text == "" or name_text.lower() == str(ConfigService.ACTIVE_PRESET_CUSTOM).lower()


@bp.post("/config")
def update_config():
    cfg_svc = g.services.config_service
    try:
        payload = _collect_scheduler_config_form_payload(request.form)
        outcome = cfg_svc.save_page_config(payload)
        _flash_config_save_outcome(outcome)
    except AppError as e:
        flash(user_visible_app_error_message(e), "error")
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
