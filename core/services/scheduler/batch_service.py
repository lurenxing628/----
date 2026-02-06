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
        - 支持字符串：YYYY-MM-DD / YYYY/MM/DD / YYYY-MM-DD HH:MM(:SS) / YYYY-MM-DDTHH:MM
        - 支持 datetime/date
        """
        if value is None:
            return None
        from datetime import date as _date, datetime as _dt

        if isinstance(value, _dt):
            return value.date().isoformat()
        if isinstance(value, _date):
            return value.isoformat()

        v = str(value).strip()
        if not v:
            return None
        v = v.replace("/", "-")
        # 允许带时间：只取日期部分
        if "T" in v:
            v = v.split("T", 1)[0]
        if " " in v:
            v = v.split(" ", 1)[0]
        try:
            return _dt.strptime(v, "%Y-%m-%d").date().isoformat()
        except Exception:
            raise ValidationError("日期格式不合法（期望：YYYY-MM-DD）", field="日期")

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
        ready_status: Any = ReadyStatus.YES.value,
        ready_date: Any = None,
        status: Any = BatchStatus.PENDING.value,
        remark: Any = None,
        part_name: Any = None,
    ) -> Batch:
        bid = self._normalize_text(batch_id)
        pn = self._normalize_text(part_no)
        qty = self._normalize_int(quantity, field="数量", allow_none=False)
        dd = self._normalize_date(due_date)
        pr = self._normalize_text(priority) or BatchPriority.NORMAL.value
        rs = self._normalize_text(ready_status) or ReadyStatus.YES.value
        rd = self._normalize_date(ready_date)
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
                    "ready_date": rd,
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
        ready_date: Any = None,
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

        if ready_date is not None:
            updates["ready_date"] = self._normalize_date(ready_date)

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

    def copy_batch(self, source_batch_id: Any, new_batch_id: Any) -> Batch:
        """
        复制批次（含批次工序），用于批量复制/快速建相似批次。

        规则：
        - 新批次 status 固定为 pending
        - 新批次工序 status 固定为 pending（不复制 scheduled 等状态）
        - 其它字段尽量保持一致（图号/数量/交期/优先级/齐套/备注/工序补充信息等）
        """
        src = self._normalize_text(source_batch_id)
        dst = self._normalize_text(new_batch_id)
        if not src:
            raise ValidationError("“源批次号”不能为空", field="源批次号")
        if not dst:
            raise ValidationError("“新批次号”不能为空", field="新批次号")
        if src == dst:
            raise ValidationError("新批次号不能与源批次号相同", field="新批次号")

        b = self._get_or_raise(src)
        if self.batch_repo.get(dst):
            raise BusinessError(ErrorCode.BATCH_ALREADY_EXISTS, f"批次号“{dst}”已存在，不能复制。")

        ops = self.batch_op_repo.list_by_batch(src)
        with self.tx_manager.transaction():
            # 创建新批次
            self.batch_repo.create(
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
                self.batch_op_repo.create(
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
                        "ext_days": float(op.ext_days) if op.ext_days is not None and op.ext_days != "" else None,
                        "status": "pending",
                    }
                )

        return self._get_or_raise(dst)

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
        ready_status: Any = ReadyStatus.YES.value,
        ready_date: Any = None,
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
        rs = self._normalize_text(ready_status) or ReadyStatus.YES.value
        rd = self._normalize_date(ready_date)
        self._validate_enum(pr, (BatchPriority.NORMAL.value, BatchPriority.URGENT.value, BatchPriority.CRITICAL.value), "优先级")
        self._validate_enum(rs, (ReadyStatus.YES.value, ReadyStatus.NO.value, ReadyStatus.PARTIAL.value), "齐套")

        part = self.part_repo.get(pn)
        if not part:
            raise BusinessError(ErrorCode.NOT_FOUND, f"图号“{pn}”不存在，请先在工艺管理中维护零件。")

        template_ops = self.part_op_repo.list_by_part(pn, include_deleted=False)
        if not template_ops:
            # 若模板缺失：尝试从 Parts.route_raw 自动解析并保存模板（减少“创建批次报错”）
            rr = (part.route_raw or "").strip() if getattr(part, "route_raw", None) is not None else ""
            if rr:
                try:
                    from core.services.process.part_service import PartService

                    PartService(self.conn, logger=self.logger, op_logger=self.op_logger).reparse_and_save(part_no=pn, route_raw=rr)
                except Exception as e:
                    raise BusinessError(
                        ErrorCode.ROUTE_PARSE_ERROR,
                        "该零件尚未生成工序模板，且自动解析失败。请到【工艺管理-工序模板】中检查工艺路线并重新解析。",
                        cause=e,
                    )
                template_ops = self.part_op_repo.list_by_part(pn, include_deleted=False)

            if not template_ops:
                raise BusinessError(
                    ErrorCode.ROUTE_PARSE_ERROR,
                    "该零件尚未生成工序模板，无法创建批次工序。请先在【工艺管理-工序模板】中解析工艺路线并保存模板。",
                )

        with self.tx_manager.transaction():
            self.create_batch_from_template_no_tx(
                batch_id=bid,
                part_no=pn,
                quantity=int(qty),
                due_date=self._normalize_date(due_date),
                priority=pr,
                ready_status=rs,
                ready_date=rd,
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
        ready_date: Optional[str],
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
        rs = self._normalize_text(ready_status) or ReadyStatus.YES.value
        self._validate_enum(pr, (BatchPriority.NORMAL.value, BatchPriority.URGENT.value, BatchPriority.CRITICAL.value), "优先级")
        self._validate_enum(rs, (ReadyStatus.YES.value, ReadyStatus.NO.value, ReadyStatus.PARTIAL.value), "齐套")

        part = self.part_repo.get(pn)
        if not part:
            raise BusinessError(ErrorCode.NOT_FOUND, f"图号“{pn}”不存在，请先在工艺管理中维护零件。")

        template_ops = self.part_op_repo.list_by_part(pn, include_deleted=False)
        if not template_ops:
            rr = (part.route_raw or "").strip() if getattr(part, "route_raw", None) is not None else ""
            if rr:
                try:
                    from core.services.process.part_service import PartService

                    # no_tx：在外部事务中覆盖保存模板（避免嵌套事务）
                    PartService(self.conn, logger=self.logger, op_logger=self.op_logger).upsert_and_parse_no_tx(
                        part_no=pn, part_name=part.part_name or pn, route_raw=rr
                    )
                except Exception as e:
                    raise BusinessError(
                        ErrorCode.ROUTE_PARSE_ERROR,
                        "该零件尚未生成工序模板，且自动解析失败。请到【工艺管理-工序模板】中检查工艺路线并重新解析。",
                        cause=e,
                    )
                template_ops = self.part_op_repo.list_by_part(pn, include_deleted=False)

            if not template_ops:
                raise BusinessError(
                    ErrorCode.ROUTE_PARSE_ERROR,
                    "该零件尚未生成工序模板，无法创建批次工序。请先在【工艺管理-工序模板】中解析工艺路线并保存模板。",
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
                    "ready_date": self._normalize_date(ready_date),
                    "status": BatchStatus.PENDING.value,
                    "remark": remark,
                }
            )

        for tmpl in template_ops:
            seq = int(tmpl.seq)
            op_code = f"{bid}_{seq:02d}"

            source = (tmpl.source or SourceType.INTERNAL.value).strip().lower()
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

