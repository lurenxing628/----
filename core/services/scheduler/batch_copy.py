from __future__ import annotations

from typing import Any, Dict

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.models import Batch
from core.models.enums import BatchOperationStatus, BatchStatus


def copy_batch(svc, source_batch_id: Any, new_batch_id: Any) -> Batch:
    """
    复制批次（含批次工序），用于批量复制/快速建相似批次。

    规则：
    - 新批次 status 固定为 pending
    - 新批次工序 status 固定为 pending（不复制 scheduled 等状态）
    - 其它字段尽量保持一致（图号/数量/交期/优先级/齐套/备注/工序补充信息等）
    """
    src = svc._normalize_text(source_batch_id)
    dst = svc._normalize_text(new_batch_id)
    if not src:
        raise ValidationError("“源批次号”不能为空", field="源批次号")
    if not dst:
        raise ValidationError("“新批次号”不能为空", field="新批次号")
    if src == dst:
        raise ValidationError("新批次号不能与源批次号相同", field="新批次号")

    b = svc._get_or_raise(src)
    if svc.batch_repo.get(dst):
        raise BusinessError(ErrorCode.BATCH_ALREADY_EXISTS, f"批次号“{dst}”已存在，不能复制。")

    ops = svc.batch_op_repo.list_by_batch(src)
    with svc.tx_manager.transaction():
        # 创建新批次
        svc.batch_repo.create(
            {
                "batch_id": dst,
                "part_no": b.part_no,
                "part_name": b.part_name,
                "quantity": int(b.quantity),
                "due_date": b.due_date,
                "priority": b.priority,
                "ready_status": b.ready_status,
                "ready_date": b.ready_date,
                "status": BatchStatus.PENDING.value,
                "remark": b.remark,
            }
        )

        # 复制工序（重新生成 op_code，保持 seq/piece_id，其它字段尽量拷贝）
        for op in ops:
            seq = int(op.seq or 0)
            piece = op.piece_id
            if piece:
                op_code = f"{dst}_{seq:02d}_{piece}"
            else:
                op_code = f"{dst}_{seq:02d}"
            svc.batch_op_repo.create(
                {
                    "op_code": op_code,
                    "batch_id": dst,
                    "piece_id": piece,
                    "seq": seq,
                    "op_type_id": op.op_type_id,
                    "op_type_name": op.op_type_name,
                    "source": op.source,
                    "machine_id": op.machine_id,
                    "operator_id": op.operator_id,
                    "supplier_id": op.supplier_id,
                    "setup_hours": float(op.setup_hours or 0.0),
                    "unit_hours": float(op.unit_hours or 0.0),
                    "ext_days": svc._safe_float(op.ext_days),
                    "status": BatchOperationStatus.PENDING.value,
                }
            )

    return svc._get_or_raise(dst)

