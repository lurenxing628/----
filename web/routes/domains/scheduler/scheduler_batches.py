from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from flask import current_app, flash, g, redirect, request, url_for

from core.infrastructure.errors import AppError
from web.ui_mode import render_ui_template as render_template

from ...excel_utils import strict_mode_enabled as _strict_mode_enabled
from ...navigation_utils import _safe_next_url
from ...normalizers import _parse_result_summary_payload
from ...pagination import paginate_rows, parse_page_args
from .scheduler_bp import (
    _batch_status_zh,
    _normalize_warning_texts,
    _priority_zh,
    _ready_zh,
    _surface_schedule_warnings,
    bp,
)

if TYPE_CHECKING:
    from core.services.scheduler import BatchService


@bp.get("/")
def batches_page():
    services = g.services
    batch_svc = services.batch_service
    cfg_svc = services.config_service

    # 兼容：允许 ?status= 表示“全部状态”；未提供 status 参数时默认 pending
    if "status" in request.args:
        status = (request.args.get("status") or "").strip()
    else:
        status = "pending"
    only_ready = (request.args.get("only_ready") or "").strip()  # yes/no/partial or empty

    page, per_page = parse_page_args(request, default_per_page=100, max_per_page=300)
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

    view_rows, pager = paginate_rows(view_rows, page, per_page)
    cfg = cfg_svc.get_snapshot()
    strategies = cfg_svc.get_available_strategies()
    presets = cfg_svc.list_presets()
    active_preset = cfg_svc.get_active_preset()
    active_preset_reason = cfg_svc.get_active_preset_reason()

    # 最近一次排产（用于用户确认“留痕已写入”）
    latest_history = None
    latest_summary = None
    hist_q = services.schedule_history_query_service
    try:
        items = hist_q.list_recent(limit=1)
        latest_history = items[0].to_dict() if items else None
    except Exception:
        current_app.logger.exception("排产页读取最近一次排产历史失败")
        latest_history = None
        latest_summary = None
    if latest_history and latest_history.get("result_summary"):
        latest_summary = _parse_result_summary_payload(latest_history.get("result_summary"), version=latest_history.get("version"), log_label="排产页")
    latest_warning_messages = _normalize_warning_texts((latest_summary or {}).get("warnings") if isinstance(latest_summary, dict) else None)
    latest_warning_preview = latest_warning_messages[:3]
    latest_warning_total = len(latest_warning_messages)
    latest_warning_hidden_count = max(0, latest_warning_total - len(latest_warning_preview))

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
        active_preset_reason=active_preset_reason,
        latest_history=latest_history,
        latest_summary=latest_summary,
        latest_warning_preview=latest_warning_preview,
        latest_warning_total=latest_warning_total,
        latest_warning_hidden_count=latest_warning_hidden_count,
        default_start_dt=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d 08:00"),
        pager=pager,
    )


@bp.get("/batches")
def batches_manage_page():
    """
    批次管理（二级页）：
    - 新增批次
    - 批量复制/删除/修改
    - 查看/编辑批次详情入口
    """
    services = g.services
    batch_svc = services.batch_service

    # 兼容：允许 ?status= 表示“全部状态”；未提供 status 参数时默认 pending
    if "status" in request.args:
        status = (request.args.get("status") or "").strip()
    else:
        status = "pending"
    only_ready = (request.args.get("only_ready") or "").strip()  # yes/no/partial or empty

    page, per_page = parse_page_args(request, default_per_page=100, max_per_page=300)
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

    view_rows, pager = paginate_rows(view_rows, page, per_page)
    part_svc = services.part_service
    parts = part_svc.list()
    part_options = [(p.part_no, f"{p.part_no} {p.part_name}") for p in parts]

    return render_template(
        "scheduler/batches_manage.html",
        title="批次管理",
        batches=view_rows,
        status=status,
        only_ready=only_ready,
        part_options=part_options,
        pager=pager,
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
    strict_mode = _strict_mode_enabled(request.form.get("strict_mode"))
    remark = request.form.get("remark") or None

    batch_svc = g.services.batch_service
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
            strict_mode=strict_mode,
        )
        flash(f"已创建批次并生成工序：{b.batch_id}（共 {len(batch_svc.list_operations(b.batch_id))} 道工序）", "success")
        _surface_schedule_warnings(batch_svc.consume_user_visible_warnings(), limit=3)
        return redirect(url_for("scheduler.batch_detail", batch_id=b.batch_id))
    except AppError as e:
        flash(e.message, "error")
        return redirect(url_for("scheduler.batches_manage_page"))


