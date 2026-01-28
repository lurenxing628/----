from __future__ import annotations

from flask import flash, g, redirect, request, url_for

from core.infrastructure.errors import ValidationError
from core.services.scheduler import ConfigService

from .scheduler_bp import bp


@bp.post("/config")
def update_config():
    cfg_svc = ConfigService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    strategy = request.form.get("sort_strategy")
    cfg_svc.set_strategy(strategy)
    cfg_svc.set_prefer_primary_skill(request.form.get("prefer_primary_skill"))
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

    flash("排产策略配置已保存。", "success")
    return redirect(url_for("scheduler.batches_page"))


@bp.post("/config/default")
def restore_config_default():
    cfg_svc = ConfigService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    cfg_svc.restore_default()
    flash("已恢复默认权重与策略。", "success")
    return redirect(url_for("scheduler.batches_page"))

