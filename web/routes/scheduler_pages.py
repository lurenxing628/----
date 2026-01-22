from __future__ import annotations

import json
from typing import Any, Dict, List

from flask import flash, g, redirect, render_template, request, url_for

from core.infrastructure.errors import AppError
from core.services.scheduler import BatchService, CalendarService, ConfigService, ScheduleService
from data.repositories import MachineRepository, OperatorRepository, PartRepository, ScheduleHistoryRepository, SupplierRepository

from .scheduler_bp import bp, _batch_status_zh, _day_type_zh, _priority_zh, _ready_zh


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
    )


@bp.post("/batches/create")
def create_batch():
    batch_id = request.form.get("batch_id")
    part_no = request.form.get("part_no")
    quantity = request.form.get("quantity")
    due_date = request.form.get("due_date") or None
    priority = request.form.get("priority") or "normal"
    ready_status = request.form.get("ready_status") or "no"
    remark = request.form.get("remark") or None
    auto_gen = (request.form.get("auto_generate_ops") or "").strip().lower() in ("1", "true", "on", "yes")

    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    if auto_gen:
        b = batch_svc.create_batch_from_template(
            batch_id=batch_id,
            part_no=part_no,
            quantity=quantity,
            due_date=due_date,
            priority=priority,
            ready_status=ready_status,
            remark=remark,
            rebuild_ops=False,
        )
        flash(f"已创建批次并生成工序：{b.batch_id}（共 {len(batch_svc.list_operations(b.batch_id))} 道工序）", "success")
    else:
        b = batch_svc.create(
            batch_id=batch_id,
            part_no=part_no,
            quantity=quantity,
            due_date=due_date,
            priority=priority,
            ready_status=ready_status,
            remark=remark,
        )
        flash(f"已创建批次：{b.batch_id}", "success")

    return redirect(url_for("scheduler.batch_detail", batch_id=b.batch_id))


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
    if machine_ids_needed and operator_ids_needed:
        m_list = sorted(machine_ids_needed)
        o_list = sorted(operator_ids_needed)
        m_placeholders = ",".join(["?"] * len(m_list))
        o_placeholders = ",".join(["?"] * len(o_list))
        link_rows = g.db.execute(
            f"""
            SELECT machine_id, operator_id
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
    )


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
    sch_svc = ScheduleService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    try:
        result = sch_svc.run_schedule(batch_ids=batch_ids, created_by="web")
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

    # 权重：若用户填写则更新；否则保持不变
    pw = request.form.get("priority_weight")
    dw = request.form.get("due_weight")
    rw = request.form.get("ready_weight")
    if pw is not None and dw is not None and rw is not None and (str(pw).strip() or str(dw).strip() or str(rw).strip()):
        cfg_svc.set_weights(pw, dw, rw, require_sum_1=True)

    flash("排产策略配置已保存。", "success")
    return redirect(url_for("scheduler.batches_page"))


@bp.post("/config/default")
def restore_config_default():
    cfg_svc = ConfigService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    cfg_svc.restore_default()
    flash("已恢复默认权重与策略。", "success")
    return redirect(url_for("scheduler.batches_page"))


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
    efficiency = request.form.get("efficiency")
    allow_normal = request.form.get("allow_normal")
    allow_urgent = request.form.get("allow_urgent")
    remark = request.form.get("remark")

    cal_svc = CalendarService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    cal_svc.upsert(
        date_value=date_value,
        day_type=day_type,
        shift_hours=shift_hours,
        efficiency=efficiency,
        allow_normal=allow_normal,
        allow_urgent=allow_urgent,
        remark=remark,
    )
    flash("日历配置已保存。", "success")
    return redirect(url_for("scheduler.calendar_page"))

