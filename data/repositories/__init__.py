"""
数据访问层（Repositories）。

约束：
- V1 不引入 ORM；统一使用 sqlite3 + repository 封装
- 服务层（core/services）应只依赖 repo，不直接写 SQL
"""

from .base_repo import BaseRepository
from .operator_repo import OperatorRepository
from .op_type_repo import OpTypeRepository
from .machine_repo import MachineRepository
from .machine_downtime_repo import MachineDowntimeRepository
from .operator_machine_repo import OperatorMachineRepository
from .supplier_repo import SupplierRepository
from .part_repo import PartRepository
from .part_operation_repo import PartOperationRepository
from .external_group_repo import ExternalGroupRepository
from .batch_repo import BatchRepository
from .batch_operation_repo import BatchOperationRepository
from .schedule_repo import ScheduleRepository
from .calendar_repo import CalendarRepository
from .operator_calendar_repo import OperatorCalendarRepository
from .config_repo import ConfigRepository
from .system_config_repo import SystemConfigRepository
from .operation_log_repo import OperationLogRepository
from .schedule_history_repo import ScheduleHistoryRepository
from .system_job_state_repo import SystemJobStateRepository
from .material_repo import MaterialRepository
from .batch_material_repo import BatchMaterialRepository

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

