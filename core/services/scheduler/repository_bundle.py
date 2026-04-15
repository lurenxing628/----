from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from data.repositories import (
    BatchOperationRepository,
    BatchRepository,
    ExternalGroupRepository,
    MachineRepository,
    OperatorMachineRepository,
    OperatorRepository,
    PartOperationRepository,
    ScheduleHistoryRepository,
    ScheduleRepository,
    SupplierRepository,
)


@dataclass(frozen=True)
class ScheduleRepositoryBundle:
    batch_repo: BatchRepository
    op_repo: BatchOperationRepository
    part_op_repo: PartOperationRepository
    group_repo: ExternalGroupRepository
    machine_repo: MachineRepository
    operator_repo: OperatorRepository
    operator_machine_repo: OperatorMachineRepository
    supplier_repo: SupplierRepository
    schedule_repo: ScheduleRepository
    history_repo: ScheduleHistoryRepository


def build_schedule_repository_bundle(conn: Any, *, logger: Any = None) -> ScheduleRepositoryBundle:
    return ScheduleRepositoryBundle(
        batch_repo=BatchRepository(conn, logger=logger),
        op_repo=BatchOperationRepository(conn, logger=logger),
        part_op_repo=PartOperationRepository(conn, logger=logger),
        group_repo=ExternalGroupRepository(conn, logger=logger),
        machine_repo=MachineRepository(conn, logger=logger),
        operator_repo=OperatorRepository(conn, logger=logger),
        operator_machine_repo=OperatorMachineRepository(conn, logger=logger),
        supplier_repo=SupplierRepository(conn, logger=logger),
        schedule_repo=ScheduleRepository(conn, logger=logger),
        history_repo=ScheduleHistoryRepository(conn, logger=logger),
    )
