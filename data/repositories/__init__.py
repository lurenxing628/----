"""
数据访问层（Repositories）。

约束：
- V1 不引入 ORM；统一使用 sqlite3 + repository 封装
- 服务层（core/services）应只依赖 repo，不直接写 SQL
"""

from __future__ import annotations

from .base_repo import BaseRepository
from .batch_material_repo import BatchMaterialRepository
from .batch_operation_repo import BatchOperationRepository
from .batch_repo import BatchRepository
from .calendar_repo import CalendarRepository
from .config_repo import ConfigRepository
from .external_group_repo import ExternalGroupRepository
from .machine_downtime_repo import MachineDowntimeRepository
from .machine_repo import MachineRepository
from .material_repo import MaterialRepository
from .op_type_repo import OpTypeRepository
from .operation_log_repo import OperationLogRepository
from .operator_calendar_repo import OperatorCalendarRepository
from .operator_machine_repo import OperatorMachineRepository
from .operator_repo import OperatorRepository
from .part_operation_repo import PartOperationRepository
from .part_repo import PartRepository
from .schedule_history_repo import ScheduleHistoryRepository
from .schedule_repo import ScheduleRepository
from .supplier_repo import SupplierRepository
from .system_config_repo import SystemConfigRepository
from .system_job_state_repo import SystemJobStateRepository

__all__ = [
    "BaseRepository",
    "OperatorRepository",
    "OpTypeRepository",
    "MachineRepository",
    "MachineDowntimeRepository",
    "OperatorMachineRepository",
    "SupplierRepository",
    "PartRepository",
    "PartOperationRepository",
    "ExternalGroupRepository",
    "BatchRepository",
    "BatchOperationRepository",
    "ScheduleRepository",
    "CalendarRepository",
    "OperatorCalendarRepository",
    "ConfigRepository",
    "SystemConfigRepository",
    "OperationLogRepository",
    "ScheduleHistoryRepository",
    "SystemJobStateRepository",
    "MaterialRepository",
    "BatchMaterialRepository",
]

