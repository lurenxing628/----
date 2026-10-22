from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from core.errors import AppError
from core.infrastructure.transaction import TransactionManager

from .excel_service import ImportMode, ImportPreviewRow, RowStatus


@dataclass
class ImportExecutionStats:
    new_count: int = 0
    update_count: int = 0
    skip_count: int = 0
    error_count: int = 0
    errors_sample: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "new_count": self.new_count,
            "update_count": self.update_count,
            "skip_count": self.skip_count,
            "error_count": self.error_count,
            "errors_sample": self.errors_sample,
        }


def _append_error_sample(
    stats: ImportExecutionStats,
    *,
    row: ImportPreviewRow,
    message: Optional[str],
    max_error_sample: int,
) -> None:
    if not message:
        return
    if len(stats.errors_sample) >= max_error_sample:
        return
    stats.errors_sample.append({"row": row.row_num, "message": message})


def _should_skip_before_row_id(
    stats: ImportExecutionStats,
    *,
    pr: ImportPreviewRow,
    mode: ImportMode,
    max_error_sample: int,
) -> bool:
    if pr.status == RowStatus.ERROR:
        stats.error_count += 1
        _append_error_sample(stats, row=pr, message=pr.message, max_error_sample=max_error_sample)
        return True
    if pr.status == RowStatus.SKIP:
        stats.skip_count += 1
        return True
    # REPLACE 已清空历史数据，UNCHANGED 行也必须重写回库，不能直接跳过。
    if pr.status == RowStatus.UNCHANGED and mode != ImportMode.REPLACE:
        stats.skip_count += 1
        return True
    return False


def _should_skip_after_row_id(
    stats: ImportExecutionStats,
    *,
    mode: ImportMode,
    row_id: str,
    existing_row_ids: Set[str],
) -> bool:
    if mode == ImportMode.APPEND and row_id in existing_row_ids:
        stats.skip_count += 1
        return True
    return False


def _apply_one_row(
    stats: ImportExecutionStats,
    *,
    pr: ImportPreviewRow,
    existed: bool,
    row_id: str,
    existing_row_ids: Set[str],
    apply_row_no_tx: Callable[[Any, bool], None],
    continue_on_app_error: bool,
    max_error_sample: int,
) -> None:
    try:
        apply_row_no_tx(pr, existed)
    except AppError as e:
        if not continue_on_app_error:
            raise
        stats.error_count += 1
        _append_error_sample(stats, row=pr, message=e.message, max_error_sample=max_error_sample)
        return

    if existed:
        stats.update_count += 1
        return

    stats.new_count += 1
    existing_row_ids.add(row_id)


def execute_preview_rows_transactional(
    conn,
    *,
    mode: ImportMode,
    preview_rows: Iterable[ImportPreviewRow],
    existing_row_ids: Set[str],
    replace_existing_no_tx: Optional[Callable[[], None]],
    row_id_getter: Callable[[Any], str],
    apply_row_no_tx: Callable[[Any, bool], None],
    max_error_sample: int = 10,
    continue_on_app_error: bool = False,
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
            if _should_skip_before_row_id(
                stats,
                pr=pr,
                mode=mode,
                max_error_sample=max_error_sample,
            ):
                continue

            row_id = str(row_id_getter(pr) or "").strip()
            if not row_id:
                stats.error_count += 1
                _append_error_sample(stats, row=pr, message="缺少主键，无法写入。", max_error_sample=max_error_sample)
                continue
            if _should_skip_after_row_id(stats, mode=mode, row_id=row_id, existing_row_ids=existing_row_ids):
                continue

            existed = row_id in existing_row_ids
            _apply_one_row(
                stats,
                pr=pr,
                existed=existed,
                row_id=row_id,
                existing_row_ids=existing_row_ids,
                apply_row_no_tx=apply_row_no_tx,
                continue_on_app_error=continue_on_app_error,
                max_error_sample=max_error_sample,
            )

    return stats
