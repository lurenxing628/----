from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import ExternalGroup, PartOperation
from core.models.enums import MERGE_MODE_VALUES, MergeMode
from core.services.common.normalize import append_unique_text_messages, normalize_text
from core.services.common.safe_logging import safe_warning
from data.repositories import ExternalGroupRepository, PartOperationRepository


class ExternalGroupService:
    """外协工序组服务（ExternalGroups）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self.group_repo = ExternalGroupRepository(conn, logger=logger)
        self.op_repo = PartOperationRepository(conn, logger=logger)

    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

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
            raise BusinessError(ErrorCode.EXTERNAL_GROUP_ERROR, f"外协工序组“{group_id}”不存在")
        return g

    def list_by_part(self, part_no: str) -> List[ExternalGroup]:
        return self.group_repo.list_by_part(part_no)

    def _list_external_ops_in_group(self, part_no: str, group_id: str) -> List[PartOperation]:
        ops = self.op_repo.list_by_part(part_no, include_deleted=False)
        out: List[PartOperation] = []
        for op in ops:
            if op.ext_group_id != group_id:
                continue
            if not op.is_external():
                continue
            out.append(op)
        return out

    def _update_group_common_fields(
        self,
        group_id: str,
        *,
        merge_mode: str,
        total_days: Optional[float],
        supplier_id: Any,
        remark: Any,
        normalized_supplier_id: Optional[str],
        normalized_remark: Optional[str],
    ) -> None:
        updates: Dict[str, Any] = {"merge_mode": merge_mode, "total_days": total_days}
        if supplier_id is not None:
            updates["supplier_id"] = normalized_supplier_id
        if remark is not None:
            updates["remark"] = normalized_remark
        self.group_repo.update(group_id, updates)

    def _apply_merged_mode(
        self,
        group_id: str,
        *,
        total_days: Any,
        part_no: str,
        seqs: List[int],
        supplier_id: Any,
        remark: Any,
        normalized_supplier_id: Optional[str],
        normalized_remark: Optional[str],
    ) -> None:
        td = self._normalize_float(total_days)
        if td is None or td <= 0:
            raise ValidationError("合并周期（天）必须大于 0", field="total_days")

        self._update_group_common_fields(
            group_id,
            merge_mode=MergeMode.MERGED.value,
            total_days=float(td),
            supplier_id=supplier_id,
            remark=remark,
            normalized_supplier_id=normalized_supplier_id,
            normalized_remark=normalized_remark,
        )
        for seq in seqs:
            self.op_repo.update(part_no, int(seq), {"ext_days": None})

    def _apply_separate_mode(
        self,
        group_id: str,
        *,
        part_no: str,
        ops: List[PartOperation],
        per_op_days: Optional[Dict[int, Any]],
        supplier_id: Any,
        remark: Any,
        normalized_supplier_id: Optional[str],
        normalized_remark: Optional[str],
        user_warnings: Optional[List[str]] = None,
        strict_mode: bool = False,
    ) -> None:
        self._update_group_common_fields(
            group_id,
            merge_mode=MergeMode.SEPARATE.value,
            total_days=None,
            supplier_id=supplier_id,
            remark=remark,
            normalized_supplier_id=normalized_supplier_id,
            normalized_remark=normalized_remark,
        )

        per_op_days = per_op_days or {}
        for op in ops:
            d = per_op_days.get(int(op.seq))
            dv = self._normalize_float(d)
            seq = int(op.seq)
            if dv is None or dv <= 0:
                op_type_name = normalize_text(getattr(op, "op_type_name", None)) or f"seq={seq}"
                if strict_mode:
                    raise ValidationError(
                        f"外协工序 {seq}（{op_type_name}）的周期必须大于 0。请先填正确后再保存。",
                        field=f"ext_days_{seq}",
                    )
                log_warning_text = (
                    f"外协工序 {seq}（{op_type_name}）周期无效，"
                    f"原始周期={d!r}，兼容读取时先按 1.0 天处理"
                )
                user_warning_text = f"外协工序 {seq}（{op_type_name}）周期输入无效，本次会先按 1 天记录，请尽快补成真实周期。"
                safe_warning(self.logger, log_warning_text)
                append_unique_text_messages(user_warnings, user_warning_text)
                dv = 1.0
            self.op_repo.update(part_no, seq, {"ext_days": float(dv)})

    def set_merge_mode(
        self,
        group_id: str,
        merge_mode: str,
        total_days: Any = None,
        per_op_days: Optional[Dict[int, Any]] = None,
        supplier_id: Any = None,
        remark: Any = None,
        user_warnings: Optional[List[str]] = None,
        strict_mode: bool = False,
    ) -> ExternalGroup:
        """
        设置外部组周期模式：
        - separate：每道外部工序在 PartOperations.ext_days 维护；ExternalGroups.total_days=NULL
        - merged：ExternalGroups.total_days 维护；组内 PartOperations.ext_days=NULL
        """
        gid = self._normalize_text(group_id)
        if not gid:
            raise ValidationError("缺少外协工序组编号", field="group_id")

        mode = (self._normalize_text(merge_mode) or MergeMode.SEPARATE.value).strip().lower()
        if mode not in MERGE_MODE_VALUES:
            raise ValidationError("周期模式不正确，请选择：分开算 / 合在一起算。", field="周期模式")

        g = self._get_group_or_raise(gid)

        ops = self._list_external_ops_in_group(g.part_no, gid)
        seqs = [int(op.seq) for op in ops]

        sup_id = self._normalize_text(supplier_id)
        rmk = self._normalize_text(remark)

        with self.tx_manager.transaction():
            if mode == MergeMode.MERGED.value:
                self._apply_merged_mode(
                    gid,
                    total_days=total_days,
                    part_no=g.part_no,
                    seqs=seqs,
                    supplier_id=supplier_id,
                    remark=remark,
                    normalized_supplier_id=sup_id,
                    normalized_remark=rmk,
                )
            else:
                self._apply_separate_mode(
                    gid,
                    part_no=g.part_no,
                    ops=ops,
                    per_op_days=per_op_days,
                    supplier_id=supplier_id,
                    remark=remark,
                    normalized_supplier_id=sup_id,
                    normalized_remark=rmk,
                    user_warnings=user_warnings,
                    strict_mode=bool(strict_mode),
                )

        return self._get_group_or_raise(gid)
