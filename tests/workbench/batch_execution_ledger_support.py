"""AP fixtures use only isolated SQLite and real ledger commands."""

import pytest

from core.infrastructure.migration_state import get_schema_version, set_schema_version
from core.infrastructure.workbench_execution_ledger_schema import install_execution_ledger
from core.infrastructure.workbench_execution_void_schema import install_execution_voids
from tests.workbench.batch_support import batch_database, create_batch_client, detail, ref_for
from tests.workbench.execution_ledger_support import LedgerCase
from tests.workbench.plan_identity_support import load_v24_schema

_batch_fixture = batch_database


@pytest.fixture(name="batch_ledger")
def batch_ledger_fixture(batch_client):
    client = batch_client
    conn = client.batch_conn
    conn.execute("BEGIN")
    install_execution_ledger(conn)
    install_execution_voids(conn)
    conn.commit()
    return build_case(client)


@pytest.fixture(name="legacy_batch_ledger")
def legacy_batch_ledger(mem_conn):
    conn = load_v24_schema(mem_conn)
    set_schema_version(conn, 24)
    conn.commit()
    case = build_case(create_batch_client(conn))
    assert get_schema_version(conn) == 24
    return case


def build_case(client):
    conn = client.batch_conn
    case = LedgerCase(conn)
    case.op_id = conn.execute("SELECT id FROM BatchOperations WHERE batch_id='FREE-001'").fetchone()[0]
    case.plan(7, [case.op_id])
    case.client = client
    case.batch_ref = ref_for(client)
    case.operation_ref = detail(client)["data"]["operations"][0]["operation_ref"]
    return case


def report(case, quantity=2, **patch):
    return case.command("create", case.task(7, case.op_id), case.values(quantity, **patch))


def remove_plan_rows(case):
    case.conn.execute("DELETE FROM Schedule WHERE op_id=?", (case.op_id,))
    case.conn.commit()
    assert case.conn.execute("SELECT status FROM BatchOperations WHERE id=?", (case.op_id,)).fetchone()[0] == "pending"