@bp.post("/batches/<batch_id>/delete")
def delete_batch(batch_id: str):
    batch_svc = g.services.batch_service
    next_raw = (request.form.get("next") or "").strip()
    next_url = _safe_next_url(next_raw) if next_raw else None
    try:
        batch_svc.delete(batch_id)
        flash(f"已删除批次：{batch_id}", "success")
        if next_url:
            return redirect(next_url)
        return redirect(url_for("scheduler.batches_manage_page"))
    except AppError as e:
        flash(e.message, "error")
        if next_url:
            return redirect(next_url)
        return redirect(url_for("scheduler.batch_detail", batch_id=batch_id))


@bp.post("/batches/bulk/delete")
def bulk_delete_batches():
    batch_ids = request.form.getlist("batch_ids")
    if not batch_ids:
        flash("请至少选择 1 个批次。", "error")
        return redirect(url_for("scheduler.batches_manage_page"))

    batch_svc = g.services.batch_service
    ok = 0
    failed: List[str] = []
    failed_details: List[str] = []
    for bid in batch_ids:
        try:
            batch_svc.delete(bid)
            ok += 1
        except AppError as e:
            failed.append(str(bid))
            failed_details.append(f"{bid}: {e.message}")
            continue
        except Exception:
            current_app.logger.exception("批量删除批次失败（batch_id=%s）", bid)
            failed.append(str(bid))
            failed_details.append(f"{bid}: 内部错误，请查看日志")
            continue

    flash(f"批量删除完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        sample = "；".join(failed_details[:10])
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


def _bulk_update_one_batch(
    batch_svc: BatchService,
    bid: str,
    *,
    priority: Optional[str],
    due_date: Optional[str],
    remark: Optional[str],
) -> Optional[str]:
    try:
        kwargs: Dict[str, Any] = {"batch_id": bid}
        if due_date is not None:
            kwargs["due_date"] = due_date
        if priority is not None:
            kwargs["priority"] = priority
        if remark is not None:
            kwargs["remark"] = remark
        batch_svc.update(**kwargs)
        return None
    except AppError as e:
        return f"{bid}（{e.message}）"
    except Exception:
        current_app.logger.exception("批量修改批次失败（batch_id=%s）", bid)
        return f"{bid}（系统错误）"



@bp.post("/batches/bulk/copy")
def bulk_copy_batches():
    batch_ids = request.form.getlist("batch_ids")
    if not batch_ids:
        flash("请至少选择 1 个批次。", "error")
        return redirect(url_for("scheduler.batches_manage_page"))

    batch_svc = g.services.batch_service
    ok = 0
    failed: List[str] = []
    mappings: List[str] = []
    for bid in batch_ids:
        try:
            new_id = _next_batch_id_like(str(bid), exists_fn=lambda x: batch_svc.batch_repo.get(x) is not None)
            b2 = batch_svc.copy_batch(bid, new_id)
            ok += 1
            mappings.append(f"{bid}→{b2.batch_id}")
        except AppError as e:
            failed.append(f"{bid}（{e.message}）")
            continue
        except Exception:
            current_app.logger.exception("批量复制批次失败（batch_id=%s）", bid)
            failed.append(f"{bid}（系统错误）")
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

    batch_svc = g.services.batch_service
    ok = 0
    failed: List[str] = []
    for bid in batch_ids:
        err = _bulk_update_one_batch(batch_svc, str(bid), priority=priority, due_date=due_date, remark=remark)
        if err is None:
            ok += 1
        else:
            failed.append(err)

    flash(f"批量修改完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        flash("失败原因（最多 5 条）：" + "；".join(failed[:5]), "warning")
    return redirect(url_for("scheduler.batches_manage_page"))


@bp.post("/batches/<batch_id>/generate-ops")
def generate_ops(batch_id: str):
    batch_svc = g.services.batch_service
    strict_mode = _strict_mode_enabled(request.form.get("strict_mode"))
    b = batch_svc.get(batch_id)

    try:
        batch_svc.create_batch_from_template(
            batch_id=b.batch_id,
            part_no=b.part_no,
            quantity=b.quantity,
            due_date=b.due_date,
            priority=b.priority,
            ready_status=b.ready_status,
            remark=b.remark,
            rebuild_ops=True,
            strict_mode=strict_mode,
        )
        cnt = len(batch_svc.list_operations(b.batch_id))
        flash(f"已重建批次工序：共 {cnt} 道工序。", "success")
        _surface_schedule_warnings(batch_svc.consume_user_visible_warnings(), limit=3)
    except AppError as e:
        flash(e.message, "error")
    return redirect(url_for("scheduler.batch_detail", batch_id=b.batch_id))
