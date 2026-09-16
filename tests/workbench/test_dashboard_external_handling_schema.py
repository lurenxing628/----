"""Only explicit v31 helper installation enables handling; v29/v30 stay fixed."""

import pytest

from core.infrastructure.migration_state import ensure_current_schema_contract, get_schema_version
from core.infrastructure.workbench_dashboard_external_schema import contract_issues, install, objects
from core.infrastructure.workbench_dashboard_schema import objects as original_objects
from tests.workbench.dashboard_external_handling_support import external_handling_case as _handling_case  # noqa: F401
from tests.workbench.dashboard_external_handling_support import production_storage
from tests.workbench.dashboard_external_migration_support import external_v30_case as _external_v30_case  # noqa: F401
from tests.workbench.dashboard_external_migration_support import fixed_v30_connection, install_v32_read_guards
from tests.workbench.dashboard_external_support import external_case as _external_case  # noqa: F401
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401
from tests.workbench.dashboard_support import follow


def test_current30_accepts_explicit_extension_without_version_or_original_data_change(tmp_path):
    path = tmp_path / "current30-dt.sqlite"
    conn = fixed_v30_connection(path)
    try:
        assert get_schema_version(conn) == 30
        before = production_storage(conn)
        conn.execute("BEGIN")
        install(conn)
        conn.commit()
        assert get_schema_version(conn) == 30 and not contract_issues(conn)
        ensure_current_schema_contract(conn, schema_version=30)
        assert production_storage(conn) == before
    finally:
        conn.close()


def test_explicit_helper_backfills_only_mapping_and_is_idempotent(external_v30_case):
    case = external_v30_case
    install_v32_read_guards(case.conn)
    ref = case.register()
    assert case.read()[0]["categories"]["external"]["handling_supported"] is False
    before = production_storage(case.conn)
    definitions = {row[0]: row[1] for row in case.conn.execute("SELECT name,sql FROM sqlite_master") if row[0] in original_objects()}
    with pytest.raises(RuntimeError, match="caller's migration transaction"):
        install(case.conn)
    case.conn.execute("BEGIN")
    install(case.conn)
    case.conn.commit()
    item = case.item("external")
    assert item["source"]["outsourcing_ref"] == ref and item["handling"]["status"] == "new"
    assert not contract_issues(case.conn) and production_storage(case.conn) == before
    assert {row[0]: row[1] for row in case.conn.execute("SELECT name,sql FROM sqlite_master") if row[0] in original_objects()} == definitions
    case.conn.execute("BEGIN")
    install(case.conn)
    case.conn.commit()
    assert case.item("external")["item_ref"] == item["item_ref"]
    assert production_storage(case.conn) == before


def test_gets_are_select_only_and_do_not_seed_states(external_handling_case):
    case = external_handling_case
    case.register()
    before = production_storage(case.conn)
    count = case.conn.total_changes
    case.conn.execute("PRAGMA query_only=ON")
    item = case.item("external")
    assert case.history(item["item_ref"]) == []
    assert case.conn.total_changes == count and production_storage(case.conn) == before
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchDashboardExternalStates").fetchone()[0] == 0


def test_partial_helper_is_explicit_unavailable_and_not_repaired(external_handling_case):
    case = external_handling_case
    case.register()
    summary = case.read()[0]["categories"]["external"]
    case.conn.execute("DROP TRIGGER wb_dashboard_external_history_no_update")
    case.conn.commit()
    current = case.read()[0]["categories"]["external"]
    assert current["handling_supported"] is False and current["handling_state"] == "unavailable"
    assert current["handling_count"] is None and current["closed_count"] is None
    for key in ("risk_count", "known_risk_count", "unknown_count", "evaluation_gaps", "overdue_count"):
        assert current[key] == summary[key]
    case.conn.execute("BEGIN")
    with pytest.raises(RuntimeError, match="Cannot install or repair"):
        install(case.conn)
    case.conn.rollback()


def test_lost_extension_with_receipt_is_not_a_fresh_install(external_handling_case):
    case = external_handling_case
    case.register()
    case.command(case.item("external"), follow())
    names = set(objects())
    case.conn.execute("PRAGMA foreign_keys=OFF")
    for kind, name in list(case.conn.execute("SELECT type,name FROM sqlite_master")):
        if name in names and kind != "table":
            case.conn.execute("DROP " + kind.upper() + " " + name)
    for suffix in ("History", "States", "Items"):
        case.conn.execute("DROP TABLE WorkbenchDashboardExternal" + suffix)
    case.conn.commit()
    summary = case.read()[0]["categories"]["external"]
    assert summary["handling_state"] == "unavailable" and summary["handling_count"] is None
    case.conn.execute("BEGIN")
    with pytest.raises(RuntimeError, match="without their original ledger"):
        install(case.conn)
    case.conn.rollback()
