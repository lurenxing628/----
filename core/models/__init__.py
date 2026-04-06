"""
领域模型（数据结构定义）。

说明：
- V1 使用 sqlite3（不引入 ORM），模型仅作为数据载体
- 字段名与数据库列名保持一致，便于 repo 映射与 Excel 导入导出
"""

from __future__ import annotations

from .batch import Batch
from .batch_material import BatchMaterial
from .batch_operation import BatchOperation
from .calendar import OperatorCalendar, WorkCalendar
from .config import ScheduleConfig
from .enums import (
    BatchPriority,
    BatchStatus,
    CalendarDayType,
    DowntimeScopeType,
    LockStatus,
    MachineStatus,
    MaterialStatus,
    MergeMode,
    OperatorStatus,
    ReadyStatus,
    ResourceTeamStatus,
    SkillLevel,
    SourceType,
    SupplierStatus,
    YesNo,
)
from .external_group import ExternalGroup
from .machine import Machine
from .machine_downtime import MachineDowntime
from .material import Material
from .op_type import OpType
from .operation_log import OperationLog
from .operator import Operator
from .operator_machine import OperatorMachine
from .part import Part
from .part_operation import PartOperation
from .resource_team import ResourceTeam
from .schedule import Schedule
from .schedule_history import ScheduleHistory
from .supplier import Supplier
from .system_config import SystemConfig
from .system_job_state import SystemJobState

__all__ = [
    # enums
    "YesNo",
    "OperatorStatus",
    "MachineStatus",
    "ResourceTeamStatus",
    "SupplierStatus",
    "MaterialStatus",
    "SourceType",
    "BatchPriority",
    "ReadyStatus",
    "BatchStatus",
    "CalendarDayType",
    "MergeMode",
    "LockStatus",
    "DowntimeScopeType",
    "SkillLevel",
    # models
    "Operator",
    "OpType",
    "Machine",
    "ResourceTeam",
    "MachineDowntime",
    "OperatorMachine",
    "Supplier",
    "Part",
    "PartOperation",
    "ExternalGroup",
    "Batch",
    "BatchOperation",
    "Schedule",
    "WorkCalendar",
    "OperatorCalendar",
    "ScheduleConfig",
    "SystemConfig",
    "OperationLog",
    "ScheduleHistory",
    "SystemJobState",
    "Material",
    "BatchMaterial",
]
