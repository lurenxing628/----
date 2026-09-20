from __future__ import annotations

from typing import Any

from core.errors import BusinessError, ErrorCode, ValidationError
from core.models import Batch
from core.models.enums import BatchStatus
from data.repositories.schedule_batch_copy_repo import ScheduleBatchCopyRepository

from .template_lineage import TemplateLineageWriter


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

    with svc.tx_manager.transaction():
        # 只读原始 ID（仓储不经 model 转换），避免把未知值、NULL 或 BLOB 转成默认值。
        source_ids = ScheduleBatchCopyRepository(svc.conn, logger=svc.logger).source_operation_ids(src)
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

        # 与批次共用事务，保留原始工序及复制时的来源版本。
        writer = TemplateLineageWriter(svc.conn)
        for source_id in source_ids:
            writer.copy_instance(dst, source_id)

    return svc._get_or_raise(dst)
