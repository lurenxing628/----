from __future__ import annotations

from flask import flash, g, redirect, request, url_for

from core.infrastructure.errors import AppError, ValidationError
from core.services.scheduler import ConfigService

from web.ui_mode import render_ui_template as render_template

from .scheduler_bp import bp


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
    next_url = request.form.get("next") or url_for("scheduler.config_page")
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
    except Exception as e:
        flash(f"应用模板失败：{e}", "error")
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
    except Exception as e:
        flash(f"保存模板失败：{e}", "error")
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
    except Exception as e:
        flash(f"删除模板失败：{e}", "error")
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

