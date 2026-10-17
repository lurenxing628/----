"""Single and imported permissions apply one final write per changed relationship."""

from collections import Counter

import pytest
from flask import Blueprint, Flask, g

from core.infrastructure.transaction import TransactionManager
from core.models import OperatorMachine
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.personnel.operator_machine_service import OperatorMachineService
from core.services.workbench.resource.operator_machine_permissions import WorkbenchOperatorMachinePermissions
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from core.services.workbench.resource.relation_files.files import WorkbenchRelationFileService
from core.services.workbench.resource.states import WorkbenchResourceStateService
from data.repositories.operator_machine_repo import OperatorMachineRepository
from tests.workbench.identity_metadata_support import insert_row
from tests.workbench.resource_entity_support import identity_for, resource_database  # noqa: F401
from tests.workbench.resource_file_support import file_bytes
from web.routes.workbench.operator_machine_permissions import register_operator_machine_routes
from web.routes.workbench.write_context import issue_write_context


def _machines(conn):
    for code in ("M2", "M3"):
        insert_row(conn, "Machines", {"machine_id": code, "name": code, "op_type_id": "OT1"})
    conn.commit()


def _rows(conn):
    return [tuple(row) for row in conn.execute(
        "SELECT machine_id,skill_level,is_primary FROM OperatorMachine WHERE operator_id='O1' ORDER BY machine_id")]


def _writes(monkeypatch):
    written = []
    update, add, remove = OperatorMachineRepository.update_fields, OperatorMachineRepository.add, OperatorMachineRepository.remove

    def tracked_update(self, operator, machine, **fields):
        written.append((operator, machine, "update"))
        return update(self, operator, machine, **fields)

    def tracked_add(self, operator, machine, **fields):
        written.append((operator, machine, "add"))
        return add(self, operator, machine, **fields)

    def tracked_remove(self, operator, machine):
        written.append((operator, machine, "remove"))
        return remove(self, operator, machine)

    monkeypatch.setattr(OperatorMachineRepository, "update_fields", tracked_update)
    monkeypatch.setattr(OperatorMachineRepository, "add", tracked_add)
    monkeypatch.setattr(OperatorMachineRepository, "remove", tracked_remove)
    return written


def test_public_single_and_batch_apply_keep_last_written_primary(resource_conn, monkeypatch):
    conn = resource_conn
    _machines(conn)
    service = OperatorMachineService(conn)
    written = _writes(monkeypatch)
    added = service.add_link("O1", "M2", skill_level="熟练", is_primary="是")
    assert added.id is not None and added.skill_level == "expert"
    assert _rows(conn) == [("M1", "expert", "no"), ("M2", "expert", "yes")]
    assert Counter(written) == Counter([("O1", "M1", "update"), ("O1", "M2", "add")])
    written.clear()
    service.update_link_fields("O1", "M2", skill_level="expert", is_primary="yes")
    assert written == []

    with TransactionManager(conn).transaction():
        current = service.repo.list_simple_rows_for_operators(["O1"])
        changes = service.prepare_changes(current, [OperatorMachine(None, "O1", "M1", "normal", "yes"),
                                                     OperatorMachine(None, "O1", "M3", "expert", "yes")])
        service.apply_changes(changes)
    assert _rows(conn) == [("M1", "normal", "no"), ("M2", "expert", "no"), ("M3", "expert", "yes")]
    assert len(written) == 3 and len(set(written)) == 3


def test_permission_replacement_reuses_capture_and_rejects_stale_before_writing(resource_conn, monkeypatch):
    conn = resource_conn
    _machines(conn)
    insert_row(conn, "OperatorMachine", {"operator_id": "O1", "machine_id": "M2", "skill_level": "beginner"})
    insert_row(conn, "WorkbenchMachineGroups", {"group_id": "G1", "name": "group", "status": "active"})
    insert_row(conn, "WorkbenchMachineGroupMembers", {"machine_id": "M3", "group_id": "G1"})
    conn.commit()
    ref = identity_for(conn, "operator").ref
    desired = [{"machine_ref": identity_for(conn, "machine", code).ref, "skill_level": skill, "is_primary": primary}
               for code, skill, primary in (("M2", "expert", "no"), ("M3", "normal", "yes"))]
    reader = WorkbenchResourceQueryService(conn, "operator")
    service = WorkbenchOperatorMachinePermissions(conn)
    with reader.read_snapshot():
        preparation = reader.preparation()
        preparation.state("operator", "O1")
        preview = service.preview(ref, desired, preparation=preparation)
    written = _writes(monkeypatch)
    sql = []
    conn.set_trace_callback(sql.append)
    with TransactionManager(conn).transaction():
        result = service.confirm(preview)
    conn.set_trace_callback(None)
    assert result.result == "committed"
    assert _rows(conn) == [("M2", "expert", "no"), ("M3", "normal", "yes")]
    assert Counter(written) == Counter([("O1", "M1", "remove"), ("O1", "M2", "update"), ("O1", "M3", "add")])
    assert sum(statement.startswith("SELECT * FROM OperatorMachine WHERE operator_id IN") for statement in sql) == 1
    assert not any(statement == "SELECT * FROM OperatorMachine ORDER BY operator_id,machine_id" for statement in sql)

    preview = service.preview(ref, desired)
    conn.execute("UPDATE Machines SET name='changed' WHERE machine_id='M3'")
    conn.commit()
    written.clear()
    with TransactionManager(conn).transaction(), pytest.raises(WorkbenchCommandRejected) as exc:
        service.confirm(preview)
    assert exc.value.code == "stale_write" and written == []


