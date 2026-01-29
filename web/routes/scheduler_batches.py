from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List

from flask import flash, g, redirect, request, url_for

from web.ui_mode import render_ui_template as render_template

from core.infrastructure.errors import AppError
from core.services.scheduler import BatchService, ConfigService
from data.repositories import PartRepository, ScheduleHistoryRepository

from .scheduler_bp import bp, _batch_status_zh, _priority_zh, _ready_zh


@bp.get("/")
def batches_page():
    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    cfg_svc = ConfigService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))

    # 兼容：允许 ?status= 表示“全部状态”；未提供 status 参数时默认 pending
    if "status" in request.args:
        status = (request.args.get("status") or "").strip()
    else:
        status = "pending"
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

    cfg = cfg_svc.get_snapshot()
    strategies = cfg_svc.get_available_strategies()
    presets = cfg_svc.list_presets()
    active_preset = cfg_svc.get_active_preset()

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
        cfg=cfg,
        strategies=strategies,
        presets=presets,
        active_preset=active_preset,
        latest_history=latest_history,
        latest_summary=latest_summary,
        default_start_dt=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d 08:00"),
    )


@bp.get("/batches")
def batches_manage_page():
    """
    批次管理（二级页）：
    - 新增批次
    - 批量复制/删除/修改
    - 查看/编辑批次详情入口
    """
    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))

    # 兼容：允许 ?status= 表示“全部状态”；未提供 status 参数时默认 pending
    if "status" in request.args:
        status = (request.args.get("status") or "").strip()
    else:
        status = "pending"
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

    return render_template(
        "scheduler/batches_manage.html",
        title="批次管理",
        batches=view_rows,
        status=status,
        only_ready=only_ready,
        part_options=part_options,
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
        return redirect(url_for("scheduler.batches_manage_page"))


@bp.post("/batches/<batch_id>/delete")
def delete_batch(batch_id: str):
    batch_svc = BatchService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    try:
        batch_svc.delete(batch_id)
        flash(f"已删除批次：{batch_id}", "success")
        return redirect(url_for("scheduler.batches_manage_page"))
    except AppError as e:
        flash(e.message, "error")
        return redirect(url_for("scheduler.batch_detail", batch_id=batch_id))


@bp.post("/batches/bulk/delete")
def bulk_delete_batches():
    batch_ids = request.form.getlist("batch_ids")
    if not batch_ids:
        flash("请至少选择 1 个批次。", "error")
        return redirect(url_for("scheduler.batches_manage_page"))

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
    return redirect(url_for("scheduler.batches_manage_page"))


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
        return redirect(url_for("scheduler.batches_manage_page"))

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
    return redirect(url_for("scheduler.batches_manage_page"))


@bp.post("/batches/bulk/update")
def bulk_update_batches():
    batch_ids = request.form.getlist("batch_ids")
    if not batch_ids:
        flash("请至少选择 1 个批次。", "error")
        return redirect(url_for("scheduler.batches_manage_page"))

    priority = (request.form.get("bulk_priority") or "").strip() or None
    due_date = (request.form.get("bulk_due_date") or "").strip() or None
    remark = request.form.get("bulk_remark")
    remark = (remark.strip() if remark is not None else None) or None

    if priority is None and due_date is None and remark is None:
        flash("未填写任何要批量修改的字段（优先级/交期/备注）。", "error")
        return redirect(url_for("scheduler.batches_manage_page"))

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
    return redirect(url_for("scheduler.batches_manage_page"))


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

