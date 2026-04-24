from __future__ import annotations

from functools import cached_property
from typing import Any, Callable

from core.services.common.excel_import_executor import execute_preview_rows_transactional
from core.services.common.excel_service import ExcelService
from core.services.equipment import MachineService
from core.services.material import BatchMaterialService, MaterialService
from core.services.personnel import OperatorService
from core.services.personnel.operator_machine_query_service import OperatorMachineQueryService
from core.services.process import PartService, SupplierService
from core.services.process.part_operation_query_service import PartOperationQueryService
from core.services.scheduler import (
    BatchService,
    CalendarService,
    ConfigService,
    GanttService,
    ResourceDispatchService,
    ScheduleService,
)
from core.services.scheduler.schedule_history_query_service import ScheduleHistoryQueryService
from core.services.system import OperationLogService, SystemConfigService, SystemJobStateQueryService

REQUEST_SERVICES_PUBLIC_ATTRS = (
    "schedule_service",
    "batch_service",
    "config_service",
    "calendar_service",
    "schedule_history_query_service",
    "machine_service",
    "operator_service",
    "supplier_service",
    "operator_machine_query_service",
    "material_service",
    "batch_material_service",
    "gantt_service",
    "resource_dispatch_service",
    "part_service",
    "part_operation_query_service",
    "excel_service",
    "system_config_service",
    "system_job_state_query_service",
    "operation_log_service",
)


class RequestServices:
    def __init__(
        self,
        *,
        db: Any,
        app_logger: Any,
        op_logger: Any,
        get_excel_backend: Callable[[], Any],
    ) -> None:
        self._db = db
        self._app_logger = app_logger
        self._op_logger = op_logger
        self._get_excel_backend = get_excel_backend

    def _construct(self, attr_name: str, factory: Callable[[], Any]) -> Any:
        try:
            return factory()
        except AttributeError as exc:
            raise RuntimeError(f"RequestServices.{attr_name} 构造失败：{exc}") from exc

    @cached_property
    def schedule_service(self) -> ScheduleService:
        return self._construct(
            "schedule_service",
            lambda: ScheduleService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def batch_service(self) -> BatchService:
        return self._construct(
            "batch_service",
            lambda: BatchService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def config_service(self) -> ConfigService:
        return self._construct(
            "config_service",
            lambda: ConfigService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def calendar_service(self) -> CalendarService:
        return self._construct(
            "calendar_service",
            lambda: CalendarService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def schedule_history_query_service(self) -> ScheduleHistoryQueryService:
        return self._construct(
            "schedule_history_query_service",
            lambda: ScheduleHistoryQueryService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def machine_service(self) -> MachineService:
        return self._construct(
            "machine_service",
            lambda: MachineService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def operator_service(self) -> OperatorService:
        return self._construct(
            "operator_service",
            lambda: OperatorService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def supplier_service(self) -> SupplierService:
        return self._construct(
            "supplier_service",
            lambda: SupplierService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def operator_machine_query_service(self) -> OperatorMachineQueryService:
        return self._construct(
            "operator_machine_query_service",
            lambda: OperatorMachineQueryService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def material_service(self) -> MaterialService:
        return self._construct(
            "material_service",
            lambda: MaterialService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def batch_material_service(self) -> BatchMaterialService:
        return self._construct(
            "batch_material_service",
            lambda: BatchMaterialService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def gantt_service(self) -> GanttService:
        return self._construct(
            "gantt_service",
            lambda: GanttService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def resource_dispatch_service(self) -> ResourceDispatchService:
        return self._construct(
            "resource_dispatch_service",
            lambda: ResourceDispatchService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def part_service(self) -> PartService:
        return self._construct(
            "part_service",
            lambda: PartService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def part_operation_query_service(self) -> PartOperationQueryService:
        return self._construct(
            "part_operation_query_service",
            lambda: PartOperationQueryService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def excel_service(self) -> ExcelService:
        return self._construct(
            "excel_service",
            lambda: ExcelService(
                backend=self._get_excel_backend(),
                logger=self._app_logger,
                op_logger=self._op_logger,
            ),
        )

    @cached_property
    def system_config_service(self) -> SystemConfigService:
        return self._construct(
            "system_config_service",
            lambda: SystemConfigService(self._db, logger=self._app_logger),
        )

    @cached_property
    def system_job_state_query_service(self) -> SystemJobStateQueryService:
        return self._construct(
            "system_job_state_query_service",
            lambda: SystemJobStateQueryService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    @cached_property
    def operation_log_service(self) -> OperationLogService:
        return self._construct(
            "operation_log_service",
            lambda: OperationLogService(self._db, logger=self._app_logger, op_logger=self._op_logger),
        )

    def execute_preview_rows_transactional(self, **kwargs: Any) -> Any:
        return execute_preview_rows_transactional(self._db, **kwargs)


__all__ = ["RequestServices", "REQUEST_SERVICES_PUBLIC_ATTRS"]
