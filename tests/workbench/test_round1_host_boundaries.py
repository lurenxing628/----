"""Round-one host boundaries keep real restore ownership and public behavior."""

import json
import sqlite3
import subprocess
import sys
from contextlib import closing

import pytest

from core.infrastructure.database import get_connection
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_system import query_input
from core.services.system import backup_restore
from tests.workbench.test_system_restore_host_support import BASE
from tests.workbench.test_system_restore_host_support import restore_host as restore_host
from web.bootstrap import workbench_system_restore as host_module
from web.routes import system_backup_actions


def test_legacy_restore_names_are_exact_shared_service_objects():
    assert system_backup_actions.run_backup_restore is backup_restore.run_backup_restore
    assert system_backup_actions.RestoreBackupOutcome is backup_restore.RestoreBackupOutcome


def test_restore_audit_uses_a_fresh_tracked_connection_and_closes_it(restore_host, monkeypatch):
    case = restore_host
    body = case.intent()
    opened, tracked, closed = [], [], []
    connect = host_module.get_connection
    track = host_module.track_workbench_request_connection
    close = host_module.close_workbench_request_connection

    def open_connection(path):
        conn = connect(path)
        opened.append((path, conn))
        return conn

    def track_connection(conn):
        tracked.append(conn)
        return track(conn)

    def close_connection(conn):
        closed.append(conn)
        return close(conn)

    monkeypatch.setattr(host_module, "get_connection", open_connection)
    monkeypatch.setattr(host_module, "track_workbench_request_connection", track_connection)
    monkeypatch.setattr(host_module, "close_workbench_request_connection", close_connection)
    response = case.client.post(BASE + "/backups/restore", json=body, buffered=True)
    assert response.status_code == 200
    operation = response.get_json()["data"]["operation"]
    assert operation["state"] == "succeeded" and operation["audit_persisted"] is True
    assert len(opened) == 1 and opened[0][0] == case.path
    conn = opened[0][1]
    assert tracked == [conn] and closed.count(conn) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
    assert case.gate.status["active"] == 0
    assert case.marker() == "selected"
    with closing(get_connection(case.path)) as check:
        assert check.execute("SELECT COUNT(*) FROM OperationLogs WHERE action='workbench_restore'").fetchone()[0] == 1
    case.assert_locks_held()


def test_failed_restore_audit_does_not_claim_it_was_recorded(restore_host, monkeypatch):
    case = restore_host
    body = case.intent()
    monkeypatch.setattr(host_module, "audit_backup_operation", lambda *args: False)
    response = case.client.post(BASE + "/backups/restore", json=body, buffered=True)
    assert response.status_code == 200
    operation = response.get_json()["data"]["operation"]
    assert operation["state"] == "succeeded" and operation["audit_persisted"] is False
    assert operation["restart_required"] is True and case.marker() == "selected"
    assert case.gate.status["active"] == 0
    with closing(get_connection(case.path)) as check:
        assert check.execute("SELECT COUNT(*) FROM OperationLogs WHERE action='workbench_restore'").fetchone()[0] == 0


def test_restore_host_rejects_another_action_before_opening_a_connection(restore_host, monkeypatch):
    def forbidden(*args):
        raise AssertionError("Invalid action opened a database")
    monkeypatch.setattr(host_module, "get_connection", forbidden)
    with pytest.raises(ValueError, match="different file operation"):
        restore_host.host.audit_restore_result({"action": "delete"})


@pytest.mark.parametrize("kind", ["logs", "backups"])
def test_query_defaults_and_explicit_pagination_remain_exact(kind):
    result = query_input({"query": "中文", "start": "2024-02-29", "end": "2024-03-01",
                          "page": "2", "page_size": "25", "snapshot_ref": "kept-by-transport"}, kind)
    assert result == {"query": "中文", "start": "2024-02-29", "end": "2024-03-01",
                      "page": 2, "page_size": 25, "type": "", "status": "", "level": "", "file": ""}
    assert query_input({}, kind)["page_size"] == 10


@pytest.mark.parametrize("value,status", [({"page": 1}, 400), ({"page": "0"}, 400),
    ({"page_size": "20"}, 400), ({"start": "2023-02-29"}, 422),
    ({"start": "2024-03-01", "end": "2024-02-29"}, 422),
    ({"query": None}, 400), ({"query": "x" * 201}, 400), ({"type": "invented"}, 400),
    ({"extra": "field"}, 400)])
def test_query_rejections_keep_original_status(value, status):
    with pytest.raises(WorkbenchCommandRejected) as caught:
        query_input(value, "logs")
    assert caught.value.code == "invalid_input" and caught.value.status == status


def test_unit_excel_leaf_import_does_not_eagerly_load_the_pipeline():
    script = """
import json, sys
import core.services.process.unit_excel as package
assert not hasattr(package, 'UnitExcelParser')
prefix = 'core.services.process.unit_excel.'
assert not any(prefix + name in sys.modules for name in ('exporter', 'parser', 'template_builder'))
from core.services.process.unit_excel.builder_diagnostics import __name__
assert not any(prefix + name in sys.modules for name in ('exporter', 'template_builder'))
from core.services.process.unit_excel_converter import UnitExcelConverter
from core.services.process.unit_excel.parser import UnitExcelParser
from core.services.process.unit_excel.template_builder import UnitTemplateBuilder
from core.services.process.unit_excel.exporter import UnitTemplateExporter
converter = UnitExcelConverter()
assert isinstance(converter._parser, UnitExcelParser)
assert isinstance(converter._builder, UnitTemplateBuilder)
assert isinstance(converter._exporter, UnitTemplateExporter)
print(json.dumps({'pipeline': 'same concrete implementations'}))
"""
    result = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True,
                            text=True, check=True, timeout=30)
    assert json.loads(result.stdout) == {"pipeline": "same concrete implementations"}


def test_shared_sqlite_snapshots_keep_original_objects_rows_and_schema():
    from tests._support import sqlite_snapshot
    from tests.workbench import identity_metadata_support, process_workflow_support

    assert identity_metadata_support.schema_snapshot is sqlite_snapshot.schema_snapshot
    assert identity_metadata_support.table_rows is sqlite_snapshot.table_rows
    assert process_workflow_support.stored_state is sqlite_snapshot.stored_state
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, value, raw BLOB)")
        conn.executemany("INSERT INTO sample VALUES(?,?,?)", [(1, None, b"\x00\xff"), (2, 0, b""), (3, "0", None)])
        conn.commit()
        before = conn.total_changes
        conn.execute("PRAGMA query_only=ON")
        schema, tables = sqlite_snapshot.stored_state(conn)
        assert tables == {"sample": [(1, None, b"\x00\xff"), (2, 0, b""), (3, "0", None)]}
        assert schema["sample"] == ("table", "sample", "CREATE TABLE sample(id INTEGER PRIMARY KEY, value, raw BLOB)")
        assert conn.total_changes == before and not conn.in_transaction
    finally:
        conn.close()
