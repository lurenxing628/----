from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint, current_app, flash, g, redirect, request, url_for

from core.infrastructure.errors import AppError, ValidationError
from core.models.enums import MaterialStatus
from core.services.material import BatchMaterialService, MaterialService
from core.services.scheduler import BatchService
from web.ui_mode import render_ui_template as render_template

from .pagination import paginate_rows, parse_page_args

bp = Blueprint("material", __name__)


@bp.get("/")
def index():
    return redirect(url_for("material.materials_page"))


@bp.get("/materials")
def materials_page():
    page, per_page = parse_page_args(request, default_per_page=100, max_per_page=300)
    svc = MaterialService(g.db, op_logger=getattr(g, "op_logger", None))
    items = [m.to_dict() for m in svc.list()]
    items, pager = paginate_rows(items, page, per_page)
    return render_template(
        "material/materials.html",
        title="物料管理 - 物料主数据",
        materials=items,
        status_options=[(MaterialStatus.ACTIVE.value, "可用"), (MaterialStatus.INACTIVE.value, "停用")],
        pager=pager,
    )


@bp.post("/materials/create")
def materials_create():
    try:
        svc = MaterialService(g.db, op_logger=getattr(g, "op_logger", None))
        m = svc.create(
            material_id=request.form.get("material_id"),
            name=request.form.get("name"),
            spec=request.form.get("spec"),
            unit=request.form.get("unit"),
            stock_qty=request.form.get("stock_qty"),
            status=request.form.get("status") or MaterialStatus.ACTIVE.value,
            remark=request.form.get("remark"),
        )
        flash(f"已创建物料：{m.material_id} {m.name}", "success")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("创建物料失败")
        flash("创建物料失败，请稍后重试。", "error")
    return redirect(url_for("material.materials_page"))


@bp.post("/materials/<material_id>/update")
def materials_update(material_id: str):
    try:
        svc = MaterialService(g.db, op_logger=getattr(g, "op_logger", None))
        svc.update(
            material_id,
            name=request.form.get("name"),
            spec=request.form.get("spec"),
            unit=request.form.get("unit"),
            stock_qty=request.form.get("stock_qty"),
            status=request.form.get("status"),
            remark=request.form.get("remark"),
        )
        flash("物料已更新。", "success")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("更新物料失败（material_id=%s）", material_id)
        flash("更新物料失败，请稍后重试。", "error")
    return redirect(url_for("material.materials_page"))


@bp.post("/materials/<material_id>/delete")
def materials_delete(material_id: str):
    try:
        svc = MaterialService(g.db, op_logger=getattr(g, "op_logger", None))
        svc.delete(material_id)
        flash("物料已删除。", "success")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("删除物料失败（material_id=%s）", material_id)
        flash("删除物料失败，请稍后重试。", "error")
    return redirect(url_for("material.materials_page"))


# ============================================================
# 批次物料需求 / 齐套判定
# ============================================================


@bp.get("/batches")
def batch_materials_page():
    batch_id = (request.args.get("batch_id") or "").strip() or None

    batch_svc = BatchService(g.db, op_logger=getattr(g, "op_logger", None))
    batches = batch_svc.list()
    batch_options = [(b.batch_id, f"{b.batch_id}（{b.part_no} x {b.quantity}）") for b in batches]
    ready_summary = {"yes": 0, "partial": 0, "no": 0, "unknown": 0}
    for b in batches:
        rs = (getattr(b, "ready_status", "") or "").strip().lower()
        if rs in ready_summary:
            ready_summary[rs] += 1
        else:
            ready_summary["unknown"] += 1

    batch_map = {str(getattr(b, "batch_id", "") or ""): b for b in batches}
    selected_batch = batch_map.get(batch_id) if batch_id else None

    req_rows: List[Dict[str, Any]] = []
    if batch_id:
        req_rows = BatchMaterialService(g.db, op_logger=getattr(g, "op_logger", None)).list_for_batch(batch_id)

    mats = MaterialService(g.db, op_logger=getattr(g, "op_logger", None)).list(status=MaterialStatus.ACTIVE.value)
    mat_options = [(m.material_id, f"{m.material_id} {m.name}".strip()) for m in mats]

    return render_template(
        "material/batch_materials.html",
        title="物料管理 - 批次物料需求",
        batch_id=batch_id,
        batch_options=batch_options,
        batch=(selected_batch.to_dict() if selected_batch else None),
        requirements=req_rows,
        material_options=mat_options,
        ready_summary=ready_summary,
    )


@bp.post("/batches/<batch_id>/requirements/add")
def batch_material_add(batch_id: str):
    try:
        svc = BatchMaterialService(g.db, op_logger=getattr(g, "op_logger", None))
        svc.add_requirement(
            batch_id=batch_id,
            material_id=request.form.get("material_id"),
            required_qty=request.form.get("required_qty"),
            available_qty=request.form.get("available_qty") or 0,
        )
        flash("已新增批次物料需求，并已同步齐套状态。", "success")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("新增批次物料需求失败（batch_id=%s）", batch_id)
        flash("新增失败，请稍后重试。", "error")
    return redirect(url_for("material.batch_materials_page", batch_id=batch_id))


@bp.post("/requirements/<int:bm_id>/update")
def batch_material_update(bm_id: int):
    batch_id = (request.form.get("batch_id") or "").strip()
    if not batch_id:
        raise ValidationError("缺少批次号", field="batch_id")
    try:
        svc = BatchMaterialService(g.db, op_logger=getattr(g, "op_logger", None))
        svc.update_requirement(
            bm_id,
            required_qty=request.form.get("required_qty"),
            available_qty=request.form.get("available_qty"),
        )
        flash("已更新批次物料，并已同步齐套状态。", "success")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("更新批次物料需求失败（bm_id=%s, batch_id=%s）", bm_id, batch_id)
        flash("更新失败，请稍后重试。", "error")
    return redirect(url_for("material.batch_materials_page", batch_id=batch_id))


@bp.post("/requirements/<int:bm_id>/delete")
def batch_material_delete(bm_id: int):
    batch_id = (request.form.get("batch_id") or "").strip()
    if not batch_id:
        raise ValidationError("缺少批次号", field="batch_id")
    try:
        svc = BatchMaterialService(g.db, op_logger=getattr(g, "op_logger", None))
        svc.delete_requirement(bm_id)
        flash("已删除批次物料需求，并已同步齐套状态。", "success")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("删除批次物料需求失败（bm_id=%s, batch_id=%s）", bm_id, batch_id)
        flash("删除失败，请稍后重试。", "error")
    return redirect(url_for("material.batch_materials_page", batch_id=batch_id))

