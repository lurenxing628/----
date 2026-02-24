from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from core.infrastructure.transaction import TransactionManager

from .excel_service import ImportMode, RowStatus


@dataclass
class ImportExecutionStats:
    new_count: int = 0
    update_count: int = 0
    skip_count: int = 0
    error_count: int = 0
    errors_sample: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "new_count": int(self.new_count),
            "update_count": int(self.update_count),
            "skip_count": int(self.skip_count),
            "error_count": int(self.error_count),
            "errors_sample": list(self.errors_sample),
        }


def execute_preview_rows_transactional(
    conn,
    *,
    mode: ImportMode,
    preview_rows: Iterable[Any],
    existing_row_ids: Set[str],
    replace_existing_no_tx: Optional[Callable[[], None]],
    row_id_getter: Callable[[Any], str],
    apply_row_no_tx: Callable[[Any, bool], None],
    max_error_sample: int = 10,
) -> ImportExecutionStats:
    """
    通用 Excel 导入执行器：
    - 统一事务包裹
    - 统一 NEW/UPDATE/SKIP/ERROR 计数与错误样本采集
    - 路由不再重复维护导入循环
    """
    stats = ImportExecutionStats()
    tx = TransactionManager(conn)

    with tx.transaction():
        if mode == ImportMode.REPLACE and replace_existing_no_tx is not None:
            replace_existing_no_tx()
            existing_row_ids.clear()

        for pr in preview_rows:
            if pr.status == RowStatus.ERROR:
                stats.error_count += 1
                if pr.message and len(stats.errors_sample) < int(max_error_sample):
                    stats.errors_sample.append({"row": pr.row_num, "message": pr.message})
                continue
            if pr.status == RowStatus.SKIP:
                stats.skip_count += 1
                continue
            if pr.status == RowStatus.UNCHANGED:
                continue

            row_id = str(row_id_getter(pr) or "").strip()
            if mode == ImportMode.APPEND and row_id in existing_row_ids:
                stats.skip_count += 1
                continue

            existed = row_id in existing_row_ids
            apply_row_no_tx(pr, existed)

            if existed:
                stats.update_count += 1
            else:
                stats.new_count += 1
                existing_row_ids.add(row_id)

    return stats

