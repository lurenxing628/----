from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from flask import current_app, flash, g, redirect, request, url_for

from core.infrastructure.errors import AppError
from core.models.enums import MergeMode, PartOperationStatus, SourceType, YesNo
from core.services.process import ExternalGroupService, PartService, SupplierService
from web.ui_mode import render_ui_template as render_template

from .pagination import paginate_rows, parse_page_args
from .process_bp import _merge_mode_zh, _source_zh, bp


def _strict_mode_enabled(raw_value: Any) -> bool:
    return str(raw_value or "").strip().lower() in {"1", "y", "yes", "true", "on"}


def _summarize_active_ops(ops: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int, int, int]:
    active_ops = [o for o in ops if o.get("status") == PartOperationStatus.ACTIVE.value]
    internal_count = sum(1 for o in active_ops if o.get("source") == SourceType.INTERNAL.value)
    external_count = sum(1 for o in active_ops if o.get("source") == SourceType.EXTERNAL.value)
    total_count = len(active_ops)
    return active_ops, total_count, internal_count, external_count


def _build_ops_by_group(active_ops: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    ops_by_group: Dict[str, List[Dict[str, Any]]] = {}
    for o in active_ops:
        gid = o.get("ext_group_id")
        if not gid:
            continue
        ops_by_group.setdefault(gid, []).append(o)
    for gid in ops_by_group:
        ops_by_group[gid].sort(key=lambda x: int(x.get("seq") or 0))
    return ops_by_group


@bp.get("/")
def list_parts():
    svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))
    page, per_page = parse_page_args(request, default_per_page=100, max_per_page=300)
    parts = svc.list()

    view_rows: List[Dict[str, Any]] = []
    for p in parts:
        route_short = (p.route_raw or "").strip()
        if len(route_short) > 48:
            route_short = route_short[:48] + "..."
        view_rows.append(
            {
                "part_no": p.part_no,
                "part_name": p.part_name,
                "route_raw": p.route_raw,
                "route_short": route_short if route_short else None,
                "route_parsed": p.route_parsed,
                "route_parsed_zh": "已解析" if p.route_parsed == YesNo.YES.value else "未解析",
            }
        )

    view_rows, pager = paginate_rows(view_rows, page, per_page)
    return render_template("process/list.html", title="工艺管理", parts=view_rows, pager=pager)


@bp.post("/parts/create")
def create_part():
    part_no = request.form.get("part_no")
    part_name = request.form.get("part_name")
    route_raw = request.form.get("route_raw")
    remark = request.form.get("remark")
    strict_mode = _strict_mode_enabled(request.form.get("strict_mode"))

    svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))
    try:
        p = svc.create(part_no=part_no, part_name=part_name, route_raw=route_raw, remark=remark, strict_mode=strict_mode)
        flash(f"已创建零件：{p.part_no} {p.part_name}", "success")
        return redirect(url_for("process.part_detail", part_no=p.part_no))
    except AppError as e:
        flash(e.message, "error")
        return redirect(url_for("process.list_parts"))


@bp.get("/parts/<part_no>")
def part_detail(part_no: str):
    p_svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))

    detail = p_svc.get_template_detail(part_no)
    part = detail["part"].to_dict()
    ops = [o.to_dict() for o in detail["operations"]]
    groups = [gr.to_dict() for gr in detail["groups"]]

    # 统计
    active_ops, total_count, internal_count, external_count = _summarize_active_ops(ops)

    # 供应商名称映射（用于展示）
    suppliers = {s.supplier_id: s for s in SupplierService(g.db).list()}  # type: ignore[arg-type]

    # deletable group（按规则控制按钮）
    deletable_group_ids = set(p_svc.calc_deletable_external_group_ids(part_no))

    # 组内工序列表
    ops_by_group = _build_ops_by_group(active_ops)

    # 组对象映射
    group_map = {g["group_id"]: g for g in groups}

    return render_template(
        "process/detail.html",
        title=f"工序模板 - {part.get('part_no')} {part.get('part_name')}",
        part=part,
        operations=ops,
        active_operations=active_ops,
        total_count=total_count,
        internal_count=internal_count,
        external_count=external_count,
        groups=groups,
        group_map=group_map,
        ops_by_group=ops_by_group,
        suppliers_map={k: v.to_dict() for k, v in suppliers.items()},
        deletable_group_ids=deletable_group_ids,
        source_zh=_source_zh,
        merge_mode_zh=_merge_mode_zh,
    )