def test_relation_import_applies_implicit_primary_change_once_and_keeps_untouched_rows(resource_conn, monkeypatch):
    conn = resource_conn
    _machines(conn)
    insert_row(conn, "OperatorMachine", {"operator_id": "O1", "machine_id": "M2", "skill_level": "beginner"})
    conn.commit()
    service = WorkbenchRelationFileService(conn, "operator_machine")
    content = file_bytes([("O1", "M1", "", ""), ("O1", "M2", "熟练", ""), ("O1", "M3", "普通", "是")],
                         headers=("工号", "设备编号", "技能等级", "主操设备"))
    preview = service.preview_import(content, file_format="csv")
    assert [row["result"] for row in preview.as_dict()["rows"]] == ["update", "update", "new"]
    written = _writes(monkeypatch)
    sql = []
    conn.set_trace_callback(sql.append)
    with TransactionManager(conn).transaction():
        service.confirm_import(preview, content, file_format="csv")
    conn.set_trace_callback(None)
    assert _rows(conn) == [("M1", "expert", "no"), ("M2", "expert", "no"), ("M3", "normal", "yes")]
    assert len(written) == 3 and len(set(written)) == 3
    assert sum(statement.startswith("SELECT * FROM OperatorMachine WHERE operator_id IN") for statement in sql) == 1
    assert not any(statement == "SELECT * FROM OperatorMachine ORDER BY operator_id,machine_id" for statement in sql)

    # An imported no-op preserves historical aliases and even multiple legacy primaries.
    conn.execute("UPDATE OperatorMachine SET skill_level='skilled',is_primary='是' WHERE machine_id='M1'")
    conn.commit()
    content = file_bytes([("O1", "M1", "熟练", "是"), ("O1", "M3", "普通", "是")],
                         headers=("工号", "设备编号", "技能等级", "主操设备"))
    preview = service.preview_import(content, file_format="csv")
    written.clear()
    with TransactionManager(conn).transaction():
        service.confirm_import(preview, content, file_format="csv")
    assert written == [] and _rows(conn)[0] == ("M1", "skilled", "是")


def test_permission_routes_accept_existing_write_context_and_replay_receipt(resource_conn):
    conn = resource_conn
    _machines(conn)
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="operator-permission-fixture")
    bp = Blueprint("operator_permissions_test", __name__)
    register_operator_machine_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def isolated_connection():
        g.db = conn

    identity = identity_for(conn, "operator")
    with app.app_context(), TransactionManager(conn).transaction():
        state = WorkbenchResourceStateService(conn).snapshot(identity)
        context = issue_write_context(identity.ref, ["operator.update"], state)
    path = "/api/workbench/v1/entities/operator/" + identity.ref + "/machine-permissions/"
    client = app.test_client()
    response = client.post(path + "preview", json={"write_token": context["write_token"], "machine_permissions": [
        {"machine_ref": identity_for(conn, "machine", "M2").ref, "skill_level": "expert", "is_primary": "yes"}]})
    assert response.status_code == 200, response.get_json()
    preview = response.get_json()["data"]
    body = {"request_key": "operator-permission-0001", "write_token": preview["write_context"]["write_token"],
            "input": {"preview_ref": preview["preview_ref"]}}
    response = client.post(path + "confirm", json=body)
    assert response.status_code == 200 and response.get_json()["result"] == "committed", response.get_json()
    assert _rows(conn) == [("M2", "expert", "yes")]
    response = client.post(path + "confirm", json=body)
    assert response.status_code == 200 and response.get_json()["replayed"] is True
