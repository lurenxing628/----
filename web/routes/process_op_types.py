from __future__ import annotations

from flask import flash, g, redirect, request, url_for

from web.ui_mode import render_ui_template as render_template

from core.services.process import OpTypeService

from .process_bp import bp
from .pagination import paginate_rows, parse_page_args


# ============================================================
# 工种配置（页面）
# ============================================================


@bp.get("/op-types")
def op_types_page():
    page, per_page = parse_page_args(request, default_per_page=100, max_per_page=300)
    svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    rows = [x.to_dict() for x in svc.list()]
    rows, pager = paginate_rows(rows, page, per_page)
    return render_template("process/op_types_list.html", title="工种配置", op_types=rows, pager=pager)


@bp.post("/op-types/create")
def create_op_type():
    op_type_id = request.form.get("op_type_id")
    name = request.form.get("name")
    category = request.form.get("category") or "internal"
    remark = request.form.get("remark")
    svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    ot = svc.create(op_type_id=op_type_id, name=name, category=category, remark=remark)
    flash(f"已创建工种：{ot.op_type_id} {ot.name}", "success")
    return redirect(url_for("process.op_type_detail", op_type_id=ot.op_type_id))


@bp.get("/op-types/<op_type_id>")
def op_type_detail(op_type_id: str):
    svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    ot = svc.get(op_type_id)
    return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type_id}", op_type=ot.to_dict())


@bp.post("/op-types/<op_type_id>/update")
def update_op_type(op_type_id: str):
    name = request.form.get("name")
    category = request.form.get("category")
    remark = request.form.get("remark")
    svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.update(op_type_id=op_type_id, name=name, category=category, remark=remark)
    flash("工种信息已保存。", "success")
    return redirect(url_for("process.op_type_detail", op_type_id=op_type_id))


@bp.post("/op-types/<op_type_id>/delete")
def delete_op_type(op_type_id: str):
    svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.delete(op_type_id)
    flash("已删除工种。", "success")
    return redirect(url_for("process.op_types_page"))

