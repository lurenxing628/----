"""Independent WAL connections prove a coherent read and stale-write rejection."""

import sqlite3

import pytest

from core.infrastructure.errors import AppError
from core.services.execution.ledger_reader import ExecutionLedgerReader
from core.services.scheduler.execution_fact_provider import ExecutionFactProvider
from core.services.scheduler.execution_snapshot import build_execution_snapshot
from core.services.scheduler.run.schedule_execution_persistence_guard import _validate_execution_snapshot
from tests.workbench.execution_ledger_support import LedgerCase
from tests.workbench.scheduler_execution_ledger_support import PLAN_FIELDS, plan_rows, read_facts, read_snapshot
from tests.workbench.scheduler_execution_ledger_support import ledger_case as ledger_fixture


def test_report_changes_between_preflight_and_persist_are_stale(ledger_case):
    case = ledger_case
    case.install()
    case.conn.execute("PRAGMA journal_mode=WAL")
    facts = read_facts(case.conn)
    snapshot = read_snapshot(case.conn)
    path = case.conn.execute("PRAGMA database_list").fetchone()[2]
    writer_conn = sqlite3.connect(path)
    writer_conn.row_factory = sqlite3.Row
    try:
        writer = LedgerCase(writer_conn)
        writer.command("create", writer.task(1, case.op_id), writer.values(4))
    finally:
        writer_conn.close()
    with pytest.raises(AppError) as error:
        _validate_execution_snapshot(case, expected_revision=snapshot.revision,
                                     expected_op_ids=snapshot.op_ids, execution_facts=facts)
    assert error.value.details["reason"] == "execution_state_changed"


def test_snapshot_load_has_one_coherent_sqlite_read_even_when_writer_commits(ledger_case, monkeypatch):
    case = ledger_case
    case.install()
    case.conn.execute("PRAGMA journal_mode=WAL")
    before = read_snapshot(case.conn)
    path = case.conn.execute("PRAGMA database_list").fetchone()[2]
    writer_conn = sqlite3.connect(path)
    writer_conn.row_factory = sqlite3.Row
    writer = LedgerCase(writer_conn)
    load = ExecutionLedgerReader.load
    called = []

    def inject(self, *args, **kwargs):
        if self.conn is case.conn and not called:
            called.append(True)
            writer.command("create", writer.task(1, case.op_id), writer.values(4))
        return load(self, *args, **kwargs)

    monkeypatch.setattr(ExecutionLedgerReader, "load", inject)
    try:
        during = read_snapshot(case.conn)
        after = read_snapshot(case.conn)
    finally:
        writer_conn.close()
    assert called == [True]
    assert during.revision == before.revision and after.revision != before.revision


def test_real_resource_identity_changes_are_in_snapshot(ledger_case):
    case = ledger_case
    case.install()
    case.command("create", case.task(1, case.op_id), case.values(10))
    before = read_snapshot(case.conn)
    case.conn.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE kind='machine' AND entity_key='M1'")
    case.conn.commit()
    fact = read_facts(case.conn)[case.op_id]
    assert "execution_ledger_actual_resource_unavailable" in fact.execution_protection_reasons
    assert read_snapshot(case.conn).revision != before.revision


def test_supplied_projection_view_context_is_not_execution_revision(ledger_case):
    case = ledger_case
    case.install()
    case.command("create", case.task(1, case.op_id), case.values(10))
    current = read_snapshot(case.conn)
    projection = case.ledger.get_task(case.task(1, case.op_id))
    assert projection.comparison_task_ref is not None
    facts = ExecutionFactProvider(case.conn).facts_by_op_id_for_plan_rows(
        plan_rows(case.conn, 1), PLAN_FIELDS, execution_projections=[projection])
    assert build_execution_snapshot(facts, list(facts)).revision == current.revision
