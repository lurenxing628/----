from __future__ import annotations

import math
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

        parsed, err = self._parse_write_row(pr)
        if err:
            stats.add_error(pr.row_num, err)
            return
        assert parsed is not None
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
    def _coerce_int(value: Any) -> Optional[int]:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int):
            return int(value)
        if isinstance(value, float):
            return int(value) if value.is_integer() else None
        s = str(value).strip()
        if not s:
            return None
        if "e" in s.lower():
            return None
        try:
            f = float(s)
        except Exception:
            return None
        if not math.isfinite(f):
            return None
        return int(f) if float(f).is_integer() else None

    @staticmethod
    def _coerce_finite_float(value: Any) -> Optional[float]:
        if value is None:
            return 0.0
        if isinstance(value, bool):
            return None
        if isinstance(value, str):
            s = value.strip()
            if s == "":
                return 0.0
            try:
                f = float(s)
            except Exception:
                return None
        else:
            try:
                f = float(value)
            except Exception:
                return None
        if not math.isfinite(f):
            return None
        return float(f)

    @classmethod
    def _parse_write_row(cls, pr: ImportPreviewRow) -> Tuple[Optional[Tuple[str, int, float, float]], Optional[str]]:
        data = pr.data or {}
        part_no = str(data.get("图号") or "").strip()
        seq_int = cls._coerce_int(data.get("工序"))
        if not part_no or seq_int is None:
            return None, "缺少图号/工序，无法写入。"

        # 正常链路下 preview 已完成校验与类型标准化；此处仅做“输入漂移防御”，避免整批回滚。
        sh = cls._coerce_finite_float(data.get("换型时间(h)"))
        if sh is None:
            return None, "“换型时间(h)”必须是有限数字"
        uh = cls._coerce_finite_float(data.get("单件工时(h)"))
        if uh is None:
            return None, "“单件工时(h)”必须是有限数字"
        if float(sh) < 0 or float(uh) < 0:
            return None, "“换型时间(h)”和“单件工时(h)”不能为负数"
        return (part_no, int(seq_int), float(sh), float(uh)), None

