from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional, Tuple

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import AppError, ValidationError
from core.services.scheduler import ConfigService

from web.ui_mode import render_ui_template as render_template

from .scheduler_bp import bp
from .system_utils import _safe_next_url


def _resolve_scheduler_manual_md_path() -> Tuple[Optional[str], List[str]]:
    """
    解析“排产调度说明书”的 md 文件路径。

    说明：
    - app.py / app_new_ui.py 的 static_folder 不同，因此这里同时尝试多个候选路径
    - 返回：(命中的路径 or None, 所有候选路径)
    """
    candidates: List[str] = []
    try:
        if getattr(current_app, "static_folder", None):
            candidates.append(os.path.join(str(current_app.static_folder), "docs", "scheduler_manual.md"))
    except Exception:
        pass

    base_dir = None
    try:
        base_dir = current_app.config.get("BASE_DIR")
    except Exception:
        base_dir = None

    if base_dir:
        candidates.append(os.path.join(str(base_dir), "static", "docs", "scheduler_manual.md"))
        candidates.append(os.path.join(str(base_dir), "web_new_test", "static", "docs", "scheduler_manual.md"))

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


@bp.get("/config/manual")
def config_manual_page():
    """
    排产调度说明书（面向计划/工艺新手）。
    - 原样展示 Markdown（不做渲染，避免新增依赖）
    - 提供下载原始 md
    """
    manual_path, candidates = _resolve_scheduler_manual_md_path()
    manual_text = ""
    manual_mtime = None
    if manual_path:
        try:
            with open(manual_path, "r", encoding="utf-8") as f:
                manual_text = f.read()
            try:
                manual_mtime = datetime.fromtimestamp(os.path.getmtime(manual_path)).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                manual_mtime = None
        except Exception:
            current_app.logger.exception("读取排产调度说明书失败")
            manual_text = "说明书加载失败，请稍后重试或联系管理员。"
            manual_mtime = None
    else:
        # 候选路径仅写日志，避免渲染给用户（信息泄露）
        try:
            current_app.logger.warning("排产调度说明书文件不存在（candidates=%s）", candidates)
        except Exception:
            pass
        manual_text = "说明书文件缺失（可能是安装包未包含或文件被误删）。请联系管理员。"

    download_url = url_for("scheduler.config_manual_download") if manual_path else None
    return render_template(
        "scheduler/config_manual.html",
        title="排产调度说明书",
        manual_text=manual_text,
        manual_mtime=manual_mtime,
        download_url=download_url,
    )


@bp.get("/config/manual/download")
def config_manual_download():
    """
    下载原始说明书 Markdown。
    """
    manual_path, _candidates = _resolve_scheduler_manual_md_path()
    if not manual_path:
        flash("说明书文件不存在，无法下载。", "error")
        return redirect(url_for("scheduler.config_manual_page"))
    try:
        return send_file(
            manual_path,
            as_attachment=True,
            download_name="排产调度说明书.md",
            mimetype="text/markdown; charset=utf-8",
        )
    except Exception:
        current_app.logger.exception("下载排产调度说明书失败")
        flash("下载说明书失败，请稍后重试。", "error")
        return redirect(url_for("scheduler.config_manual_page"))


@bp.get("/config")
def config_page():
    """
    排产高级设置（二级页）：
    - 解释说明更充分
    - 后续承载“配置模板/方案”
    """
    cfg_svc = ConfigService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    cfg = cfg_svc.get_snapshot()
    strategies = cfg_svc.get_available_strategies()

    presets = cfg_svc.list_presets()
    active_preset = cfg_svc.get_active_preset()
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
        builtin_presets=builtin_presets,
    )


@bp.post("/config/preset/apply")
def preset_apply():
    """
    应用模板/方案：
    - 可从主页面/高级设置页触发
    - 支持 next 回跳
    """
    cfg_svc = ConfigService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    name = request.form.get("preset_name") or request.form.get("name")
    next_url = _safe_next_url(request.form.get("next") or url_for("scheduler.config_page"))
    try:
        # 允许显式切回“自定义”（不改变任何参数，仅更新 active_preset）
        name_text = ("" if name is None else str(name)).strip()
        if name_text == "" or name_text.lower() == str(ConfigService.ACTIVE_PRESET_CUSTOM).lower():
            cfg_svc.mark_active_preset_custom()
            flash("已切换为：自定义（以当前高级设置为准）。", "success")
            return redirect(next_url)
        applied = cfg_svc.apply_preset(name)
        flash(f"已应用排产模板：{applied}", "success")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("应用排产模板失败")
        flash("应用模板失败，请稍后重试。", "error")
    return redirect(next_url)


