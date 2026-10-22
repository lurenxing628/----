from __future__ import annotations

from typing import Any, Optional, cast

from core.errors import BusinessError, ErrorCode, ValidationError
from core.models import Part
from core.models.enums import BatchPriority, BatchStatus, ReadyStatus
from core.services.process.workflow_state import require_template_ready
from core.services.scheduler.template_lineage import TemplateLineageWriter


def ensure_template_ops_in_tx(
    svc,
    part_no: str,
    part: Part,
    *,
    strict_mode: bool = False,
):
    require_template_ready(svc.conn, part_no)
    template_ops = svc.template_repo.templates_for_part(part_no)
    if template_ops:
        return template_ops

    route_raw = (part.route_raw or "").strip()
    if route_raw:
        from core.services.process.part_service import PartService

        try:
            PartService(svc.conn, logger=svc.logger).upsert_and_parse_no_tx(
                part_no=part_no,
                part_name=part.part_name or part_no,
                route_raw=route_raw,
                strict_mode=strict_mode,
            )
        except BusinessError as exc:
            raise BusinessError(
                ErrorCode.ROUTE_PARSE_ERROR,
                "该零件尚未生成工序清单，且系统无法按路线文字生成。请到【工艺管理-零件工艺模板】中检查路线文字，并重新生成工序清单。",
                cause=exc,
            ) from exc
        template_ops = svc.template_repo.templates_for_part(part_no)

    if not template_ops:
        raise BusinessError(
            ErrorCode.ROUTE_PARSE_ERROR,
            "该零件尚未生成工序清单，无法创建批次工序。请先在【工艺管理-零件工艺模板】中维护路线文字，并生成工序清单。",
        )
    return template_ops


def _ensure_batch_exists_for_template_ops(
    svc,
    *,
    batch_id: str,
    part_no: str,
    part_name: Optional[str],
    quantity: int,
    due_date: Optional[str],
    priority: str,
    ready_status: str,
    ready_date: Optional[str],
    remark: Optional[str],
    rebuild_ops: bool,
) -> None:
    if svc.batch_repo.get(batch_id):
        if rebuild_ops:
            svc.batch_op_repo.delete_by_batch(batch_id)
            return
        raise BusinessError(ErrorCode.BATCH_ALREADY_EXISTS, f"批次号“{batch_id}”已存在，不能重复添加。")

    svc.batch_repo.create(
        {
            "batch_id": batch_id,
            "part_no": part_no,
            "part_name": part_name,
            "quantity": quantity,
            "due_date": due_date,
            "priority": priority,
            "ready_status": ready_status,
            "ready_date": ready_date,
            "status": BatchStatus.PENDING.value,
            "remark": remark,
        }
    )


def create_batch_from_template_no_tx(
    svc,
    *,
    batch_id: Any,
    part_no: Any,
    quantity: Any,
    due_date: Any,
    priority: Any,
    ready_status: Any,
    ready_date: Any,
    remark: Any,
    rebuild_ops: bool = False,
    strict_mode: bool = False,
    _prevalidated: bool = False,
    _part: Optional[Part] = None,
) -> str:
    if _prevalidated:
        bid, part_no_text = batch_id, part_no
        part = cast(Part, _part)
    else:
        bid = svc._normalize_text(batch_id)
        if not bid:
            raise ValidationError("“批次号”不能为空", field="批次号")
        part_no_text = svc._normalize_text(part_no)
        if not part_no_text:
            raise ValidationError("“图号”不能为空", field="图号")
        quantity = svc._normalize_int(quantity, field="数量")
        if quantity <= 0:
            raise ValidationError("“数量”必须大于 0", field="数量")
        priority = svc._normalize_text(priority) or BatchPriority.NORMAL.value
        ready_status = svc._normalize_text(ready_status) or ReadyStatus.YES.value
        ready_date = svc._normalize_date(ready_date)
        svc._validate_enum(priority, (BatchPriority.NORMAL.value, BatchPriority.URGENT.value, BatchPriority.CRITICAL.value), "优先级")
        svc._validate_enum(ready_status, (ReadyStatus.YES.value, ReadyStatus.NO.value, ReadyStatus.PARTIAL.value), "齐套")
        part = svc.part_repo.get(part_no_text)
        if not part:
            raise BusinessError(ErrorCode.NOT_FOUND, f"图号“{part_no_text}”不存在，请先在工艺管理中维护零件。")
        due_date = svc._normalize_date(due_date)
        remark = svc._normalize_text(remark)

    lineage = TemplateLineageWriter(svc.conn)
    lineage.require_ready()
    template_ops = ensure_template_ops_in_tx(svc, part_no_text, part, strict_mode=strict_mode)
    prepared = lineage.prepare_templates(template_ops)
    if _prevalidated:
        # Excel 已在当前事务完成批次写入，直接重建其工序。
        svc.batch_op_repo.delete_by_batch(bid)
    else:
        _ensure_batch_exists_for_template_ops(
            svc,
            batch_id=bid,
            part_no=part_no_text,
            part_name=part.part_name,
            quantity=quantity,
            due_date=due_date,
            priority=priority,
            ready_status=ready_status,
            ready_date=ready_date,
            remark=remark,
            rebuild_ops=rebuild_ops,
        )
    for template in prepared:
        lineage.copy_prepared_template(bid, template)
    return bid
