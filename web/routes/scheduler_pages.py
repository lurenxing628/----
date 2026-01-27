from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from flask import flash, g, redirect, render_template, request, url_for

from core.infrastructure.errors import AppError, ValidationError
from core.services.scheduler import BatchService, CalendarService, ConfigService, ScheduleService
from data.repositories import MachineRepository, OperatorRepository, PartRepository, ScheduleHistoryRepository, SupplierRepository

from .scheduler_bp import bp, _batch_status_zh, _day_type_zh, _priority_zh, _ready_zh


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or str(v).strip() == "":
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or str(v).strip() == "":
            return int(default)
        return int(float(v))
    except Exception:
        return int(default)


def _extract_metrics_from_summary(summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    algo = summary.get("algo") if isinstance(summary, dict) else None
    if isinstance(algo, dict):
        m = algo.get("metrics")
        if isinstance(m, dict) and m:
            return m
    return None


def _build_svg_polyline(values: List[Tuple[int, float]], *, width: int = 520, height: int = 120, pad: int = 18) -> Optional[Dict[str, Any]]:
    """
    把 (x_label, y) 序列转为简单折线图（SVG polyline）。
    - 不依赖任何外部 JS/库，适合 Win7 离线环境。
    """
    if not values:
        return None
    vals = [(int(x), float(y)) for x, y in values]
    if len(vals) < 2:
        return None

    ys = [y for _, y in vals]
    y_min = min(ys)
    y_max = max(ys)
    rng = (y_max - y_min) if (y_max - y_min) != 0 else 1.0

    xs = [x for x, _ in vals]
    x_min = min(xs)
    x_max = max(xs)
    x_rng = (x_max - x_min) if (x_max - x_min) != 0 else 1.0
    x_span = float(width - 2 * pad)
    y_span = float(height - 2 * pad)

    pts: List[Tuple[float, float]] = []
    for x0, y in vals:
        xx = float(pad) + ((float(x0) - float(x_min)) / float(x_rng)) * x_span
        # y 越大越靠上：反向映射到画布坐标
        yy = float(height - pad) - ((float(y) - float(y_min)) / rng) * y_span
        pts.append((xx, yy))

    points_str = " ".join([f"{round(x, 2)},{round(y, 2)}" for x, y in pts])
    last_xy = pts[-1]
    return {
        "width": int(width),
        "height": int(height),
        "pad": int(pad),
        "points": points_str,
        "y_min": float(y_min),
        "y_max": float(y_max),
        "last_x": float(last_xy[0]),
        "last_y": float(last_xy[1]),
        "x_labels": [x for x, _ in vals],
    }


@bp.get("/")
def batches_page():
    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    cfg_svc = ConfigService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))

    status = (request.args.get("status") or "pending").strip()
    only_ready = (request.args.get("only_ready") or "").strip()  # yes/no/partial or empty

    batches = batch_svc.list(status=status if status else None)
    view_rows: List[Dict[str, Any]] = []
    for b in batches:
        if only_ready and (b.ready_status or "") != only_ready:
            continue
        view_rows.append(
            {
                **b.to_dict(),
                "priority_zh": _priority_zh(b.priority),
                "ready_status_zh": _ready_zh(b.ready_status),
                "status_zh": _batch_status_zh(b.status),
            }
        )

    parts = PartRepository(g.db).list()
    part_options = [(p.part_no, f"{p.part_no} {p.part_name}") for p in parts]

    cfg = cfg_svc.get_snapshot()
    strategies = cfg_svc.get_available_strategies()

    # 最近一次排产（用于用户确认“留痕已写入”）
    latest_history = None
    latest_summary = None
    try:
        items = ScheduleHistoryRepository(g.db).list_recent(limit=1)
        latest_history = items[0].to_dict() if items else None
        if latest_history and latest_history.get("result_summary"):
            latest_summary = json.loads(latest_history.get("result_summary") or "{}")
    except Exception:
        latest_history = None
        latest_summary = None

    return render_template(
        "scheduler/batches.html",
        title="排产调度",
        batches=view_rows,
        status=status,
        only_ready=only_ready,
        part_options=part_options,
        cfg=cfg,
        strategies=strategies,
        latest_history=latest_history,
        latest_summary=latest_summary,
        default_start_dt=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d 08:00"),
    )


