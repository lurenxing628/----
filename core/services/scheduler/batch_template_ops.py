from __future__ import annotations

from typing import Any, Dict, Optional

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.models.enums import BatchOperationStatus, BatchPriority, BatchStatus, ReadyStatus, SourceType


def _normalize_source(value: Any) -> str:
    src = ("" if value is None else str(value)).strip().lower()
    if not src:
        return SourceType.INTERNAL.value
    if src in (SourceType.INTERNAL.value, SourceType.EXTERNAL.value):
        return src
    return SourceType.INTERNAL.value


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
    # 允许 rebuild：先删后建（但只影响同一个 batch_id）
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
            "quantity": int(quantity),
            "due_date": due_date,
            "priority": priority,
            "ready_status": ready_status,
            "ready_date": svc._normalize_date(ready_date),
            "status": BatchStatus.PENDING.value,
            "remark": remark,
        }
    )


def _build_batch_op_payload(svc, *, batch_id: str, seq: int, tmpl: Any, source: str) -> Dict[str, Any]:
    supplier_id = tmpl.supplier_id if source == SourceType.EXTERNAL.value else None
    return {
        "op_code": f"{batch_id}_{int(seq):02d}",
        "batch_id": batch_id,
        "piece_id": None,
        "seq": int(seq),
        "op_type_id": tmpl.op_type_id,
        "op_type_name": tmpl.op_type_name,
        "source": source,
        "machine_id": None,
        "operator_id": None,
        "supplier_id": supplier_id,
        "setup_hours": float(tmpl.setup_hours or 0.0),
        "unit_hours": float(tmpl.unit_hours or 0.0),
        "ext_days": svc._safe_float(tmpl.ext_days),
        "status": BatchOperationStatus.PENDING.value,
    }


def create_batch_from_template_no_tx(
    svc,
    *,
    batch_id: str,
    part_no: str,
    quantity: int,
    due_date: Optional[str],
    priority: str,
    ready_status: str,
    ready_date: Optional[str],
    remark: Optional[str],
    rebuild_ops: bool = False,
    strict_mode: bool = False,
) -> None:
    """
    从零件模板生成/重建批次工序（不控制事务）。

    说明：
    - 供 Excel 批量导入在“外部已开启事务”时使用，避免嵌套 commit 导致无法整体回滚。
    """
    bid = svc._normalize_text(batch_id)
    pn = svc._normalize_text(part_no)
    if not bid:
        raise ValidationError("“批次号”不能为空", field="批次号")
    if not pn:
        raise ValidationError("“图号”不能为空", field="图号")
    if quantity is None or int(quantity) <= 0:
        raise ValidationError("“数量”必须大于 0", field="数量")

    pr = svc._normalize_text(priority) or BatchPriority.NORMAL.value
    rs = svc._normalize_text(ready_status) or ReadyStatus.YES.value
    svc._validate_enum(pr, (BatchPriority.NORMAL.value, BatchPriority.URGENT.value, BatchPriority.CRITICAL.value), "优先级")
    svc._validate_enum(rs, (ReadyStatus.YES.value, ReadyStatus.NO.value, ReadyStatus.PARTIAL.value), "齐套")

    part = svc.part_repo.get(pn)
    if not part:
        raise BusinessError(ErrorCode.NOT_FOUND, f"图号“{pn}”不存在，请先在工艺管理中维护零件。")

    template_ops = svc._load_template_ops_with_fallback(pn, part, no_tx=True, strict_mode=bool(strict_mode))

    _ensure_batch_exists_for_template_ops(
        svc,
        batch_id=bid,
        part_no=pn,
        part_name=getattr(part, "part_name", None),
        quantity=int(quantity),
        due_date=due_date,
        priority=pr,
        ready_status=rs,
        ready_date=ready_date,
        remark=remark,
        rebuild_ops=bool(rebuild_ops),
    )

    for tmpl in template_ops:
        seq = int(tmpl.seq)
        source = _normalize_source(getattr(tmpl, "source", None))
        svc.batch_op_repo.create(_build_batch_op_payload(svc, batch_id=bid, seq=seq, tmpl=tmpl, source=source))

