from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import MachineDowntime
from core.models.enums import MachineDowntimeStatus, MachineStatus
from core.services.common.normalize import normalize_text
from data.repositories import MachineDowntimeRepository, MachineRepository


class MachineDowntimeService:
    """设备停机时间段服务（MachineDowntimes）。"""

    # 预留：原因枚举（UI 下拉固定；后续可升级为可配置表）
    REASON_OPTIONS: Tuple[Tuple[str, str], ...] = (
        ("maintenance", "计划维护"),
        ("breakdown", "故障停机"),
        ("power", "停电/能耗"),
        ("tooling", "换刀/工装"),
        ("other", "其他"),
    )
    VALID_REASON_CODES = tuple([x[0] for x in REASON_OPTIONS])

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self.repo = MachineDowntimeRepository(conn, logger=logger)
        self.machine_repo = MachineRepository(conn, logger=logger)

    # -------------------------
    # 工具：标准化
    # -------------------------
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    @staticmethod
    def _parse_datetime(value: Any, field: str) -> datetime:
        """
        支持：
        - HTML datetime-local：YYYY-MM-DDTHH:MM（或带秒）
        - 常见字符串：YYYY-MM-DD HH:MM（或带秒）
        """
        v = MachineDowntimeService._normalize_text(value)
        if not v:
            raise ValidationError(f"“{field}”不能为空", field=field)
        s = v.replace("/", "-").replace("T", " ").replace("：", ":")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        raise ValidationError(f"“{field}”格式不合法（期望：YYYY-MM-DD HH:MM）", field=field)

    @staticmethod
    def _to_db_datetime(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _ensure_machine_exists(self, machine_id: str) -> None:
        if not self.machine_repo.get(machine_id):
            raise BusinessError(ErrorCode.MACHINE_NOT_FOUND, f"设备“{machine_id}”不存在")

    # -------------------------
    # 查询
    # -------------------------
    def list_by_machine(self, machine_id: Any, include_cancelled: bool = False) -> List[MachineDowntime]:
        mc_id = self._normalize_text(machine_id)
        if not mc_id:
            raise ValidationError("“设备编号”不能为空", field="设备编号")
        self._ensure_machine_exists(mc_id)
        return self.repo.list_by_machine(mc_id, include_cancelled=include_cancelled)

    def get(self, downtime_id: Any) -> MachineDowntime:
        try:
            did = int(downtime_id)
        except Exception as e:
            raise ValidationError("停机记录 ID 不合法", field="downtime_id") from e
        d = self.repo.get(did)
        if not d:
            raise BusinessError(ErrorCode.NOT_FOUND, f"停机记录（ID={did}）不存在")
        return d

    # -------------------------
    # 新增/取消
    # -------------------------
    def create(
        self,
        machine_id: Any,
        start_time: Any,
        end_time: Any,
        reason_code: Any = None,
        reason_detail: Any = None,
    ) -> MachineDowntime:
        mc_id = self._normalize_text(machine_id)
        if not mc_id:
            raise ValidationError("“设备编号”不能为空", field="设备编号")
        self._ensure_machine_exists(mc_id)

        st = self._parse_datetime(start_time, field="停机开始时间")
        et = self._parse_datetime(end_time, field="停机结束时间")
        if et <= st:
            raise ValidationError("“停机结束时间”必须晚于“停机开始时间”", field="停机结束时间")

        rc = self._normalize_text(reason_code) or "maintenance"
        if rc not in self.VALID_REASON_CODES:
            raise ValidationError("“停机原因”不合法", field="停机原因")
        rd = self._normalize_text(reason_detail)

        st_db = self._to_db_datetime(st)
        et_db = self._to_db_datetime(et)

        # 重叠检测（只对 active 生效）
        if self.repo.has_overlap(mc_id, start_time=st_db, end_time=et_db, exclude_id=None):
            raise BusinessError(ErrorCode.SCHEDULE_CONFLICT, "该设备在该时间段已存在停机计划（时间段重叠）。请调整时间。")

        with self.tx_manager.transaction():
            d = self.repo.create(
                {
                    "machine_id": mc_id,
                    "scope_type": "machine",
                    "scope_value": mc_id,
                    "start_time": st_db,
                    "end_time": et_db,
                    "reason_code": rc,
                    "reason_detail": rd,
                    "status": MachineDowntimeStatus.ACTIVE.value,
                }
            )
        return d

    def create_by_scope(
        self,
        *,
        scope_type: Any,
        scope_value: Any = None,
        start_time: Any,
        end_time: Any,
        reason_code: Any = None,
        reason_detail: Any = None,
        only_active_machines: bool = True,
    ) -> Dict[str, Any]:
        """
        按范围批量创建停机计划：
        - scope_type=machine：scope_value=machine_id
        - scope_type=category：scope_value=Machines.category
        - scope_type=all：scope_value 可空/'*'

        说明：
        - 为兼容现有 schema 外键（MachineDowntimes.machine_id -> Machines.machine_id），当前实现会把范围展开为“按设备逐条写入”。
        - 对每台设备做重叠检测；重叠的会跳过并返回失败列表（其余仍会创建）。
        """
        st = self._parse_datetime(start_time, field="停机开始时间")
        et = self._parse_datetime(end_time, field="停机结束时间")
        if et <= st:
            raise ValidationError("“停机结束时间”必须晚于“停机开始时间”", field="停机结束时间")

        st_db = self._to_db_datetime(st)
        et_db = self._to_db_datetime(et)

        rc = self._normalize_text(reason_code) or "maintenance"
        if rc not in self.VALID_REASON_CODES:
            raise ValidationError("“停机原因”不合法", field="停机原因")
        rd = self._normalize_text(reason_detail)

        stype = (self._normalize_text(scope_type) or "").strip()
        if stype not in ("machine", "category", "all"):
            raise ValidationError("停机范围不正确，请选择：指定设备 / 按类别 / 全部。", field="停机范围")

        sval = self._normalize_text(scope_value)
        target_machine_ids: List[str] = []

        if stype == "machine":
            if not sval:
                raise ValidationError("scope_value 不能为空（machine 模式）", field="scope_value")
            self._ensure_machine_exists(sval)
            target_machine_ids = [sval]
        elif stype == "category":
            if not sval:
                raise ValidationError("scope_value 不能为空（category 模式）", field="scope_value")
            ms = self.machine_repo.list(status=MachineStatus.ACTIVE.value if only_active_machines else None, category=sval)
            target_machine_ids = [m.machine_id for m in ms]
        else:
            ms = self.machine_repo.list(status=MachineStatus.ACTIVE.value if only_active_machines else None)
            target_machine_ids = [m.machine_id for m in ms]
            sval = sval or "*"

        if not target_machine_ids:
            raise BusinessError(ErrorCode.NOT_FOUND, "未找到符合范围的设备，无法创建停机计划。")

        created_ids: List[int] = []
        skipped_overlap: List[str] = []

        with self.tx_manager.transaction():
            for mid in target_machine_ids:
                if self.repo.has_overlap(mid, start_time=st_db, end_time=et_db, exclude_id=None):
                    skipped_overlap.append(mid)
                    continue
                d = self.repo.create(
                    {
                        "machine_id": mid,
                        "scope_type": stype,
                        "scope_value": sval,
                        "start_time": st_db,
                        "end_time": et_db,
                        "reason_code": rc,
                        "reason_detail": rd,
                        "status": MachineDowntimeStatus.ACTIVE.value,
                    }
                )
                if d.id is not None:
                    created_ids.append(int(d.id))

        return {
            "scope_type": stype,
            "scope_value": sval,
            "start_time": st_db,
            "end_time": et_db,
            "created_count": len(created_ids),
            "created_ids": created_ids[:50],
            "skipped_overlap": skipped_overlap,
        }

    def cancel(self, downtime_id: Any, machine_id: Any = None) -> None:
        d = self.get(downtime_id)
        if machine_id is not None:
            mc_id = self._normalize_text(machine_id)
            if mc_id and d.machine_id != mc_id:
                raise BusinessError(ErrorCode.PERMISSION_DENIED, "该停机记录不属于当前设备，不能操作。")

        if (d.status or "").strip() != MachineDowntimeStatus.ACTIVE.value:
            # 幂等：已取消就不报错
            return

        with self.tx_manager.transaction():
            self.repo.cancel(int(d.id))

