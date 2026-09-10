"""Caller-transaction schema contracts: no repair, upgrade, implicit commit or writes on read."""

import sqlite3

import pytest

from core.infrastructure.workbench_run_schema import (
    RUN_TABLES,
    install_workbench_run_schema,
    workbench_run_contract_issues,
    workbench_run_objects,
)
from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.test_execution_ledger_support import all_rows
from tests.workbench.test_run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.test_run_jobs_support import service


def test_installer_requires_transaction_and_existing_install_is_unchanged(job_case):
    conn = job_case.conn
    before = all_rows(conn)
    with pytest.raises(RuntimeError, match="transaction"):
        install_workbench_run_schema(conn)
    conn.execute("BEGIN IMMEDIATE")
    install_workbench_run_schema(conn)
    assert conn.in_transaction
    conn.rollback()
    assert all_rows(conn) == before


def test_select_only_contract_never_repairs_partial_schema(job_case):
    conn = job_case.conn
    conn.execute("DROP INDEX idx_wb_run_state")
    conn.commit()
    seen = []
    conn.set_trace_callback(seen.append)
    assert workbench_run_contract_issues(conn) == ["missing_run_schema:idx_wb_run_state"]
    conn.set_trace_callback(None)
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in seen)
    before = all_rows(conn)
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(RuntimeError, match="partial"):
        install_workbench_run_schema(conn)
    conn.rollback()
    with pytest.raises(WorkbenchCommandRejected):
        service(conn).lookup("run-request-00000001")
    assert all_rows(conn) == before


def test_new_install_is_fully_rolled_back_on_caller_rollback(job_case):
    conn = job_case.conn
    for name in reversed(workbench_run_objects()):
        kind = conn.execute("SELECT type FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
        conn.execute(f'DROP {kind.upper()} "{name}"')
    conn.commit()
    before = list(conn.execute("SELECT name,sql FROM sqlite_master ORDER BY name"))
    conn.execute("BEGIN IMMEDIATE")
    install_workbench_run_schema(conn)
    assert workbench_run_contract_issues(conn) == []
    conn.rollback()
    assert [tuple(row) for row in conn.execute("SELECT name,sql FROM sqlite_master ORDER BY name")] == [tuple(row) for row in before]


def test_lost_whole_ledger_with_admission_receipt_is_not_recreated(job_case):
    case = job_case
    case.accept()
    case.conn.execute("PRAGMA foreign_keys=OFF")
    for name in reversed(workbench_run_objects()):
        kind = case.conn.execute("SELECT type FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
        case.conn.execute(f'DROP {kind.upper()} "{name}"')
    case.conn.commit()
    case.conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(RuntimeError, match="admissions remain"):
        install_workbench_run_schema(case.conn)
    case.conn.rollback()
    assert not set(RUN_TABLES) & {row[0] for row in case.conn.execute("SELECT name FROM sqlite_master")}


def test_admission_is_immutable_and_permanent(job_case):
    case = job_case
    case.accept()
    for sql in ("DELETE FROM WorkbenchRunJobs", "UPDATE WorkbenchRunJobs SET normalized_input_json='{}'",
                "UPDATE WorkbenchRunJobs SET state='complete'"):
        with pytest.raises(sqlite3.IntegrityError):
            case.conn.execute(sql)
        case.conn.rollback()


def test_missing_schema_query_does_not_install(mem_conn):
    changes = mem_conn.total_changes
    seen = []
    mem_conn.set_trace_callback(seen.append)
    assert len(workbench_run_contract_issues(mem_conn)) == len(workbench_run_objects())
    assert changes == mem_conn.total_changes == 0
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in seen)