@bp.post("/batches/create")
def create_batch():
    batch_id = request.form.get("batch_id")
    part_no = request.form.get("part_no")
    quantity = request.form.get("quantity")
    due_date = request.form.get("due_date") or None
    priority = request.form.get("priority") or "normal"
    ready_status = request.form.get("ready_status") or "yes"
    ready_date = request.form.get("ready_date") or None
    remark = request.form.get("remark") or None

    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    try:
        # 创建批次默认强制生成工序（从零件模板；缺模板时会尝试自动解析 route_raw）
        b = batch_svc.create_batch_from_template(
            batch_id=batch_id,
            part_no=part_no,
            quantity=quantity,
            due_date=due_date,
            priority=priority,
            ready_status=ready_status,
            ready_date=ready_date,
            remark=remark,
            rebuild_ops=False,
        )
        flash(f"已创建批次并生成工序：{b.batch_id}（共 {len(batch_svc.list_operations(b.batch_id))} 道工序）", "success")
        return redirect(url_for("scheduler.batch_detail", batch_id=b.batch_id))
    except AppError as e:
        flash(e.message, "error")
        return redirect(url_for("scheduler.batches_page"))


@bp.get("/batches/<batch_id>")
def batch_detail(batch_id: str):
    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    sch_svc = ScheduleService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))

    b = batch_svc.get(batch_id)
    ops = sch_svc.list_batch_operations(batch_id=b.batch_id)

    # 预收集：当前批次内部工序已选的设备/人员（用于回显，即使其已停用/维修）
    selected_machine_ids = set()
    selected_operator_ids = set()
    for op in ops:
        if (op.source or "").strip() != "internal":
            continue
        if op.machine_id:
            selected_machine_ids.add(op.machine_id)
        if op.operator_id:
            selected_operator_ids.add(op.operator_id)

    # 下拉选项：默认只给“启用/在岗”的资源，减少误选
    m_repo = MachineRepository(g.db)
    o_repo = OperatorRepository(g.db)
    machines_active = m_repo.list(status="active")
    operators_active = o_repo.list(status="active")
    suppliers = SupplierRepository(g.db).list(status="active")

    # 为了让用户能定位问题：若历史上已选过停用/维修资源，也回显在下拉中（但禁用）
    machines_by_id = {m.machine_id: m for m in machines_active}
    for mid in sorted(selected_machine_ids):
        if mid in machines_by_id:
            continue
        extra = m_repo.get(mid)
        if extra:
            machines_by_id[extra.machine_id] = extra

    operators_by_id = {o.operator_id: o for o in operators_active}
    for oid in sorted(selected_operator_ids):
        if oid in operators_by_id:
            continue
        extra = o_repo.get(oid)
        if extra:
            operators_by_id[extra.operator_id] = extra

    # 供模板渲染：value/label/disabled（disabled=非 active，用于只回显不可选）
    machine_options: List[Dict[str, Any]] = []
    for m in sorted(machines_by_id.values(), key=lambda x: (x.status != "active", x.machine_id)):
        disabled = (m.status or "").strip() != "active"
        status_note = f"（不可用：{m.status}）" if disabled else ""
        machine_options.append({"value": m.machine_id, "label": f"{m.machine_id} {m.name}{status_note}", "disabled": disabled})

    operator_options: List[Dict[str, Any]] = []
    for o in sorted(operators_by_id.values(), key=lambda x: (x.status != "active", x.operator_id)):
        disabled = (o.status or "").strip() != "active"
        status_note = f"（不可用：{o.status}）" if disabled else ""
        operator_options.append({"value": o.operator_id, "label": f"{o.operator_id} {o.name}{status_note}", "disabled": disabled})

    supplier_options = [(s.supplier_id, f"{s.supplier_id} {s.name}") for s in suppliers]

    # 构建人机映射（用于批次详情页的“设备/人员”双向联动）。为避免过重，仅保留本页涉及的资源。
    active_machine_ids = [x["value"] for x in machine_options if not x.get("disabled")]
    active_operator_ids = [x["value"] for x in operator_options if not x.get("disabled")]
    machine_ids_needed = set(active_machine_ids) | set(selected_machine_ids)
    operator_ids_needed = set(active_operator_ids) | set(selected_operator_ids)

    machine_operators: Dict[str, List[str]] = {}
    operator_machines: Dict[str, List[str]] = {}
    machine_operator_meta: Dict[str, Dict[str, Dict[str, Any]]] = {}
    if machine_ids_needed and operator_ids_needed:
        m_list = sorted(machine_ids_needed)
        o_list = sorted(operator_ids_needed)
        m_placeholders = ",".join(["?"] * len(m_list))
        o_placeholders = ",".join(["?"] * len(o_list))
        link_rows = g.db.execute(
            f"""
            SELECT machine_id, operator_id, skill_level, is_primary
            FROM OperatorMachine
            WHERE machine_id IN ({m_placeholders}) AND operator_id IN ({o_placeholders})
            ORDER BY machine_id, operator_id
            """,
            tuple(m_list + o_list),
        ).fetchall()
        for r in link_rows:
            mc_id = r["machine_id"]
            op_id = r["operator_id"]
            machine_operators.setdefault(mc_id, []).append(op_id)
            operator_machines.setdefault(op_id, []).append(mc_id)
            machine_operator_meta.setdefault(mc_id, {})[op_id] = {
                "skill_level": r["skill_level"],
                "is_primary": r["is_primary"],
            }

    view_ops: List[Dict[str, Any]] = []
    for op in ops:
        d = op.to_dict()
        hint = sch_svc.get_external_merge_hint(op.id)
        d["merge_hint"] = hint
        view_ops.append(d)

    return render_template(
        "scheduler/batch_detail.html",
        title=f"批次详情 - {b.batch_id}",
        batch=b.to_dict(),
        batch_status_zh=_batch_status_zh(b.status),
        priority_zh=_priority_zh(b.priority),
        ready_status_zh=_ready_zh(b.ready_status),
        operations=view_ops,
        machine_options=machine_options,
        operator_options=operator_options,
        supplier_options=supplier_options,
        machine_operators=machine_operators,
        operator_machines=operator_machines,
        machine_operator_meta=machine_operator_meta,
        prefer_primary_skill=ConfigService(g.db).get_snapshot().prefer_primary_skill,
    )


