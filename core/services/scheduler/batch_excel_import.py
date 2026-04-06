from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from core.models.enums import BatchStatus
from core.services.common.excel_import_executor import execute_preview_rows_transactional
from core.services.common.excel_service import ImportMode

from . import batch_write_rules


def import_batches_from_preview_rows(
    svc,
    *,
    preview_rows: List[Any],
    mode: ImportMode,
    parts_cache: Dict[str, Any],
    auto_generate_ops: bool = False,
    strict_mode: bool = False,
    existing_ids: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    批次 Excel 导入编排入口（事务由 execute_preview_rows_transactional 统一控制）。

    说明：
    - 路由层不再直接调用 *_no_tx，避免事务策略泄漏到控制层；
    - 计数与错误样本通过通用执行器统一生成，降低多路由漂移风险。
    """
    rows = list(preview_rows or [])
    existing_row_ids = set(existing_ids or set()) if existing_ids is not None else {b.batch_id for b in svc.list()}

    def _replace_existing_no_tx() -> None:
        svc.delete_all_no_tx()

    def _row_id_getter(pr: Any) -> str:
        return str(pr.data.get("批次号") or "").strip()

    def _apply_row_no_tx(pr: Any, existed: bool) -> None:
        batch_id = str(pr.data.get("批次号") or "").strip()
        part_no = str(pr.data.get("图号") or "").strip()
        part = parts_cache.get(part_no)
        part_name = getattr(part, "part_name", None) if part is not None else None
        due_date = pr.data.get("交期")
        ready_date = pr.data.get("齐套日期")
        remark = pr.data.get("备注")

        if existed:
            existing_batch = svc.get(batch_id)
            update_kwargs = {
                "current_part_no": getattr(existing_batch, "part_no", None),
                "auto_generate_ops": bool(auto_generate_ops),
                "part_no": part_no,
                "quantity": pr.data.get("数量"),
                "due_date": due_date,
                "priority": pr.data.get("优先级"),
                "ready_status": pr.data.get("齐套"),
                "ready_date": ready_date,
                "remark": remark,
            }
            if part_name is not None:
                update_kwargs["part_name"] = part_name
            svc.update_no_tx(batch_id, batch_write_rules.build_update_payload(svc, **update_kwargs))
        else:
            create_kwargs = {
                "batch_id": batch_id,
                "part_no": part_no,
                "quantity": pr.data.get("数量"),
                "due_date": due_date,
                "priority": pr.data.get("优先级"),
                "ready_status": pr.data.get("齐套"),
                "ready_date": ready_date,
                "status": BatchStatus.PENDING.value,
                "remark": remark,
            }
            if part_name is not None:
                create_kwargs["part_name"] = part_name
            svc.create_no_tx(batch_write_rules.build_create_payload(svc, **create_kwargs))

        if auto_generate_ops:
            svc.create_batch_from_template_no_tx(
                batch_id=batch_id,
                part_no=part_no,
                quantity=svc._normalize_int(pr.data.get("数量"), field="数量", allow_none=False),
                due_date=svc._normalize_date(due_date),
                priority=pr.data.get("优先级"),
                ready_status=pr.data.get("齐套"),
                ready_date=svc._normalize_date(ready_date),
                remark=(str(remark).strip() if remark is not None and str(remark).strip() else None),
                rebuild_ops=True,
                strict_mode=bool(strict_mode),
            )

    stats = execute_preview_rows_transactional(
        svc.conn,
        mode=mode,
        preview_rows=rows,
        existing_row_ids=existing_row_ids,
        replace_existing_no_tx=_replace_existing_no_tx,
        row_id_getter=_row_id_getter,
        apply_row_no_tx=_apply_row_no_tx,
        max_error_sample=10,
        process_unchanged=False,
    )
    result = stats.to_dict()
    result["total_rows"] = len(rows)
    result["auto_generate_ops"] = bool(auto_generate_ops)
    return result
