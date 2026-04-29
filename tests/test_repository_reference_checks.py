from __future__ import annotations

import sqlite3

import pytest

from data.repositories.machine_repo import MachineRepository
from data.repositories.operator_repo import OperatorRepository
from data.repositories.reference_checks import (
    exists_any_nonblank_reference,
    exists_value_reference,
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE BatchOperations (
            machine_id TEXT,
            operator_id TEXT
        );

        CREATE TABLE Schedule (
            machine_id TEXT,
            operator_id TEXT
        );
        """
    )
    return conn


def test_machine_reference_wrappers_keep_existing_semantics() -> None:
    conn = _conn()
    repo = MachineRepository(conn)

    assert not repo.is_referenced_by_batch_operations("M1")
    assert not repo.is_referenced_by_schedule("M1")
    assert not repo.has_any_batch_operations_machine_reference()
    assert not repo.has_any_schedule_machine_reference()

    conn.execute("INSERT INTO BatchOperations(machine_id) VALUES ('M1')")
    conn.execute("INSERT INTO Schedule(machine_id) VALUES ('M1')")

    assert repo.is_referenced_by_batch_operations("M1")
    assert repo.is_referenced_by_schedule("M1")
    assert repo.has_any_batch_operations_machine_reference()
    assert repo.has_any_schedule_machine_reference()


def test_operator_reference_wrappers_keep_existing_semantics() -> None:
    conn = _conn()
    repo = OperatorRepository(conn)

    assert not repo.is_referenced_by_batch_operations("O1")
    assert not repo.is_referenced_by_schedule("O1")
    assert not repo.has_any_batch_operations_operator_reference()
    assert not repo.has_any_schedule_operator_reference()

    conn.execute("INSERT INTO BatchOperations(operator_id) VALUES ('O1')")
    conn.execute("INSERT INTO Schedule(operator_id) VALUES ('O1')")

    assert repo.is_referenced_by_batch_operations("O1")
    assert repo.is_referenced_by_schedule("O1")
    assert repo.has_any_batch_operations_operator_reference()
    assert repo.has_any_schedule_operator_reference()


def test_nonblank_reference_ignores_null_and_blank_values() -> None:
    conn = _conn()
    machine_repo = MachineRepository(conn)
    operator_repo = OperatorRepository(conn)

    conn.execute("INSERT INTO BatchOperations(machine_id, operator_id) VALUES (NULL, NULL)")
    conn.execute("INSERT INTO BatchOperations(machine_id, operator_id) VALUES ('', '')")
    conn.execute("INSERT INTO BatchOperations(machine_id, operator_id) VALUES ('   ', '   ')")

    assert not machine_repo.has_any_batch_operations_machine_reference()
    assert not operator_repo.has_any_batch_operations_operator_reference()

    conn.execute("INSERT INTO BatchOperations(machine_id, operator_id) VALUES ('M2', 'O2')")

    assert machine_repo.has_any_batch_operations_machine_reference()
    assert operator_repo.has_any_batch_operations_operator_reference()


def test_value_reference_uses_parameter_binding_for_user_values() -> None:
    conn = _conn()
    repo = MachineRepository(conn)
    suspicious_value = "M1' OR 1=1 --"

    conn.execute("INSERT INTO BatchOperations(machine_id) VALUES ('M1')")

    assert not exists_value_reference(
        repo,
        table="BatchOperations",
        column="machine_id",
        value=suspicious_value,
    )


def test_reference_check_rejects_invalid_identifier() -> None:
    conn = _conn()
    repo = MachineRepository(conn)

    with pytest.raises(ValueError):
        exists_any_nonblank_reference(
            repo,
            table="BatchOperations; DROP TABLE Schedule;",
            column="machine_id",
        )

    with pytest.raises(ValueError):
        exists_any_nonblank_reference(
            repo,
            table="BatchOperations",
            column="machine_id) OR 1=1 --",
        )
