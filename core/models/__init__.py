"""
领域模型（数据结构定义）。

说明：
- V1 使用 sqlite3（不引入 ORM），模型仅作为“数据载体”
- 字段名与数据库列名保持一致，便于 repo 映射与 Excel 导入导出
"""

from .enums import (
    YesNo,
    OperatorStatus,
    MachineStatus,
    SourceType,
    BatchPriority,
    ReadyStatus,
    BatchStatus,
    CalendarDayType,
    MergeMode,
)
from .operator import Operator
from .op_type import OpType
from .machine import Machine
from .machine_downtime import MachineDowntime
from .operator_machine import OperatorMachine
from .supplier import Supplier
from .part import Part
from .part_operation import PartOperation
from .external_group import ExternalGroup
from .batch import Batch
from .batch_operation import BatchOperation
from .schedule import Schedule
from .calendar import WorkCalendar
from .config import ScheduleConfig
from .system_config import SystemConfig
from .operation_log import OperationLog
from .schedule_history import ScheduleHistory
from .system_job_state import SystemJobState
from .material import Material
from .batch_material import BatchMaterial

__all__ = [
    # enums
    "YesNo",
    "OperatorStatus",
    "MachineStatus",
    "SourceType",
    "BatchPriority",
    "ReadyStatus",
    "BatchStatus",
    "CalendarDayType",
    "MergeMode",
    # models
    "Operator",
    "OpType",
    "Machine",
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
    "ScheduleConfig",
    "SystemConfig",
    "OperationLog",
    "ScheduleHistory",
    "SystemJobState",
    "Material",
    "BatchMaterial",
]