@bp.post("/batches/<batch_id>/delete")
def delete_batch(batch_id: str):
    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    try:
        batch_svc.delete(batch_id)
        flash(f"已删除批次：{batch_id}", "success")
        return redirect(url_for("scheduler.batches_page"))
    except AppError as e:
        flash(e.message, "error")
        return redirect(url_for("scheduler.batch_detail", batch_id=batch_id))


@bp.post("/batches/bulk/delete")
def bulk_delete_batches():
    batch_ids = request.form.getlist("batch_ids")
    if not batch_ids:
        flash("请至少选择 1 个批次。", "error")
        return redirect(url_for("scheduler.batches_page"))

    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    ok = 0
    failed: List[str] = []
    for bid in batch_ids:
        try:
            batch_svc.delete(bid)
            ok += 1
        except Exception:
            failed.append(str(bid))
            continue

    flash(f"批量删除完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        sample = "，".join(failed[:10])
        flash(f"删除失败（最多展示 10 个）：{sample}", "warning")
    return redirect(url_for("scheduler.batches_page"))


def _next_batch_id_like(src: str, exists_fn) -> str:
    """
    将批次号末尾数字 +1，并在冲突时继续 +1，直到可用。
    示例：B001 -> B002；B009 -> B010。
    """
    s = (src or "").strip()
    m = re.match(r"^(.*?)(\d+)$", s)
    if not m:
        raise ValueError("批次号末尾必须包含数字，才能自动 +1（如：B001）")
    prefix, num_text = m.group(1), m.group(2)
    width = len(num_text)
    n = int(num_text)
    guard = 0
    while True:
        guard += 1
        if guard > 10000:
            raise ValueError("无法生成新批次号：尝试次数过多")
        n += 1
        cand = f"{prefix}{n:0{width}d}"
        if not exists_fn(cand):
            return cand


@bp.post("/batches/bulk/copy")
def bulk_copy_batches():
    batch_ids = request.form.getlist("batch_ids")
    if not batch_ids:
        flash("请至少选择 1 个批次。", "error")
        return redirect(url_for("scheduler.batches_page"))

    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    ok = 0
    failed: List[str] = []
    mappings: List[str] = []
    for bid in batch_ids:
        try:
            new_id = _next_batch_id_like(str(bid), exists_fn=lambda x: batch_svc.batch_repo.get(x) is not None)
            b2 = batch_svc.copy_batch(bid, new_id)
            ok += 1
            mappings.append(f"{bid}→{b2.batch_id}")
        except Exception as e:
            failed.append(f"{bid}（{e}）")
            continue

    flash(f"批量复制完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if mappings:
        flash("复制结果（最多 10 条）：" + "，".join(mappings[:10]), "success")
    if failed:
        flash("失败原因（最多 5 条）：" + "；".join(failed[:5]), "warning")
    return redirect(url_for("scheduler.batches_page"))


@bp.post("/batches/bulk/update")
def bulk_update_batches():
    batch_ids = request.form.getlist("batch_ids")
    if not batch_ids:
        flash("请至少选择 1 个批次。", "error")
        return redirect(url_for("scheduler.batches_page"))

    priority = (request.form.get("bulk_priority") or "").strip() or None
    due_date = (request.form.get("bulk_due_date") or "").strip() or None
    remark = request.form.get("bulk_remark")
    remark = (remark.strip() if remark is not None else None) or None

    if priority is None and due_date is None and remark is None:
        flash("未填写任何要批量修改的字段（优先级/交期/备注）。", "error")
        return redirect(url_for("scheduler.batches_page"))

    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    ok = 0
    failed: List[str] = []
    for bid in batch_ids:
        try:
            batch_svc.update(
                batch_id=bid,
                due_date=due_date if due_date is not None else None,
                priority=priority if priority is not None else None,
                remark=remark if remark is not None else None,
            )
            ok += 1
        except Exception as e:
            failed.append(f"{bid}（{e}）")
            continue

    flash(f"批量修改完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        flash("失败原因（最多 5 条）：" + "；".join(failed[:5]), "warning")
    return redirect(url_for("scheduler.batches_page"))


@bp.post("/batches/<batch_id>/generate-ops")
def generate_ops(batch_id: str):
    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    b = batch_svc.get(batch_id)

    batch_svc.create_batch_from_template(
        batch_id=b.batch_id,
        part_no=b.part_no,
        quantity=b.quantity,
        due_date=b.due_date,
        priority=b.priority,
        ready_status=b.ready_status,
        remark=b.remark,
        rebuild_ops=True,
    )
    cnt = len(batch_svc.list_operations(b.batch_id))
    flash(f"已重建批次工序：共 {cnt} 道工序。", "success")
    return redirect(url_for("scheduler.batch_detail", batch_id=b.batch_id))


@bp.post("/ops/<int:op_id>/update")
def update_op(op_id: int):
    sch_svc = ScheduleService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    op = sch_svc.get_operation(op_id)

    if op.source == "internal":
        machine_id = request.form.get("machine_id") or None
        operator_id = request.form.get("operator_id") or None
        setup_hours = request.form.get("setup_hours")
        unit_hours = request.form.get("unit_hours")
        sch_svc.update_internal_operation(
            op_id=op_id,
            machine_id=machine_id,
            operator_id=operator_id,
            setup_hours=setup_hours,
            unit_hours=unit_hours,
        )
        flash("内部工序已保存。", "success")
    else:
        supplier_id = request.form.get("supplier_id") or None
        ext_days = request.form.get("ext_days")
        # merged 外部组时 ext_days 可能被禁用（模板会传空），服务层会做限制/兜底
        sch_svc.update_external_operation(op_id=op_id, supplier_id=supplier_id, ext_days=ext_days)
        flash("外部工序已保存。", "success")

    return redirect(url_for("scheduler.batch_detail", batch_id=op.batch_id))

@bp.post("/run")
def run_schedule():
    """
    执行排产（Phase 7）。
    """
    batch_ids = request.form.getlist("batch_ids")
    start_dt = request.form.get("start_dt") or None
    end_date = request.form.get("end_date") or None
    sch_svc = ScheduleService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    try:
        result = sch_svc.run_schedule(batch_ids=batch_ids, start_dt=start_dt, end_date=end_date, created_by="web")
        ver = result.get("version")
        summary = result.get("summary") or {}
        overdue = result.get("overdue_batches") or []
        overdue_text = f"超期 {len(overdue)} 个" if overdue else "无超期"

        msg = (
            f"排产完成（版本 {ver}）：成功 {summary.get('scheduled_ops')}/{summary.get('total_ops')}，"
            f"失败 {summary.get('failed_ops')}。{overdue_text}。"
        )
        flash(msg, "success")

        if overdue:
            sample = "，".join([x.get("batch_id") for x in overdue[:10] if x.get("batch_id")])
            if sample:
                flash(f"超期批次（最多展示10个）：{sample}", "warning")

        # 有错误则补充提示（最多 5 条）
        errs = summary.get("errors") or []
        if errs:
            for e in errs[:5]:
                flash(str(e), "warning")
    except AppError as e:
        flash(e.message, "error")
    except Exception as e:
        flash(f"排产失败：{e}", "error")

    return redirect(url_for("scheduler.batches_page"))


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
        pw_f = cfg_svc._normalize_weight(pw_v, field="优先级权重")  # type: ignore[attr-defined]
        dw_f = cfg_svc._normalize_weight(dw_v, field="交期权重")  # type: ignore[attr-defined]
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


@bp.get("/analysis")
def analysis_page():
    """
    排产效果/优化分析：
    - 展示 result_summary.algo 中的指标、尝试列表（attempts），以及最近版本趋势。
    - 不依赖外网与第三方图表库（Win7 离线可用）。
    """
    repo = ScheduleHistoryRepository(g.db)
    versions = repo.list_versions(limit=50)

    ver_raw = (request.args.get("version") or "").strip()
    selected_ver: Optional[int] = None
    if ver_raw:
        try:
            selected_ver = int(ver_raw)
        except Exception:
            raise ValidationError("version 不合法（期望整数）", field="version")
    else:
        if versions:
            try:
                selected_ver = int(versions[0]["version"])
            except Exception:
                selected_ver = None

    # 趋势：取最近若干条 history（去重 version），抽取 algo.metrics
    raw_hist = repo.list_recent(limit=400)
    by_ver: Dict[int, Dict[str, Any]] = {}
    for h in raw_hist:
        d = h.to_dict()
        ver = _safe_int(d.get("version"), default=0)
        if ver <= 0 or ver in by_ver:
            continue
        rs = d.get("result_summary") or ""
        try:
            summary = json.loads(rs) if rs else {}
        except Exception:
            summary = {}
        metrics = _extract_metrics_from_summary(summary) or None
        if not metrics:
            continue
        algo = summary.get("algo") if isinstance(summary, dict) else None
        algo = algo if isinstance(algo, dict) else {}
        by_ver[int(ver)] = {
            "version": int(ver),
            "schedule_time": d.get("schedule_time"),
            "strategy": d.get("strategy"),
            "result_status": d.get("result_status"),
            "algo_mode": algo.get("mode"),
            "objective": algo.get("objective"),
            "metrics": metrics,
        }

    trend_all = sorted(by_ver.values(), key=lambda x: int(x.get("version") or 0))
    trend_rows = trend_all[-30:] if len(trend_all) > 30 else trend_all

    def _mval(row: Dict[str, Any], key: str) -> float:
        m = row.get("metrics") or {}
        if not isinstance(m, dict):
            return 0.0
        return _safe_float(m.get(key), default=0.0)

    trend_charts = {
        "overdue": _build_svg_polyline([(r["version"], _mval(r, "overdue_count")) for r in trend_rows]),
        "tardiness": _build_svg_polyline([(r["version"], _mval(r, "total_tardiness_hours")) for r in trend_rows]),
        "weighted_tardiness": _build_svg_polyline([(r["version"], _mval(r, "weighted_tardiness_hours")) for r in trend_rows]),
        "makespan": _build_svg_polyline([(r["version"], _mval(r, "makespan_hours")) for r in trend_rows]),
        "makespan_internal": _build_svg_polyline([(r["version"], _mval(r, "makespan_internal_hours")) for r in trend_rows]),
        "changeover": _build_svg_polyline([(r["version"], _mval(r, "changeover_count")) for r in trend_rows]),
        "machine_util": _build_svg_polyline([(r["version"], _mval(r, "machine_util_avg")) for r in trend_rows]),
        "operator_util": _build_svg_polyline([(r["version"], _mval(r, "operator_util_avg")) for r in trend_rows]),
    }

    selected = None
    selected_summary = None
    selected_metrics = None
    prev_metrics = None
    attempts_rows: List[Dict[str, Any]] = []
    objective_key = "overdue_count"
    trace_chart = None
    if selected_ver is not None:
        item = repo.get_by_version(int(selected_ver))
        if item:
            selected = item.to_dict()
            rs = selected.get("result_summary") or ""
            try:
                selected_summary = json.loads(rs) if rs else {}
            except Exception:
                selected_summary = None
            if isinstance(selected_summary, dict):
                selected_metrics = _extract_metrics_from_summary(selected_summary)
                algo = selected_summary.get("algo") if isinstance(selected_summary, dict) else None
                algo = algo if isinstance(algo, dict) else {}
                obj = str(algo.get("objective") or "min_overdue").strip()
                if obj == "min_tardiness":
                    objective_key = "total_tardiness_hours"
                elif obj == "min_changeover":
                    objective_key = "changeover_count"
                else:
                    objective_key = "overdue_count"

                attempts = algo.get("attempts") if isinstance(algo, dict) else None
                if isinstance(attempts, list):
                    for a in attempts:
                        if not isinstance(a, dict):
                            continue
                        m = a.get("metrics") if isinstance(a.get("metrics"), dict) else {}
                        score = a.get("score") if isinstance(a.get("score"), list) else []
                        attempts_rows.append(
                            {
                                "tag": a.get("tag") or "-",
                                "strategy": a.get("strategy") or "-",
                                "failed_ops": _safe_int(a.get("failed_ops"), default=0),
                                "score": score,
                                "metrics": m,
                                "primary_value": _safe_float(m.get(objective_key), default=0.0) if isinstance(m, dict) else 0.0,
                            }
                        )

                # 改进轨迹：仅记录“找到更优解”的点（按 elapsed_ms 展示）
                trace = algo.get("improvement_trace") if isinstance(algo, dict) else None
                trace_values: List[Tuple[int, float]] = []
                if isinstance(trace, list):
                    for t in trace:
                        if not isinstance(t, dict):
                            continue
                        ms = _safe_int(t.get("elapsed_ms"), default=0)
                        mm = t.get("metrics") if isinstance(t.get("metrics"), dict) else {}
                        pv = _safe_float(mm.get(objective_key), default=0.0) if isinstance(mm, dict) else 0.0
                        trace_values.append((int(ms), float(pv)))
                if len(trace_values) >= 2:
                    trace_values.sort(key=lambda x: x[0])
                    trace_chart = _build_svg_polyline(trace_values, width=520, height=120, pad=18)

                # 前一版本（有指标的最近一个版本）
                if trend_all:
                    prev = None
                    for r in reversed(trend_all):
                        if int(r.get("version") or 0) < int(selected_ver):
                            prev = r
                            break
                    if prev and isinstance(prev.get("metrics"), dict):
                        prev_metrics = prev.get("metrics")

    # attempts：按 score 字典序排序（越小越好），并计算条形宽度（值越大条越长）
    def _score_key(score: Any) -> Tuple[float, ...]:
        if not isinstance(score, list) or not score:
            return (float("inf"),)
        out: List[float] = []
        for x in score:
            try:
                out.append(float(x))
            except Exception:
                out.append(float("inf"))
        return tuple(out)

    attempts_rows_sorted = sorted(attempts_rows, key=lambda r: _score_key(r.get("score")))
    max_primary = 0.0
    if attempts_rows_sorted:
        max_primary = max([_safe_float(r.get("primary_value"), default=0.0) for r in attempts_rows_sorted] + [0.0])
    if selected_metrics and isinstance(selected_metrics, dict):
        max_primary = max(max_primary, _safe_float(selected_metrics.get(objective_key), default=0.0))
    if max_primary <= 0:
        max_primary = 0.0
    for r in attempts_rows_sorted:
        v = _safe_float(r.get("primary_value"), default=0.0)
        r["bar_pct"] = 0.0 if max_primary <= 0 else float(round((v / max_primary) * 100.0, 4))

    return render_template(
        "scheduler/analysis.html",
        title="排产优化分析",
        versions=versions,
        selected=selected,
        selected_summary=selected_summary,
        selected_metrics=selected_metrics,
        prev_metrics=prev_metrics,
        objective_key=objective_key,
        attempts=attempts_rows_sorted,
        trace_chart=trace_chart,
        trend_rows=trend_rows,
        trend_charts=trend_charts,
    )


@bp.get("/calendar")
def calendar_page():
    cal_svc = CalendarService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    rows = [c.to_dict() for c in cal_svc.list_all()]
    for r in rows:
        r["day_type_zh"] = _day_type_zh(r.get("day_type") or "")
    return render_template("scheduler/calendar.html", title="工作日历配置", rows=rows)


@bp.post("/calendar/upsert")
def calendar_upsert():
    date_value = request.form.get("date")
    day_type = request.form.get("day_type")
    shift_hours = request.form.get("shift_hours")
    shift_start = request.form.get("shift_start")
    shift_end = request.form.get("shift_end")
    efficiency = request.form.get("efficiency")
    allow_normal = request.form.get("allow_normal")
    allow_urgent = request.form.get("allow_urgent")
    remark = request.form.get("remark")

    cal_svc = CalendarService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    cal_svc.upsert(
        date_value=date_value,
        day_type=day_type,
        shift_hours=shift_hours,
        shift_start=shift_start,
        shift_end=shift_end,
        efficiency=efficiency,
        allow_normal=allow_normal,
        allow_urgent=allow_urgent,
        remark=remark,
    )
    flash("日历配置已保存。", "success")
    return redirect(url_for("scheduler.calendar_page"))

