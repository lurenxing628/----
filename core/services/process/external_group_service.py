from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.enums import MergeMode
from data.repositories import ExternalGroupRepository, PartOperationRepository


class ExternalGroupService:
    """外部工序组服务（ExternalGroups）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self.group_repo = ExternalGroupRepository(conn, logger=logger)
        self.op_repo = PartOperationRepository(conn, logger=logger)

    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            v = value.strip()
            return v if v != "" else None
        v = str(value).strip()
        return v if v != "" else None

    @staticmethod
    def _normalize_float(value: Any) -> Optional[float]:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        try:
            return float(value)
        except Exception:
            return None

    def _get_group_or_raise(self, group_id: str):
        g = self.group_repo.get(group_id)
        if not g:
            raise BusinessError(ErrorCode.EXTERNAL_GROUP_ERROR, f"外部工序组“{group_id}”不存在")
        return g

    def list_by_part(self, part_no: str):
        return self.group_repo.list_by_part(part_no)

    def set_merge_mode(
        self,
        group_id: str,
        merge_mode: str,
        total_days: Any = None,
        per_op_days: Optional[Dict[int, Any]] = None,
        supplier_id: Any = None,
        remark: Any = None,
    ):
        """
        设置外部组周期模式：
        - separate：每道外部工序在 PartOperations.ext_days 维护；ExternalGroups.total_days=NULL
        - merged：ExternalGroups.total_days 维护；组内 PartOperations.ext_days=NULL
        """
        gid = self._normalize_text(group_id)
        if not gid:
            raise ValidationError("缺少外部工序组ID", field="group_id")

        mode = (self._normalize_text(merge_mode) or MergeMode.SEPARATE.value).strip().lower()
        if mode not in (MergeMode.SEPARATE.value, MergeMode.MERGED.value):
            raise ValidationError("周期模式不合法（允许：separate / merged）", field="merge_mode")

        g = self._get_group_or_raise(gid)

        # 取该组内外部工序
        ops = [
            op
            for op in self.op_repo.list_by_part(g.part_no, include_deleted=False)
            if op.ext_group_id == gid and (op.source or "").strip().lower() == "external"
        ]
        seqs = [int(op.seq) for op in ops]

        sup_id = self._normalize_text(supplier_id)
        rmk = self._normalize_text(remark)

        with self.tx_manager.transaction():
            if mode == MergeMode.MERGED.value:
                td = self._normalize_float(total_days)
                if td is None or td <= 0:
                    raise ValidationError("合并周期（天）必须大于 0", field="total_days")

                # 组表：写 total_days；工序表：清空 ext_days
                self.group_repo.update(
                    gid,
                    {
                        "merge_mode": mode,
                        "total_days": float(td),
                        # 允许可选字段覆盖
                        **({"supplier_id": sup_id} if supplier_id is not None else {}),
                        **({"remark": rmk} if remark is not None else {}),
                    },
                )
                for seq in seqs:
                    self.op_repo.update(g.part_no, seq, {"ext_days": None})

            else:
                # separate：组表 total_days 清空；工序表写每道 ext_days
                self.group_repo.update(
                    gid,
                    {
                        "merge_mode": mode,
                        "total_days": None,
                        **({"supplier_id": sup_id} if supplier_id is not None else {}),
                        **({"remark": rmk} if remark is not None else {}),
                    },
                )

                per_op_days = per_op_days or {}
                for op in ops:
                    d = per_op_days.get(int(op.seq))
                    dv = self._normalize_float(d)
                    if dv is None or dv <= 0:
                        # 没填时给默认 1 天（避免写入 NULL 导致后续排产无法计算）
                        dv = 1.0
                    self.op_repo.update(g.part_no, int(op.seq), {"ext_days": float(dv)})

        return self._get_group_or_raise(gid)

