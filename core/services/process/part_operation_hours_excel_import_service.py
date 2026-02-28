from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import AppError
from core.infrastructure.transaction import TransactionManager
from core.services.common.excel_service import ImportPreviewRow, RowStatus

from .part_service import PartService


@dataclass
class _ImportStats:
    new_count: int = 0
    update_count: int = 0
    skip_count: int = 0
    error_count: int = 0
    errors_sample: List[Dict[str, Any]] = field(default_factory=list)

    def add_error(self, row_num: int, message: str) -> None:
        self.error_count += 1
        if message and len(self.errors_sample) < 10:
            self.errors_sample.append({"row": row_num, "message": message})

    def to_dict(self, total_rows: int) -> Dict[str, Any]:
        return {
            "total_rows": total_rows,
            "new_count": self.new_count,
            "update_count": self.update_count,
            "skip_count": self.skip_count,
            "error_count": self.error_count,
            "errors_sample": list(self.errors_sample),
        }


class PartOperationHoursExcelImportService:
    """零件工序工时 Excel 导入落库服务（基于 preview_rows）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self.part_svc = PartService(conn, logger=logger, op_logger=op_logger)

    def apply_preview_rows(self, preview_rows: List[ImportPreviewRow]) -> Dict[str, Any]:
        stats = _ImportStats()

        # 导入级事务壳：
        # - 业务错误（AppError）按行统计并继续
        # - 非预期异常直接抛出，由 TransactionManager 触发整体回滚，避免半提交
        with self.tx_manager.transaction():
            for pr in preview_rows or []:
                self._apply_one(pr, stats)

        return stats.to_dict(total_rows=len(preview_rows))

    def _apply_one(self, pr: ImportPreviewRow, stats: _ImportStats) -> None:
        if pr.status in (RowStatus.ERROR, RowStatus.SKIP, RowStatus.UNCHANGED):
            self._apply_non_write_row(pr, stats)
            return

        parsed = self._parse_write_row(pr)
        if parsed is None:
            stats.add_error(pr.row_num, "缺少图号/工序，无法写入。")
            return
        part_no, seq, sh, uh = parsed

        try:
            self.part_svc.update_internal_hours(part_no=part_no, seq=seq, setup_hours=sh, unit_hours=uh)
        except AppError as e:
            stats.add_error(pr.row_num, e.message)
            return

        if pr.status == RowStatus.NEW:
            stats.new_count += 1
        else:
            stats.update_count += 1

    @staticmethod
    def _apply_non_write_row(pr: ImportPreviewRow, stats: _ImportStats) -> None:
        if pr.status == RowStatus.ERROR:
            stats.add_error(pr.row_num, pr.message)
            return
        if pr.status == RowStatus.SKIP:
            stats.skip_count += 1
            return
        if pr.status == RowStatus.UNCHANGED:
            stats.skip_count += 1
            return
        return

    @staticmethod
    def _parse_write_row(pr: ImportPreviewRow) -> Optional[Tuple[str, int, float, float]]:
        data = pr.data or {}
        part_no = str(data.get("图号") or "").strip()
        seq = data.get("工序")
        if not part_no or not isinstance(seq, int):
            return None

        # preview 阶段已完成校验与类型标准化，这里直接使用结果，避免跨包依赖与重复解析。
        sh = float(data.get("换型时间(h)") or 0.0)
        uh = float(data.get("单件工时(h)") or 0.0)
        return part_no, int(seq), sh, uh

