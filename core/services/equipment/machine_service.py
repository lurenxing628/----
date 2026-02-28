from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import Machine
from core.models.enums import MachineStatus
from core.services.common.normalize import normalize_text
from data.repositories import MachineRepository, OpTypeRepository


class MachineService:
    """设备服务（Machines）。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)

        self.repo = MachineRepository(conn, logger=logger)
        self.op_type_repo = OpTypeRepository(conn, logger=logger)

    # -------------------------
    # 校验与工具方法
    # -------------------------
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    @staticmethod
    def _normalize_status(value: Any) -> Optional[str]:
        """
        设备状态标准化（允许中英文混用输入）：
        - active / 可用
        - maintain / 维修/维护
        - inactive / 停用
        """
        v = MachineService._normalize_text(value)
        if v is None:
            return None

        # 中文兼容
        if v in ("可用", "启用", "正常"):
            return MachineStatus.ACTIVE.value
        if v in ("维修", "维护", "保养", "维护中", "维修中"):
            return MachineStatus.MAINTAIN.value
        if v in ("停用", "禁用", "不可用"):
            return MachineStatus.INACTIVE.value

        # 英文/枚举
        if v in (
            MachineStatus.ACTIVE.value,
            MachineStatus.INACTIVE.value,
            MachineStatus.MAINTAIN.value,
        ):
            return v
        raise ValidationError("“状态”不合法（允许：active / inactive / maintain）", field="状态")

    def _validate_machine_fields(
        self,
        machine_id: Any,
        name: Any,
        status: Any,
        op_type_id: Any = None,
        allow_partial: bool = False,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        mc_id = self._normalize_text(machine_id)
        mc_name = self._normalize_text(name)
        mc_status = self._normalize_status(status) if status is not None or not allow_partial else None
        mc_op_type_id = self._normalize_text(op_type_id)

        if not allow_partial:
            if not mc_id:
                raise ValidationError("“设备编号”不能为空", field="设备编号")
            if not mc_name:
                raise ValidationError("“设备名称”不能为空", field="设备名称")
            if not mc_status:
                # status 允许省略时默认 active，但 UI/Excel 一般会显式传
                mc_status = MachineStatus.ACTIVE.value

        # 工种存在性校验（可为空）
        if mc_op_type_id:
            if not self.op_type_repo.get(mc_op_type_id):
                raise BusinessError(ErrorCode.NOT_FOUND, f"工种“{mc_op_type_id}”不存在，请先维护工种配置。")

        return mc_id, mc_name, mc_status, mc_op_type_id

    def _get_or_raise(self, machine_id: str) -> Machine:
        m = self.repo.get(machine_id)
        if not m:
            raise BusinessError(ErrorCode.MACHINE_NOT_FOUND, f"设备“{machine_id}”不存在")
        return m

    # -------------------------
    # CRUD
    # -------------------------
    def list(self, status: Optional[str] = None, op_type_id: Optional[str] = None) -> List[Machine]:
        if status:
            # 校验一下 status（避免页面/接口传错）
            self._validate_machine_fields(machine_id="DUMMY", name="DUMMY", status=status, allow_partial=True)
        if op_type_id:
            # 校验一下工种存在（避免页面传错）
            ot = self.op_type_repo.get(op_type_id)
            if not ot:
                raise BusinessError(ErrorCode.NOT_FOUND, f"工种“{op_type_id}”不存在")
        return self.repo.list(status=status, op_type_id=op_type_id)

    def get(self, machine_id: str) -> Machine:
        mc_id = self._normalize_text(machine_id)
        if not mc_id:
            raise ValidationError("“设备编号”不能为空", field="设备编号")
        return self._get_or_raise(mc_id)

    def get_optional(self, machine_id: Any) -> Optional[Machine]:
        """
        宽松查询：找不到返回 None（用于页面回显“已删除/已停用”资源）。
        """
        mc_id = self._normalize_text(machine_id)
        if not mc_id:
            return None
        return self.repo.get(mc_id)

    def create(
        self,
        machine_id: Any,
        name: Any,
        op_type_id: Any = None,
        category: Any = None,
        status: Any = "active",
        remark: Any = None,
    ) -> Machine:
        mc_id, mc_name, mc_status, mc_op_type_id = self._validate_machine_fields(
            machine_id=machine_id, name=name, status=status, op_type_id=op_type_id
        )
        mc_remark = self._normalize_text(remark)
        mc_category = self._normalize_text(category)

        if self.repo.exists(mc_id):
            raise BusinessError(ErrorCode.MACHINE_ALREADY_EXISTS, f"设备编号“{mc_id}”已存在，不能重复添加。")

        with self.tx_manager.transaction():
            self.repo.create(
                {
                    "machine_id": mc_id,
                    "name": mc_name,
                    "op_type_id": mc_op_type_id,
                    "category": mc_category,
                    "status": mc_status or MachineStatus.ACTIVE.value,
                    "remark": mc_remark,
                }
            )
        return self._get_or_raise(mc_id)

    def update(
        self,
        machine_id: Any,
        name: Any = None,
        op_type_id: Any = None,
        category: Any = None,
        status: Any = None,
        remark: Any = None,
    ) -> Machine:
        mc_id = self._normalize_text(machine_id)
        if not mc_id:
            raise ValidationError("“设备编号”不能为空", field="设备编号")
        self._get_or_raise(mc_id)

        updates: Dict[str, Any] = {}
        if name is not None:
            updates["name"] = self._normalize_text(name)
            if not updates["name"]:
                raise ValidationError("“设备名称”不能为空", field="设备名称")
        if status is not None:
            updates["status"] = self._normalize_status(status)
        if op_type_id is not None:
            # 允许显式清空：传空串/None → 写 NULL
            v = self._normalize_text(op_type_id)
            if v:
                if not self.op_type_repo.get(v):
                    raise BusinessError(ErrorCode.NOT_FOUND, f"工种“{v}”不存在，请先维护工种配置。")
                updates["op_type_id"] = v
            else:
                updates["op_type_id"] = None
        if remark is not None:
            updates["remark"] = self._normalize_text(remark)  # 允许显式清空为 NULL
        if category is not None:
            # 允许显式清空
            updates["category"] = self._normalize_text(category)

        with self.tx_manager.transaction():
            self.repo.update(mc_id, updates)
        return self._get_or_raise(mc_id)

    def set_status(self, machine_id: Any, status: Any) -> Machine:
        return self.update(machine_id=machine_id, status=status)

    def delete(self, machine_id: Any) -> None:
        mc_id = self._normalize_text(machine_id)
        if not mc_id:
            raise ValidationError("“设备编号”不能为空", field="设备编号")

        # 若被批次工序引用，则禁止删除（避免排产数据断链）
        row = self.conn.execute(
            "SELECT 1 FROM BatchOperations WHERE machine_id = ? LIMIT 1",
            (mc_id,),
        ).fetchone()
        if row is not None:
            raise BusinessError(ErrorCode.MACHINE_IN_USE, "该设备已被批次工序引用，不能删除。请先解除引用或改为“停用”。")

        with self.tx_manager.transaction():
            self.repo.delete(mc_id)

    # -------------------------
    # Excel 相关辅助（按中文列名）
    # -------------------------
    def build_existing_for_excel(self) -> Dict[str, Dict[str, Any]]:
        """
        构建给 ExcelService.preview_import 使用的 existing_data：
        - key: 设备编号
        - value: 以 Excel 列名（中文）表示的 dict
        """
        op_types = {ot.op_type_id: ot for ot in self.op_type_repo.list()}
        existing: Dict[str, Dict[str, Any]] = {}
        for m in self.repo.list():
            ot = op_types.get(m.op_type_id or "")
            existing[m.machine_id] = {
                "设备编号": m.machine_id,
                "设备名称": m.name,
                "工种": (ot.name if ot else None),
                "状态": m.status,
            }
        return existing

    def list_for_export(self) -> List[Dict[str, Any]]:
        """
        导出用：返回带工种名称的扁平行（字段名与 Excel 导出路由一致）。
        """
        return self.repo.list_for_export()

    def ensure_replace_allowed(self) -> None:
        """
        REPLACE（清空后导入）保护：
        如果设备已被批次工序引用（BatchOperations.machine_id），则禁止清空。
        """
        row = self.conn.execute(
            "SELECT 1 FROM BatchOperations WHERE machine_id IS NOT NULL AND TRIM(machine_id) <> '' LIMIT 1"
        ).fetchone()
        if row is not None:
            raise BusinessError(
                ErrorCode.MACHINE_IN_USE,
                "已有批次工序引用了设备，不能执行“替换（清空后导入）”。请先解除引用或改用“覆盖/追加”。",
            )

