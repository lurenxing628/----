"""Explicit schema hooks preserve original facts, identities and schema version."""

import sqlite3

import pytest

from core.infrastructure.workbench_calibration_adoption_schema import (
    contract_issues as calibration_issues,
)
from core.infrastructure.workbench_calibration_adoption_schema import (
    install as install_calibration,
)
from core.infrastructure.workbench_calibration_adoption_schema import (
    objects as calibration_objects,
)
from core.infrastructure.workbench_dashboard_schema import contract_issues, install, objects
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401
from tests.workbench.dashboard_support import source_rows
from tests.workbench.run_schema_migration_support import snapshot, source_ddl
from tests.workbench.schema29_regression_support import assert_v29_source_maps_only
from tests.workbench.schema29_regression_support import frozen_v28_conn as _frozen_v28_conn  # noqa: F401


def remove_dashboard(conn):
    for name in reversed(objects()):
        kind = conn.execute("SELECT type FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
        conn.execute('DROP ' + kind.upper() + ' "' + name + '"')


def test_hook_idempotent_requires_outer_transaction_no_version_upgrade(dashboard_case):
    case = dashboard_case
    before, version = source_rows(case.conn), case.conn.execute("PRAGMA user_version").fetchone()[0]
    identities = list(case.conn.execute("SELECT * FROM WorkbenchDashboardItems ORDER BY item_ref"))
    with pytest.raises(RuntimeError, match="migration transaction"):
        install(case.conn)
    case.conn.execute("BEGIN")
    install(case.conn)
    assert case.conn.in_transaction and contract_issues(case.conn) == []
    case.conn.commit()
    assert before == source_rows(case.conn)
    assert list(case.conn.execute("SELECT * FROM WorkbenchDashboardItems ORDER BY item_ref")) == identities
    assert case.conn.execute("PRAGMA user_version").fetchone()[0] == version


def test_partial_install_is_rejected_without_repair(dashboard_case):
    conn = dashboard_case.conn
    conn.execute("DROP TRIGGER wb_dashboard_task_insert")
    conn.execute("BEGIN")
    with pytest.raises(RuntimeError, match="partial dashboard"):
        install(conn)
    conn.rollback()
    assert "missing_dashboard_schema:wb_dashboard_task_insert" in contract_issues(conn)


def test_new_install_rollback_and_backfill_only_maps_sources(dashboard_case):
    conn = dashboard_case.conn
    remove_dashboard(conn)
    before = source_rows(conn)
    conn.execute("BEGIN")
    install(conn)
    assert not contract_issues(conn)
    assert conn.execute("SELECT COUNT(*) FROM WorkbenchDashboardStates").fetchone()[0] == 0
    conn.rollback()
    assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='WorkbenchDashboardItems'").fetchone()
    assert before == source_rows(conn)
    conn.execute("BEGIN")
    install(conn)
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM WorkbenchDashboardItems").fetchone()[0] == 4
    assert before == source_rows(conn)


def test_ddl_rejects_wrong_parent_and_illegal_identity_shape(dashboard_case):
    conn = dashboard_case.conn
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO WorkbenchDashboardItems(item_ref,category,batch_ref) VALUES (?,'actual',?)", ("a" * 48, "b" * 48))
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO WorkbenchDashboardItems(item_ref,category,batch_ref) VALUES (?,'material',?)", ("a" * 48, "b" * 48))
    conn.rollback()


@pytest.mark.parametrize("dashboard_first", [True, False])
def test_next_version_hooks_coexist_without_changing_frozen_v28(frozen_v28_conn, dashboard_first, record_property):
    conn = frozen_v28_conn
    conn.commit()
    assert len(calibration_objects()) == 9
    assert not set(calibration_objects()) & set(objects())
    before, version = source_rows(conn), list(conn.execute("SELECT * FROM SchemaVersion"))
    old_rows, old_ddl = snapshot(conn), source_ddl(conn)
    record_property("base_schema_version", conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0])
    installers = (install, install_calibration) if dashboard_first else (install_calibration, install)
    conn.execute("BEGIN IMMEDIATE")
    for installer in installers:
        installer(conn)
    assert contract_issues(conn) == [] and calibration_issues(conn) == []
    conn.rollback()
    assert snapshot(conn) == old_rows and source_ddl(conn) == old_ddl
    assert all(conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone() is None
               for name in tuple(objects()) + tuple(calibration_objects()))
    conn.execute("BEGIN IMMEDIATE")
    for installer in installers:
        installer(conn)
    conn.commit()
    assert list(conn.execute("SELECT * FROM SchemaVersion")) == version
    assert source_rows(conn) == before
    after = snapshot(conn)
    assert {name: after[name] for name in old_rows} == old_rows
    assert [row for row in source_ddl(conn) if row[1] in {old[1] for old in old_ddl}] == old_ddl
    assert_v29_source_maps_only(conn)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert list(conn.execute("PRAGMA foreign_key_check")) == []
