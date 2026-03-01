from __future__ import annotations

from flask import flash, g, redirect, request, url_for

from core.models.enums import SupplierStatus
from core.services.process import OpTypeService, SupplierService
from web.ui_mode import render_ui_template as render_template

from .pagination import paginate_rows, parse_page_args
from .process_bp import bp

# ============================================================
# 供应商配置（页面）
# ============================================================


def _supplier_status_zh(status: str) -> str:
    if status == SupplierStatus.INACTIVE.value:
        return "停用"
    return "启用"


@bp.get("/suppliers")
def suppliers_page():
    page, per_page = parse_page_args(request, default_per_page=100, max_per_page=300)
    svc = SupplierService(g.db, op_logger=getattr(g, "op_logger", None))
    rows = [x.to_dict() for x in svc.list()]

    op_types = {ot.op_type_id: ot for ot in OpTypeService(g.db).list()}  # type: ignore[arg-type]
    view_rows = []
    for r in rows:
        ot = op_types.get(r.get("op_type_id") or "")
        view_rows.append(
            {
                **r,
                "status_zh": _supplier_status_zh(r.get("status") or SupplierStatus.ACTIVE.value),
                "op_type_name": (ot.name if ot else None),
            }
        )

    view_rows, pager = paginate_rows(view_rows, page, per_page)
    op_type_options = [(ot.op_type_id, ot.name) for ot in sorted(op_types.values(), key=lambda x: x.name)]
    return render_template(
        "process/suppliers_list.html",
        title="供应商配置",
        suppliers=view_rows,
        op_type_options=op_type_options,
        status_options=[(SupplierStatus.ACTIVE.value, "启用"), (SupplierStatus.INACTIVE.value, "停用")],
        pager=pager,
    )


@bp.post("/suppliers/create")
def create_supplier():
    supplier_id = request.form.get("supplier_id")
    name = request.form.get("name")
    op_type_id = request.form.get("op_type_id") or None
    default_days = request.form.get("default_days") or "1"
    status = request.form.get("status") or SupplierStatus.ACTIVE.value
    remark = request.form.get("remark")

    svc = SupplierService(g.db, op_logger=getattr(g, "op_logger", None))
    s = svc.create(
        supplier_id=supplier_id,
        name=name,
        op_type_value=op_type_id,
        default_days=default_days,
        status=status,
        remark=remark,
    )
    flash(f"已创建供应商：{s.supplier_id} {s.name}", "success")
    return redirect(url_for("process.supplier_detail", supplier_id=s.supplier_id))


@bp.get("/suppliers/<supplier_id>")
def supplier_detail(supplier_id: str):
    svc = SupplierService(g.db, op_logger=getattr(g, "op_logger", None))
    s = svc.get(supplier_id)
    op_types = {ot.op_type_id: ot for ot in OpTypeService(g.db).list()}  # type: ignore[arg-type]
    op_type_options = [(ot.op_type_id, ot.name) for ot in sorted(op_types.values(), key=lambda x: x.name)]

    return render_template(
        "process/supplier_detail.html",
        title=f"供应商详情 - {s.supplier_id}",
        supplier=s.to_dict(),
        op_type_name=(op_types.get(s.op_type_id or "")).name if s.op_type_id and op_types.get(s.op_type_id) else None,
        op_type_options=op_type_options,
        status_options=[(SupplierStatus.ACTIVE.value, "启用"), (SupplierStatus.INACTIVE.value, "停用")],
        supplier_status_zh=_supplier_status_zh(s.status),
    )


@bp.post("/suppliers/<supplier_id>/update")
def update_supplier(supplier_id: str):
    name = request.form.get("name")
    op_type_id = request.form.get("op_type_id")
    default_days = request.form.get("default_days")
    status = request.form.get("status")
    remark = request.form.get("remark")

    svc = SupplierService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.update(
        supplier_id=supplier_id,
        name=name,
        op_type_value=op_type_id,
        default_days=default_days,
        status=status,
        remark=remark,
    )
    flash("供应商信息已保存。", "success")
    return redirect(url_for("process.supplier_detail", supplier_id=supplier_id))


@bp.post("/suppliers/<supplier_id>/delete")
def delete_supplier(supplier_id: str):
    svc = SupplierService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.delete(supplier_id)
    flash("已删除供应商。", "success")
    return redirect(url_for("process.suppliers_page"))

