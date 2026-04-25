"""
数据访问层（Repositories）。

约束：
- V1 不引入 ORM；统一使用 sqlite3 + repository 封装
- 服务层（core/services）应只依赖 repo，不直接写 SQL
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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
    from .resource_team_repo import ResourceTeamRepository
    from .schedule_history_repo import ScheduleHistoryRepository
    from .schedule_repo import ScheduleRepository
    from .supplier_repo import SupplierRepository
    from .system_config_repo import SystemConfigRepository
    from .system_job_state_repo import SystemJobStateRepository

_EXPORTS = {
    "BaseRepository": ".base_repo",
    "BatchMaterialRepository": ".batch_material_repo",
    "BatchOperationRepository": ".batch_operation_repo",
    "BatchRepository": ".batch_repo",
    "CalendarRepository": ".calendar_repo",
    "ConfigRepository": ".config_repo",
    "ExternalGroupRepository": ".external_group_repo",
    "MachineDowntimeRepository": ".machine_downtime_repo",
    "MachineRepository": ".machine_repo",
    "MaterialRepository": ".material_repo",
    "OpTypeRepository": ".op_type_repo",
    "OperationLogRepository": ".operation_log_repo",
    "OperatorCalendarRepository": ".operator_calendar_repo",
    "OperatorMachineRepository": ".operator_machine_repo",
    "OperatorRepository": ".operator_repo",
    "PartOperationRepository": ".part_operation_repo",
    "PartRepository": ".part_repo",
    "ResourceTeamRepository": ".resource_team_repo",
    "ScheduleHistoryRepository": ".schedule_history_repo",
    "ScheduleRepository": ".schedule_repo",
    "SupplierRepository": ".supplier_repo",
    "SystemConfigRepository": ".system_config_repo",
    "SystemJobStateRepository": ".system_job_state_repo",
}

__all__ = [
    "BaseRepository",
    "BatchMaterialRepository",
    "BatchOperationRepository",
    "BatchRepository",
    "CalendarRepository",
    "ConfigRepository",
    "ExternalGroupRepository",
    "MachineDowntimeRepository",
    "MachineRepository",
    "MaterialRepository",
    "OpTypeRepository",
    "OperationLogRepository",
    "OperatorCalendarRepository",
    "OperatorMachineRepository",
    "OperatorRepository",
    "PartOperationRepository",
    "PartRepository",
    "ResourceTeamRepository",
    "ScheduleHistoryRepository",
    "ScheduleRepository",
    "SupplierRepository",
    "SystemConfigRepository",
    "SystemJobStateRepository",
]


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
