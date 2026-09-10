"""Controlled templates are checked before early return and automatic parsing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.infrastructure.errors import BusinessError
from core.infrastructure.transaction import TransactionManager
from core.services.process.workflow_state import record_confirmation, start_workflow
from core.services.scheduler.batch_template_ops import ensure_template_ops_in_tx, probe_template_ops_readonly
from data.repositories import PartOperationRepository, PartRepository
from tests.workbench.process_workflow_support import confirm_all, stored_state, workflow_database


def _service(conn):
    return SimpleNamespace(conn=conn, part_op_repo=PartOperationRepository(conn), _template_resolver=Mock(), _user_visible_warnings=[])


@pytest.mark.parametrize("stage", (None, "route", "source"))
def test_pending_existing_template_blocked_before_early_return(workflow_conn, stage):
    conn = workflow_conn
    with TransactionManager(conn).transaction():
        start_workflow(conn, "P1")
        if stage:
            record_confirmation(conn, "P1", "route")
        if stage == "source":
            record_confirmation(conn, "P1", "source")
    svc = _service(conn)
    before = stored_state(conn)
    with pytest.raises(BusinessError) as caught:
        with TransactionManager(conn).transaction():
            ensure_template_ops_in_tx(svc, "P1", PartRepository(conn).get("P1"))
    assert caught.value.details["reason"] == "process_workflow_pending"
    svc._template_resolver.assert_not_called()
    assert stored_state(conn) == before


def test_managed_new_route_cannot_be_automatically_resolved(workflow_conn):
    conn = workflow_conn
    conn.execute("DELETE FROM PartOperations WHERE part_no='P1'")
    conn.commit()
    with TransactionManager(conn).transaction():
        start_workflow(conn, "P1")
    svc, part = _service(conn), PartRepository(conn).get("P1")
    before = stored_state(conn)
    probe = probe_template_ops_readonly(svc, "P1", part)
    assert not probe["has_template_ops"] and probe["route_raw"]
    with pytest.raises(BusinessError):
        with TransactionManager(conn).transaction():
            ensure_template_ops_in_tx(svc, "P1", part, probe=probe)
    svc._template_resolver.assert_not_called()
    assert stored_state(conn) == before


@pytest.mark.parametrize("managed", (False, True))
def test_legacy_and_confirmed_managed_use_same_business_template(workflow_conn, managed):
    conn = workflow_conn
    if managed:
        confirm_all(conn)
    svc, before = _service(conn), stored_state(conn)
    with TransactionManager(conn).transaction():
        ops = ensure_template_ops_in_tx(svc, "P1", PartRepository(conn).get("P1"))
    assert len(ops) == 3 and [op.seq for op in ops] == [1, 2, 3]
    svc._template_resolver.assert_not_called()
    assert stored_state(conn) == before


def test_legacy_no_template_retains_automatic_parse_behavior(workflow_conn):
    conn = workflow_conn
    conn.execute("DELETE FROM PartOperations WHERE part_no='P1'")
    conn.commit()
    svc = _service(conn)

    def resolver(*_args, **_kwargs):
        conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name) VALUES('P1',1,'legacy')")
        return SimpleNamespace(warnings=[])

    svc._template_resolver.side_effect = resolver
    with TransactionManager(conn).transaction():
        ops = ensure_template_ops_in_tx(svc, "P1", PartRepository(conn).get("P1"))
    assert len(ops) == 1
    svc._template_resolver.assert_called_once()


def test_old_modification_after_probe_is_rechecked_in_transaction(workflow_conn):
    conn = workflow_conn
    confirm_all(conn)
    svc, part = _service(conn), PartRepository(conn).get("P1")
    probe = probe_template_ops_readonly(svc, "P1", part)
    conn.execute("UPDATE PartOperations SET unit_hours=9 WHERE seq=1")
    conn.commit()
    with pytest.raises(BusinessError):
        with TransactionManager(conn).transaction():
            ensure_template_ops_in_tx(svc, "P1", part, probe=probe)
