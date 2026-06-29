"""APS fixture loading helpers for folded FJSP benchmark cases."""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Tuple

from tests._support.optimizer_fjsp_dataset import FjspInstance


def machine_id(index: int) -> str:
    return f"MC{int(index):02d}"


def operator_id(index: int) -> str:
    return f"OP{int(index):02d}"


def seed_calendar_24h(conn, *, start_date: date, days: int) -> None:
    from data.repositories import CalendarRepository

    repo = CalendarRepository(conn, logger=None)
    for offset in range(int(days)):
        work_date = start_date + timedelta(days=offset)
        repo.upsert(
            {
                "date": work_date.isoformat(),
                "day_type": "workday",
                "shift_start": "00:00",
                "shift_end": "00:00",
                "shift_hours": 24.0,
                "efficiency": 1.0,
                "allow_normal": "yes",
                "allow_urgent": "yes",
                "remark": "fjsp_benchmark_24h",
            }
        )


def set_schedule_config(conn, *, algo_mode: str, time_budget_seconds: int) -> None:
    from data.repositories import ConfigRepository

    repo = ConfigRepository(conn, logger=None)
    config_values = {
        "algo_mode": str(algo_mode),
        "time_budget_seconds": str(int(time_budget_seconds)),
        "objective": "min_overdue",
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "freeze_window_enabled": "no",
        "freeze_window_days": "0",
        "auto_assign_enabled": "no",
        "ortools_enabled": "no",
    }
    for key, value in config_values.items():
        repo.set(key, value, description=None)


def insert_minimal_entities(
    conn,
    *,
    instance: FjspInstance,
    machine_assignment: List[List[Tuple[int, int]]],
    due_date: str,
) -> List[str]:
    repositories = _repositories(conn)
    _insert_op_type(repositories["op_type"])
    _insert_machines_and_operators(instance, repositories)
    return _insert_jobs(
        instance,
        repositories,
        machine_assignment=machine_assignment,
        due_date=due_date,
    )


def _repositories(conn):
    from data.repositories import (
        BatchOperationRepository,
        BatchRepository,
        MachineRepository,
        OperatorMachineRepository,
        OperatorRepository,
        OpTypeRepository,
        PartRepository,
    )

    return {
        "op_type": OpTypeRepository(conn, logger=None),
        "machine": MachineRepository(conn, logger=None),
        "operator": OperatorRepository(conn, logger=None),
        "operator_machine": OperatorMachineRepository(conn, logger=None),
        "part": PartRepository(conn, logger=None),
        "batch": BatchRepository(conn, logger=None),
        "batch_operation": BatchOperationRepository(conn, logger=None),
    }


def _insert_op_type(op_type_repo) -> None:
    op_type_repo.create(
        {
            "op_type_id": "OT_FJSP",
            "name": "FJSP",
            "category": "internal",
            "default_hours": 0,
            "remark": "benchmark",
        }
    )


def _insert_machines_and_operators(instance: FjspInstance, repositories) -> None:
    machine_repo = repositories["machine"]
    operator_repo = repositories["operator"]
    link_repo = repositories["operator_machine"]
    for index in range(1, int(instance.num_machines) + 1):
        machine_repo.create(_machine_row(index, instance.name))
        operator_repo.create(_operator_row(index, instance.name))
        link_repo.add(operator_id(index), machine_id(index), skill_level="expert", is_primary="yes")


def _machine_row(index: int, instance_name: str):
    return {
        "machine_id": machine_id(index),
        "name": f"FJSP-M{index}",
        "op_type_id": "OT_FJSP",
        "category": "benchmark",
        "status": "active",
        "remark": instance_name,
    }


def _operator_row(index: int, instance_name: str):
    return {
        "operator_id": operator_id(index),
        "name": f"FJSP-O{index}",
        "status": "active",
        "remark": instance_name,
    }


def _insert_jobs(
    instance: FjspInstance,
    repositories,
    *,
    machine_assignment: List[List[Tuple[int, int]]],
    due_date: str,
) -> List[str]:
    batch_ids: List[str] = []
    for job_index, assigned_ops in enumerate(machine_assignment, start=1):
        batch_id = _insert_job_header(instance, repositories, job_index=job_index, due_date=due_date)
        batch_ids.append(batch_id)
        _insert_job_operations(instance, repositories["batch_operation"], job_index=job_index, assigned_ops=assigned_ops)
    return batch_ids


def _insert_job_header(instance: FjspInstance, repositories, *, job_index: int, due_date: str) -> str:
    part_no = f"FJSP-{instance.name}-J{job_index:02d}"
    batch_id = f"B-{instance.name}-J{job_index:02d}"
    repositories["part"].create(
        {
            "part_no": part_no,
            "part_name": part_no,
            "route_raw": "",
            "route_parsed": "yes",
            "remark": instance.name,
        }
    )
    repositories["batch"].create(_batch_row(batch_id=batch_id, part_no=part_no, due_date=due_date))
    return batch_id


def _batch_row(*, batch_id: str, part_no: str, due_date: str):
    return {
        "batch_id": batch_id,
        "part_no": part_no,
        "part_name": part_no,
        "quantity": 1,
        "due_date": due_date,
        "priority": "normal",
        "ready_status": "yes",
        "ready_date": None,
        "status": "pending",
        "remark": "fjsp_benchmark",
    }


def _insert_job_operations(
    instance: FjspInstance,
    operation_repo,
    *,
    job_index: int,
    assigned_ops: List[Tuple[int, int]],
) -> None:
    batch_id = f"B-{instance.name}-J{job_index:02d}"
    for seq, (assigned_machine, duration) in enumerate(assigned_ops, start=1):
        operation_repo.create(_operation_row(instance, job_index, seq, batch_id, assigned_machine, duration))


def _operation_row(
    instance: FjspInstance,
    job_index: int,
    seq: int,
    batch_id: str,
    assigned_machine: int,
    duration: int,
):
    return {
        "op_code": f"OP-{instance.name}-J{job_index:02d}-S{seq:02d}",
        "batch_id": batch_id,
        "piece_id": "1",
        "seq": int(seq),
        "op_type_id": "OT_FJSP",
        "op_type_name": "FJSP",
        "source": "internal",
        "machine_id": machine_id(assigned_machine),
        "operator_id": operator_id(assigned_machine),
        "supplier_id": None,
        "setup_hours": 0.0,
        "unit_hours": float(duration),
        "ext_days": None,
        "status": "pending",
    }
