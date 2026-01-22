from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import Batch, BatchOperation
from core.models.enums import BatchPriority, BatchStatus, ReadyStatus, SourceType
from data.repositories import BatchOperationRepository, BatchRepository, PartOperationRepository, PartRepository


class BatchService:
    """批次服务（Batches + BatchOperations）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)

        self.batch_repo = BatchRepository(conn, logger=logger)
        self.batch_op_repo = BatchOperationRepository(conn, logger=logger)
        self.part_repo = PartRepository(conn, logger=logger)
        self.part_op_repo = PartOperationRepository(conn, logger=logger)

    # -------------------------
    # 工具方法 / 校验
    # -------------------------
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
    def _normalize_int(value: Any, field: str, allow_none: bool = False) -> Optional[int]:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None if allow_none else 0
        try:
            return int(value)
        except Exception:
            raise ValidationError(f"“{field}”必须是整数", field=field)

    @staticmethod
    def _normalize_date(value: Any) -> Optional[str]:
        """
        交期（due_date）存储为 SQLite DATE，V1 以字符串 `YYYY-MM-DD` 为主。
        - 允许为空
        - 允许传入 datetime/date（会转为 ISO 格式）
        """
        if value is None:
            return None
        if isinstance(value, str):
            v = value.strip()
            return v if v != "" else None
        # datetime/date 兜底
        try:
            return value.isoformat()
        except Exception:
            return str(value)

    @staticmethod
    def _validate_enum(value: Optional[str], allowed: Tuple[str, ...], field: str) -> Optional[str]:
        if value is None:
            return None
        if value not in allowed:
            allow_text = " / ".join(list(allowed))
            raise ValidationError(f"“{field}”不合法（允许：{allow_text}）", field=field)
        return value

    def _get_or_raise(self, batch_id: str) -> Batch:
        b = self.batch_repo.get(batch_id)
        if not b:
            raise BusinessError(ErrorCode.BATCH_NOT_FOUND, f"批次“{batch_id}”不存在")
        return b

    # -------------------------
    # Batches CRUD
    # -------------------------
    def list(self, status: Optional[str] = None, priority: Optional[str] = None, part_no: Optional[str] = None) -> List[Batch]:
        if status:
            self._validate_enum(
                status,
                (
                    BatchStatus.PENDING.value,
                    BatchStatus.SCHEDULED.value,
                    BatchStatus.PROCESSING.value,
                    BatchStatus.COMPLETED.value,
                    BatchStatus.CANCELLED.value,
                ),
                "状态",
            )
        if priority:
            self._validate_enum(
                priority,
                (BatchPriority.NORMAL.value, BatchPriority.URGENT.value, BatchPriority.CRITICAL.value),
                "优先级",
            )
        return self.batch_repo.list(status=status, priority=priority, part_no=part_no)

    def get(self, batch_id: Any) -> Batch:
        bid = self._normalize_text(batch_id)
        if not bid:
            raise ValidationError("“批次号”不能为空", field="批次号")
        return self._get_or_raise(bid)

    def create(
        self,
        batch_id: Any,
        part_no: Any,
        quantity: Any,
        due_date: Any = None,
        priority: Any = BatchPriority.NORMAL.value,
        ready_status: Any = ReadyStatus.NO.value,
        status: Any = BatchStatus.PENDING.value,
        remark: Any = None,
        part_name: Any = None,
    ) -> Batch:
        bid = self._normalize_text(batch_id)
        pn = self._normalize_text(part_no)
        qty = self._normalize_int(quantity, field="数量", allow_none=False)
        dd = self._normalize_date(due_date)
        pr = self._normalize_text(priority) or BatchPriority.NORMAL.value
        rs = self._normalize_text(ready_status) or ReadyStatus.NO.value
        st = self._normalize_text(status) or BatchStatus.PENDING.value
        rmk = self._normalize_text(remark)

        if not bid:
            raise ValidationError("“批次号”不能为空", field="批次号")
        if not pn:
            raise ValidationError("“图号”不能为空", field="图号")
        if qty is None or qty <= 0:
            raise ValidationError("“数量”必须大于 0", field="数量")

        self._validate_enum(pr, (BatchPriority.NORMAL.value, BatchPriority.URGENT.value, BatchPriority.CRITICAL.value), "优先级")
        self._validate_enum(rs, (ReadyStatus.YES.value, ReadyStatus.NO.value, ReadyStatus.PARTIAL.value), "齐套")
        self._validate_enum(
            st,
            (
                BatchStatus.PENDING.value,
                BatchStatus.SCHEDULED.value,
                BatchStatus.PROCESSING.value,
                BatchStatus.COMPLETED.value,
                BatchStatus.CANCELLED.value,
            ),
            "状态",
        )

        if self.batch_repo.get(bid):
            raise BusinessError(ErrorCode.BATCH_ALREADY_EXISTS, f"批次号“{bid}”已存在，不能重复添加。")

        part = self.part_repo.get(pn)
        if not part:
            raise BusinessError(ErrorCode.NOT_FOUND, f"图号“{pn}”不存在，请先在工艺管理中维护零件。")

        # 若未显式传 part_name，则默认使用零件名称
        p_name = self._normalize_text(part_name) or part.part_name

        with self.tx_manager.transaction():
            self.create_no_tx(
                {
                    "batch_id": bid,
                    "part_no": pn,
                    "part_name": p_name,
                    "quantity": int(qty),
                    "due_date": dd,
                    "priority": pr,
                    "ready_status": rs,
                    "status": st,
                    "remark": rmk,
                }
            )

        return self._get_or_raise(bid)

    def create_no_tx(self, payload: Dict[str, Any]) -> Batch:
        """
        创建批次（不控制事务）。

        说明：
        - 供 Excel 批量导入在“外部已开启事务”时使用，避免嵌套 commit 导致无法整体回滚。
        """
        b = payload if isinstance(payload, Batch) else Batch.from_row(payload)
        self.batch_repo.create(b.to_dict())
        return b

    def update(
        self,
        batch_id: Any,
        part_no: Any = None,
        quantity: Any = None,
        due_date: Any = None,
        priority: Any = None,
        ready_status: Any = None,
        status: Any = None,
        remark: Any = None,
        part_name: Any = None,
    ) -> Batch:
        bid = self._normalize_text(batch_id)
        if not bid:
            raise ValidationError("“批次号”不能为空", field="批次号")
        self._get_or_raise(bid)

        updates: Dict[str, Any] = {}

        if part_no is not None:
            pn = self._normalize_text(part_no)
            if not pn:
                raise ValidationError("“图号”不能为空", field="图号")
            part = self.part_repo.get(pn)
            if not part:
                raise BusinessError(ErrorCode.NOT_FOUND, f"图号“{pn}”不存在，请先在工艺管理中维护零件。")
            updates["part_no"] = pn
            # 若未显式传 part_name，则切换图号时默认跟随零件名称
            if part_name is None:
                updates["part_name"] = part.part_name

        if part_name is not None:
            updates["part_name"] = self._normalize_text(part_name)

        if quantity is not None:
            qty = self._normalize_int(quantity, field="数量", allow_none=True)
            if qty is None or qty <= 0:
                raise ValidationError("“数量”必须大于 0", field="数量")
            updates["quantity"] = int(qty)

        if due_date is not None:
            updates["due_date"] = self._normalize_date(due_date)

        if priority is not None:
            pr = self._normalize_text(priority)
            self._validate_enum(pr, (BatchPriority.NORMAL.value, BatchPriority.URGENT.value, BatchPriority.CRITICAL.value), "优先级")
            updates["priority"] = pr

        if ready_status is not None:
            rs = self._normalize_text(ready_status)
            self._validate_enum(rs, (ReadyStatus.YES.value, ReadyStatus.NO.value, ReadyStatus.PARTIAL.value), "齐套")
            updates["ready_status"] = rs

        if status is not None:
            st = self._normalize_text(status)
            self._validate_enum(
                st,
                (
                    BatchStatus.PENDING.value,
                    BatchStatus.SCHEDULED.value,
                    BatchStatus.PROCESSING.value,
                    BatchStatus.COMPLETED.value,
                    BatchStatus.CANCELLED.value,
                ),
                "状态",
            )
            updates["status"] = st

        if remark is not None:
            updates["remark"] = self._normalize_text(remark)  # 允许显式清空为 NULL

        if updates:
            with self.tx_manager.transaction():
                self.update_no_tx(bid, updates)

        return self._get_or_raise(bid)

    def update_no_tx(self, batch_id: str, updates: Dict[str, Any]) -> None:
        """
        更新批次（不控制事务）。

        说明：
        - 供 Excel 批量导入在“外部已开启事务”时使用，避免嵌套 commit 导致无法整体回滚。
        """
        self.batch_repo.update(batch_id, updates)

    def delete(self, batch_id: Any) -> None:
        bid = self._normalize_text(batch_id)
        if not bid:
            raise ValidationError("“批次号”不能为空", field="批次号")
        self._get_or_raise(bid)

        # 按 schema 约束，删除批次会级联删除 BatchOperations；Schedule 也会因 op_id 外键级联删除
        with self.tx_manager.transaction():
            self.batch_repo.delete(bid)

    # -------------------------
    # 批次工序生成（P6-01：关键事务边界）
    # -------------------------
    def create_batch_from_template(
        self,
        batch_id: Any,
        part_no: Any,
        quantity: Any,
        due_date: Any = None,
        priority: Any = BatchPriority.NORMAL.value,
        ready_status: Any = ReadyStatus.NO.value,
        remark: Any = None,
        rebuild_ops: bool = False,
    ) -> Batch:
        """
        从零件模板创建批次（事务保护）：
        - 先创建 Batches
        - 再复制 PartOperations -> BatchOperations
        任意一步失败必须整体回滚，避免“批次有了但工序没生成”的脏数据。
        """
        bid = self._normalize_text(batch_id)
        if not bid:
            raise ValidationError("“批次号”不能为空", field="批次号")

        pn = self._normalize_text(part_no)
        if not pn:
            raise ValidationError("“图号”不能为空", field="图号")

        qty = self._normalize_int(quantity, field="数量", allow_none=False)
        if qty is None or qty <= 0:
            raise ValidationError("“数量”必须大于 0", field="数量")

        pr = self._normalize_text(priority) or BatchPriority.NORMAL.value
        rs = self._normalize_text(ready_status) or ReadyStatus.NO.value
        self._validate_enum(pr, (BatchPriority.NORMAL.value, BatchPriority.URGENT.value, BatchPriority.CRITICAL.value), "优先级")
        self._validate_enum(rs, (ReadyStatus.YES.value, ReadyStatus.NO.value, ReadyStatus.PARTIAL.value), "齐套")

        part = self.part_repo.get(pn)
        if not part:
            raise BusinessError(ErrorCode.NOT_FOUND, f"图号“{pn}”不存在，请先在工艺管理中维护零件。")

        template_ops = self.part_op_repo.list_by_part(pn, include_deleted=False)
        if not template_ops:
            raise BusinessError(
                ErrorCode.ROUTE_PARSE_ERROR,
                "该零件尚未生成工序模板，无法创建批次工序。请先在工艺管理中解析工艺路线并保存模板。",
            )

        with self.tx_manager.transaction():
            self.create_batch_from_template_no_tx(
                batch_id=bid,
                part_no=pn,
                quantity=int(qty),
                due_date=self._normalize_date(due_date),
                priority=pr,
                ready_status=rs,
                remark=self._normalize_text(remark),
                rebuild_ops=rebuild_ops,
            )

        return self._get_or_raise(bid)

    def create_batch_from_template_no_tx(
        self,
        batch_id: str,
        part_no: str,
        quantity: int,
        due_date: Optional[str],
        priority: str,
        ready_status: str,
        remark: Optional[str],
        rebuild_ops: bool = False,
    ) -> None:
        """
        从零件模板生成/重建批次工序（不控制事务）。

        说明：
        - 供 Excel 批量导入在“外部已开启事务”时使用，避免嵌套 commit 导致无法整体回滚。
        """
        bid = self._normalize_text(batch_id)
        pn = self._normalize_text(part_no)
        if not bid:
            raise ValidationError("“批次号”不能为空", field="批次号")
        if not pn:
            raise ValidationError("“图号”不能为空", field="图号")
        if quantity is None or int(quantity) <= 0:
            raise ValidationError("“数量”必须大于 0", field="数量")

        pr = self._normalize_text(priority) or BatchPriority.NORMAL.value
        rs = self._normalize_text(ready_status) or ReadyStatus.NO.value
        self._validate_enum(pr, (BatchPriority.NORMAL.value, BatchPriority.URGENT.value, BatchPriority.CRITICAL.value), "优先级")
        self._validate_enum(rs, (ReadyStatus.YES.value, ReadyStatus.NO.value, ReadyStatus.PARTIAL.value), "齐套")

        part = self.part_repo.get(pn)
        if not part:
            raise BusinessError(ErrorCode.NOT_FOUND, f"图号“{pn}”不存在，请先在工艺管理中维护零件。")

        template_ops = self.part_op_repo.list_by_part(pn, include_deleted=False)
        if not template_ops:
            raise BusinessError(
                ErrorCode.ROUTE_PARSE_ERROR,
                "该零件尚未生成工序模板，无法创建批次工序。请先在工艺管理中解析工艺路线并保存模板。",
            )

        # 允许 rebuild：先删后建（但只影响同一个 batch_id）
        if self.batch_repo.get(bid):
            if rebuild_ops:
                self.batch_op_repo.delete_by_batch(bid)
            else:
                raise BusinessError(ErrorCode.BATCH_ALREADY_EXISTS, f"批次号“{bid}”已存在，不能重复添加。")
        else:
            self.batch_repo.create(
                {
                    "batch_id": bid,
                    "part_no": pn,
                    "part_name": part.part_name,
                    "quantity": int(quantity),
                    "due_date": due_date,
                    "priority": pr,
                    "ready_status": rs,
                    "status": BatchStatus.PENDING.value,
                    "remark": remark,
                }
            )

        for tmpl in template_ops:
            seq = int(tmpl.seq)
            op_code = f"{bid}_{seq:02d}"

            source = (tmpl.source or SourceType.INTERNAL.value).strip()
            if source not in (SourceType.INTERNAL.value, SourceType.EXTERNAL.value):
                source = SourceType.INTERNAL.value

            payload: Dict[str, Any] = {
                "op_code": op_code,
                "batch_id": bid,
                "piece_id": None,
                "seq": seq,
                "op_type_id": tmpl.op_type_id,
                "op_type_name": tmpl.op_type_name,
                "source": source,
                "machine_id": None,
                "operator_id": None,
                "supplier_id": tmpl.supplier_id if source == SourceType.EXTERNAL.value else None,
                "setup_hours": float(tmpl.setup_hours or 0.0),
                "unit_hours": float(tmpl.unit_hours or 0.0),
                "ext_days": float(tmpl.ext_days) if tmpl.ext_days is not None and tmpl.ext_days != "" else None,
                "status": "pending",
            }
            self.batch_op_repo.create(payload)

    def list_operations(self, batch_id: Any) -> List[BatchOperation]:
        bid = self._normalize_text(batch_id)
        if not bid:
            raise ValidationError("“批次号”不能为空", field="批次号")
        self._get_or_raise(bid)
        return self.batch_op_repo.list_by_batch(bid)

