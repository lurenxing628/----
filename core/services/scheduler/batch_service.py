from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import Batch, BatchOperation
from core.models.enums import BatchPriority, BatchStatus, ReadyStatus
from core.services.common.excel_service import ImportMode
from core.services.common.normalize import normalize_text
from data.repositories import BatchOperationRepository, BatchRepository, PartOperationRepository, PartRepository

from . import batch_copy, batch_excel_import, batch_template_ops, batch_write_rules
from .number_utils import parse_finite_int


class BatchService:
    """批次服务（Batches + BatchOperations）。"""

    def __init__(
        self,
        conn,
        logger=None,
        op_logger=None,
        template_resolver: Optional[Callable[..., Any]] = None,
    ):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self._user_visible_warnings: List[str] = []

        self.batch_repo = BatchRepository(conn, logger=logger)
        self.batch_op_repo = BatchOperationRepository(conn, logger=logger)
        self.part_repo = PartRepository(conn, logger=logger)
        self.part_op_repo = PartOperationRepository(conn, logger=logger)
        self._template_resolver = template_resolver or batch_template_ops.default_template_resolver_factory(self)

    def consume_user_visible_warnings(self) -> List[str]:
        warnings = list(self._user_visible_warnings)
        self._user_visible_warnings.clear()
        return warnings

    # -------------------------
    # 工具方法 / 校验
    # -------------------------
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    @staticmethod
    def _normalize_int(value: Any, field: str, allow_none: bool = False) -> Optional[int]:
        return parse_finite_int(value, field=field, allow_none=allow_none)

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == "":
            return None
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _normalize_date(value: Any) -> Optional[str]:
        """
        交期（due_date）存储为 SQLite DATE，V1 以字符串 `YYYY-MM-DD` 为主。

        设计决策：Web 编辑接受含时间的日期并截断时间部分（如 "2026-01-01 08:00" → "2026-01-01"），
        而 Excel 导入使用 excel_validators._normalize_batch_date_cell 更严格地拒绝含时间的值。
        两者有意不统一：Excel 作为批量入口更应严格把关。

        - 允许为空
        - 支持字符串：YYYY-MM-DD / YYYY/MM/DD / YYYY-MM-DD HH:MM(:SS) / YYYY-MM-DDTHH:MM
        - 支持 datetime/date
        """
        if value is None:
            return None
        from datetime import date as _date
        from datetime import datetime as _dt

        if isinstance(value, _dt):
            return value.date().isoformat()
        if isinstance(value, _date):
            return value.isoformat()

        text = str(value).strip()
        if not text:
            return None
        text = text.replace("/", "-")
        if "T" in text:
            text = text.split("T", 1)[0]
        if " " in text:
            text = text.split(" ", 1)[0]
        try:
            return _dt.strptime(text, "%Y-%m-%d").date().isoformat()
        except Exception as exc:
            raise ValidationError("日期格式不合法（期望：YYYY-MM-DD）", field="日期") from exc

    @staticmethod
    def _validate_enum(value: Optional[str], allowed: tuple[str, ...], field: str) -> Optional[str]:
        if value is None:
            return None
        if value not in allowed:
            if field == "优先级":
                allow_text = "普通 / 急件 / 特急"
            elif field == "齐套":
                allow_text = "齐套 / 未齐套 / 部分齐套"
            elif field == "状态":
                allow_text = "待排 / 已排 / 加工中 / 已完成 / 已取消"
            else:
                allow_text = " / ".join(list(allowed))
            raise ValidationError(f"“{field}”不正确，请选择：{allow_text}。", field=field)
        return value

    def _get_or_raise(self, batch_id: str) -> Batch:
        batch = self.batch_repo.get(batch_id)
        if not batch:
            raise BusinessError(ErrorCode.BATCH_NOT_FOUND, f"批次“{batch_id}”不存在")
        return batch

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
        batch_id_text = self._normalize_text(batch_id)
        if not batch_id_text:
            raise ValidationError("“批次号”不能为空", field="批次号")
        return self._get_or_raise(batch_id_text)

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
        batch_id_text = self._normalize_text(batch_id)
        if not batch_id_text:
            raise ValidationError("“批次号”不能为空", field="批次号")
        if self.batch_repo.get(batch_id_text):
            raise BusinessError(ErrorCode.BATCH_ALREADY_EXISTS, f"批次号“{batch_id_text}”已存在，不能重复添加。")

        payload = batch_write_rules.build_create_payload(
            self,
            batch_id=batch_id_text,
            part_no=part_no,
            quantity=quantity,
            due_date=due_date,
            priority=priority,
            ready_status=ready_status,
            ready_date=ready_date,
            status=status,
            remark=remark,
            part_name=part_name,
        )
        with self.tx_manager.transaction():
            self.create_no_tx(payload)
        return self._get_or_raise(batch_id_text)

    def create_no_tx(self, payload: Dict[str, Any]) -> Batch:
        """
        创建批次（不控制事务）。

        说明：
        - 供 Excel 批量导入在“外部已开启事务”时使用，避免嵌套 commit 导致无法整体回滚。
        """
        batch = payload if isinstance(payload, Batch) else Batch.from_row(payload)
        self.batch_repo.create(batch.to_dict())
        return batch

    def update(
        self,
        batch_id: Any,
        part_no: Any = batch_write_rules._MISSING,
        quantity: Any = batch_write_rules._MISSING,
        due_date: Any = batch_write_rules._MISSING,
        priority: Any = batch_write_rules._MISSING,
        ready_status: Any = batch_write_rules._MISSING,
        ready_date: Any = batch_write_rules._MISSING,
        status: Any = batch_write_rules._MISSING,
        remark: Any = batch_write_rules._MISSING,
        part_name: Any = batch_write_rules._MISSING,
    ) -> Batch:
        batch_id_text = self._normalize_text(batch_id)
        if not batch_id_text:
            raise ValidationError("“批次号”不能为空", field="批次号")
        batch = self._get_or_raise(batch_id_text)

        update_kwargs: Dict[str, Any] = {
            "current_part_no": getattr(batch, "part_no", None),
            # 公开更新接口默认不重建工序，因此图号切换保护始终生效
            "auto_generate_ops": False,
        }
        for field_name, field_value in {
            "part_no": part_no,
            "quantity": quantity,
            "due_date": due_date,
            "priority": priority,
            "ready_status": ready_status,
            "ready_date": ready_date,
            "status": status,
            "remark": remark,
            "part_name": part_name,
        }.items():
            if field_value is not batch_write_rules._MISSING:
                update_kwargs[field_name] = field_value

        updates = batch_write_rules.build_update_payload(self, **update_kwargs)
        if updates:
            with self.tx_manager.transaction():
                self.update_no_tx(batch_id_text, updates)
        return self._get_or_raise(batch_id_text)



    def update_no_tx(self, batch_id: str, updates: Dict[str, Any]) -> None:
        """
        更新批次（不控制事务）。

        说明：
        - 供 Excel 批量导入在“外部已开启事务”时使用，避免嵌套 commit 导致无法整体回滚。
        """
        self.batch_repo.update(batch_id, updates)

    def delete(self, batch_id: Any) -> None:
        batch_id_text = self._normalize_text(batch_id)
        if not batch_id_text:
            raise ValidationError("“批次号”不能为空", field="批次号")
        self._get_or_raise(batch_id_text)
        with self.tx_manager.transaction():
            self.batch_repo.delete(batch_id_text)

    def delete_all_no_tx(self) -> None:
        """
        清空全部批次（不控制事务）。

        说明：
        - 供 Excel 批量导入在“外部已开启事务”时使用，避免嵌套 commit 导致无法整体回滚。
        - 按 schema 约束会级联删除相关批次工序与排程记录。
        """
        self.batch_repo.delete_all()

    def import_from_preview_rows(
        self,
        *,
        preview_rows: List[Any],
        mode: ImportMode,
        parts_cache: Dict[str, Any],
        auto_generate_ops: bool = False,
        strict_mode: bool = False,
        existing_ids: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        return batch_excel_import.import_batches_from_preview_rows(
            self,
            preview_rows=preview_rows,
            mode=mode,
            parts_cache=parts_cache,
            auto_generate_ops=bool(auto_generate_ops),
            strict_mode=bool(strict_mode),
            existing_ids=existing_ids,
        )

    def copy_batch(self, source_batch_id: Any, new_batch_id: Any) -> Batch:
        return batch_copy.copy_batch(self, source_batch_id, new_batch_id)

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
        strict_mode: bool = False,
    ) -> Batch:
        """
        从零件模板创建批次（事务保护）：
        - 先创建 Batches
        - 再复制 PartOperations -> BatchOperations
        任意一步失败必须整体回滚，避免“批次有了但工序没生成”的脏数据。
        """
        self.consume_user_visible_warnings()
        batch_id_text = self._normalize_text(batch_id)
        if not batch_id_text:
            raise ValidationError("“批次号”不能为空", field="批次号")

        part_no_text = self._normalize_text(part_no)
        if not part_no_text:
            raise ValidationError("“图号”不能为空", field="图号")

        quantity_value = self._normalize_int(quantity, field="数量", allow_none=False)
        if quantity_value is None or quantity_value <= 0:
            raise ValidationError("“数量”必须大于 0", field="数量")

        priority_text = self._normalize_text(priority) or BatchPriority.NORMAL.value
        ready_status_text = self._normalize_text(ready_status) or ReadyStatus.YES.value
        ready_date_text = self._normalize_date(ready_date)
        self._validate_enum(priority_text, (BatchPriority.NORMAL.value, BatchPriority.URGENT.value, BatchPriority.CRITICAL.value), "优先级")
        self._validate_enum(ready_status_text, (ReadyStatus.YES.value, ReadyStatus.NO.value, ReadyStatus.PARTIAL.value), "齐套")

        part = self.part_repo.get(part_no_text)
        if not part:
            raise BusinessError(ErrorCode.NOT_FOUND, f"图号“{part_no_text}”不存在，请先在工艺管理中维护零件。")

        template_probe = batch_template_ops.probe_template_ops_readonly(self, part_no_text, part)
        with self.tx_manager.transaction():
            self.create_batch_from_template_no_tx(
                batch_id=batch_id_text,
                part_no=part_no_text,
                quantity=int(quantity_value),
                due_date=self._normalize_date(due_date),
                priority=priority_text,
                ready_status=ready_status_text,
                ready_date=ready_date_text,
                remark=self._normalize_text(remark),
                rebuild_ops=rebuild_ops,
                strict_mode=bool(strict_mode),
                template_probe=template_probe,
            )
        return self._get_or_raise(batch_id_text)

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
        strict_mode: bool = False,
        template_probe: Optional[Dict[str, Any]] = None,
    ) -> None:
        batch_template_ops.create_batch_from_template_no_tx(
            self,
            batch_id=batch_id,
            part_no=part_no,
            quantity=quantity,
            due_date=due_date,
            priority=priority,
            ready_status=ready_status,
            ready_date=ready_date,
            remark=remark,
            rebuild_ops=rebuild_ops,
            strict_mode=bool(strict_mode),
            template_probe=template_probe,
        )

    def list_operations(self, batch_id: Any) -> List[BatchOperation]:
        batch_id_text = self._normalize_text(batch_id)
        if not batch_id_text:
            raise ValidationError("“批次号”不能为空", field="批次号")
        self._get_or_raise(batch_id_text)
        return self.batch_op_repo.list_by_batch(batch_id_text)