@bp.post("/parts/<part_no>/update")
def update_part(part_no: str):
    part_name = request.form.get("part_name")
    route_raw = request.form.get("route_raw")
    remark = request.form.get("remark")
    svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.update(part_no=part_no, part_name=part_name, route_raw=route_raw, remark=remark)
    flash("零件信息已保存。", "success")
    return redirect(url_for("process.part_detail", part_no=part_no))


@bp.post("/parts/<part_no>/delete")
def delete_part(part_no: str):
    svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))
    try:
        svc.delete(part_no)
        flash(f"已删除零件：{part_no}", "success")
    except AppError as e:
        flash(e.message, "error")
    return redirect(url_for("process.list_parts"))


@bp.post("/parts/bulk/delete")
def bulk_delete_parts():
    part_nos = request.form.getlist("part_nos")
    if not part_nos:
        flash("请至少选择 1 个零件。", "error")
        return redirect(url_for("process.list_parts"))

    svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))
    ok = 0
    failed: List[str] = []
    failed_details: List[str] = []
    for pn in part_nos:
        try:
            svc.delete(pn)
            ok += 1
        except AppError as e:
            failed.append(str(pn))
            failed_details.append(f"{pn}: {e.message}")
            continue
        except Exception:
            current_app.logger.exception("批量删除零件失败（part_no=%s）", pn)
            failed.append(str(pn))
            failed_details.append(f"{pn}: 内部错误，请查看日志")
            continue

    flash(f"批量删除完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        sample = "；".join(failed_details[:10])
        flash(f"删除失败（最多展示 10 个）：{sample}", "warning")
    return redirect(url_for("process.list_parts"))


@bp.post("/parts/<part_no>/reparse")
def reparse_part(part_no: str):
    route_raw = request.form.get("route_raw")
    strict_mode = _strict_mode_enabled(request.form.get("strict_mode"))
    svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))

    start = time.time()
    try:
        result = svc.reparse_and_save(part_no=part_no, route_raw=route_raw, strict_mode=strict_mode)
    except AppError as e:
        flash(e.message, "error")
        return redirect(url_for("process.part_detail", part_no=part_no))
    ms = int((time.time() - start) * 1000)

    warn_text = f"，警告 {len(result.warnings)} 条" if result.warnings else ""
    flash(
        f"工艺路线解析完成：共 {result.stats.get('total', 0)} 道工序（内部 {result.stats.get(SourceType.INTERNAL.value, 0)}，外部 {result.stats.get(SourceType.EXTERNAL.value, 0)}）{warn_text}。耗时 {ms} ms。",
        "success",
    )
    return redirect(url_for("process.part_detail", part_no=part_no))


@bp.post("/parts/<part_no>/ops/<int:seq>/hours")
def update_internal_hours(part_no: str, seq: int):
    setup_hours = request.form.get("setup_hours")
    unit_hours = request.form.get("unit_hours")
    svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.update_internal_hours(part_no=part_no, seq=seq, setup_hours=setup_hours, unit_hours=unit_hours)
    flash("工序工时已保存。", "success")
    return redirect(url_for("process.part_detail", part_no=part_no))


@bp.post("/parts/<part_no>/groups/<group_id>/mode")
def set_group_mode(part_no: str, group_id: str):
    merge_mode = request.form.get("merge_mode") or MergeMode.SEPARATE.value
    total_days = request.form.get("total_days")
    strict_mode = _strict_mode_enabled(request.form.get("strict_mode"))

    per_op_days: Dict[int, Any] = {}
    for k, v in request.form.items():
        if not k.startswith("ext_days_"):
            continue
        try:
            seq = int(k.replace("ext_days_", ""))
        except Exception:
            continue
        per_op_days[seq] = v

    svc = ExternalGroupService(g.db, logger=current_app.logger, op_logger=getattr(g, "op_logger", None))
    try:
        svc.set_merge_mode(
            group_id=group_id,
            merge_mode=merge_mode,
            total_days=total_days,
            per_op_days=per_op_days,
            strict_mode=strict_mode,
        )
        flash(f"外部工序组周期模式已更新：{_merge_mode_zh(merge_mode)}。", "success")
    except AppError as e:
        flash(e.message, "error")
    return redirect(url_for("process.part_detail", part_no=part_no))


@bp.post("/parts/<part_no>/groups/<group_id>/delete")
def delete_group(part_no: str, group_id: str):
    svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))
    result = svc.delete_external_group(part_no=part_no, group_id=group_id)
    flash(f"已删除外部工序组：{group_id}（{result.get('message')}）", "success")
    return redirect(url_for("process.part_detail", part_no=part_no))