@bp.post("/config/preset/save")
def preset_save():
    """
    将当前配置保存为新模板（不允许覆盖内置模板）。
    """
    cfg_svc = ConfigService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    name = request.form.get("preset_name") or request.form.get("name")
    try:
        saved = cfg_svc.save_preset(name)
        flash(f"已保存为模板：{saved}", "success")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("保存排产模板失败")
        flash("保存模板失败，请稍后重试。", "error")
    return redirect(url_for("scheduler.config_page"))


@bp.post("/config/preset/delete")
def preset_delete():
    cfg_svc = ConfigService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    name = request.form.get("preset_name") or request.form.get("name")
    try:
        cfg_svc.delete_preset(name)
        flash(f"已删除模板：{name}", "success")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("删除排产模板失败")
        flash("删除模板失败，请稍后重试。", "error")
    return redirect(url_for("scheduler.config_page"))


@bp.post("/config")
def update_config():
    cfg_svc = ConfigService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    strategy = request.form.get("sort_strategy")
    cfg_svc.set_strategy(strategy)
    # 工作日历：假期默认效率（用于未填效率时的兜底）
    cfg_svc.set_holiday_default_efficiency(request.form.get("holiday_default_efficiency"))
    cfg_svc.set_prefer_primary_skill(request.form.get("prefer_primary_skill"))
    # 排产页默认行为：是否默认启用“齐套约束”
    cfg_svc.set_enforce_ready_default(request.form.get("enforce_ready_default"))
    cfg_svc.set_dispatch(request.form.get("dispatch_mode"), request.form.get("dispatch_rule"))
    cfg_svc.set_auto_assign_enabled(request.form.get("auto_assign_enabled"))
    cfg_svc.set_ortools(request.form.get("ortools_enabled"), request.form.get("ortools_time_limit_seconds"))

    # 算法增强（默认关闭 improve）
    algo_mode = request.form.get("algo_mode")
    if algo_mode is not None:
        cfg_svc.set_algo_mode(algo_mode)
    objective = request.form.get("objective")
    if objective is not None:
        cfg_svc.set_objective(objective)
    tb = request.form.get("time_budget_seconds")
    if tb is not None and str(tb).strip():
        cfg_svc.set_time_budget_seconds(tb)
    cfg_svc.set_freeze_window(request.form.get("freeze_window_enabled"), request.form.get("freeze_window_days"))

    # 权重（仅暴露：优先级/交期；齐套权重为预留字段，当前不参与排产）
    pw = request.form.get("priority_weight")
    dw = request.form.get("due_weight")
    if (pw is not None and str(pw).strip()) or (dw is not None and str(dw).strip()):
        cur = cfg_svc.get_snapshot()
        # 允许只填一个：未填的用当前值
        pw_v = str(pw).strip() if pw is not None and str(pw).strip() else str(cur.priority_weight)
        dw_v = str(dw).strip() if dw is not None and str(dw).strip() else str(cur.due_weight)
        # 统一归一化（支持 0~1 或 0~100%）
        pw_f = cfg_svc.normalize_weight(pw_v, field="优先级权重")
        dw_f = cfg_svc.normalize_weight(dw_v, field="交期权重")
        rw_f = 1.0 - pw_f - dw_f
        if rw_f < -1e-9:
            raise ValidationError("优先级权重 + 交期权重 之和不能超过 1（或 100%）。", field="权重")
        # 防御：浮点误差
        rw_f = max(0.0, float(rw_f))
        cfg_svc.set_weights(pw_f, dw_f, rw_f, require_sum_1=True)

    # 手工保存参数后：标记为 custom（避免“模板名”与实际参数不一致）
    try:
        cfg_svc.mark_active_preset_custom()
    except Exception:
        pass

    flash("排产策略配置已保存。", "success")
    return redirect(url_for("scheduler.config_page"))


@bp.post("/config/default")
def restore_config_default():
    cfg_svc = ConfigService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    cfg_svc.restore_default()
    flash("已恢复默认权重与策略。", "success")
    return redirect(url_for("scheduler.config_page"))

