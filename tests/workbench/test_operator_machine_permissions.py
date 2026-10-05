"""Real isolated SQLite: explicit permissions, stale previews and atomic rollback."""

import sqlite3
from contextlib import contextmanager
from uuid import uuid4

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.personnel.operator_machine_service import OperatorMachineService
from core.services.personnel.operator_qualification import OperatorQualificationError, OperatorQualificationService
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.operator_machine_permissions import OPERATION, WorkbenchOperatorMachinePermissions
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.identity_metadata_support import insert_row, table_rows
from tests.workbench.operator_qualification_support import (
    auto_attempt,
    build_pool,
    qualification_database,
    register_case,
    seed_protected_plan,
)
from tests.workbench.test_resource_api import BASE, _command, _create, _detail


def _ref(conn, kind, code):
    return WorkbenchIdentityRepository(conn).find_active(kind, code).ref


def _row(ref, skill="normal", primary="no"):
    return {"machine_ref": ref, "skill_level": skill, "is_primary": primary}


def test_editing_existing_primary_writes_its_final_fields_once(qualification_conn, monkeypatch):
    from data.repositories.operator_machine_repo import OperatorMachineRepository
    conn = qualification_conn
    OperatorMachineService(conn).add_link("O1", "M1", is_primary="yes")
    svc = WorkbenchOperatorMachinePermissions(conn)
    person, machine = _ref(conn, "operator", "O1"), _ref(conn, "machine", "M1")
    preview = svc.preview(person, [_row(machine, "expert", "yes")])
    writes, original = [], OperatorMachineRepository.update_fields
    def recorded(self, operator_id, machine_id, **fields):
        writes.append((operator_id, machine_id, fields))
        return original(self, operator_id, machine_id, **fields)
    monkeypatch.setattr(OperatorMachineRepository, "update_fields", recorded)
    _execute(conn, preview)
    assert writes == [("O1", "M1", {"skill_level": "expert", "is_primary": "yes"})]


def test_standalone_primary_update_reads_other_links_after_entering_its_transaction(qualification_conn, tmp_path, monkeypatch):
    conn = sqlite3.connect(str(tmp_path / 'primary-update.db'))
    conn.row_factory = sqlite3.Row
    qualification_conn.backup(conn)
    conn.execute('PRAGMA foreign_keys=ON')
    insert_row(conn, 'Machines', {'machine_id': 'M2', 'name': 'second', 'op_type_id': 'TURN'})
    conn.commit()
    service = OperatorMachineService(conn)
    service.add_link('O1', 'M1')
    service.add_link('O1', 'M2')
    path = conn.execute('PRAGMA database_list').fetchone()[2]
    other = sqlite3.connect(path)
    original = service.tx_manager.transaction

    @contextmanager
    def transaction(**kwargs):
        # A real second writer commits immediately before the command opens its transaction.
        other.execute("UPDATE OperatorMachine SET is_primary='yes' WHERE operator_id='O1' AND machine_id='M2'")
        other.commit()
        with original(**kwargs):
            yield

    try:
        monkeypatch.setattr(service.tx_manager, 'transaction', transaction)
        service.update_link_fields('O1', 'M1', skill_level='expert', is_primary='yes', preserve_unchanged=True)
        rows = {row['machine_id']: row['is_primary'] for row in conn.execute(
            "SELECT machine_id,is_primary FROM OperatorMachine WHERE operator_id='O1'")}
        assert rows == {'M1': 'yes', 'M2': 'no'}
    finally:
        other.close()
        conn.close()


def _execute(conn, preview, service=None, key=None):
    body = preview.as_dict()
    return WorkbenchCommandService(conn).execute(
        request_key=key or "permissions-" + uuid4().hex, action=OPERATION,
        context_ref=body["request"]["operator_ref"], normalized_input={"preview": preview.digest},
        guard=lambda: preview, mutate=lambda current: (service or WorkbenchOperatorMachinePermissions(conn)).confirm(current))


def test_skill_then_permission_enters_existing_scheduler_pool_and_removal_excludes_it(qualification_conn):
    conn = qualification_conn
    register_case(conn, False, 1, ["TURN"])
    svc = WorkbenchOperatorMachinePermissions(conn)
    person, machine = _ref(conn, "operator", "O1"), _ref(conn, "machine", "M1")
    assert build_pool(conn)["operators_by_machine"].get("M1", []) == []
    with pytest.raises(OperatorQualificationError):
        OperatorQualificationService(conn).require(operator_id="O1", op_type_id="TURN", machine_id="M1")
    preview = svc.preview(person, [_row(machine, "expert", "yes")])
    assert not table_rows(conn, "OperatorMachine")  # preview is a read
    assert _execute(conn, preview)["result"] == "committed"
    OperatorQualificationService(conn).require(operator_id="O1", op_type_id="TURN", machine_id="M1")
    assert build_pool(conn)["operators_by_machine"]["M1"]
    attempt = auto_attempt(conn, build_pool(conn))
    assert (attempt.machine_id, attempt.operator_id) == ("M1", "O1")
    skills_before = table_rows(conn, "OperatorSkill")
    _execute(conn, svc.preview(person, []))
    assert table_rows(conn, "OperatorSkill") == skills_before
    assert not table_rows(conn, "OperatorMachine")
    with pytest.raises(OperatorQualificationError):
        OperatorQualificationService(conn).require(operator_id="O1", op_type_id="TURN", machine_id="M1")


def test_raw_unchanged_link_fields_and_creation_time_survive_other_permission_edits(qualification_conn):
    conn = qualification_conn
    insert_row(conn, "Machines", {"machine_id": "M2", "name": "second", "op_type_id": "TURN"})
    insert_row(conn, "OperatorMachine", {"operator_id": "O1", "machine_id": "M1", "skill_level": "旧等级",
                                          "is_primary": "非主操", "created_at": "2001-02-03 04:05:06"})
    conn.commit()
    svc = WorkbenchOperatorMachinePermissions(conn)
    person, first, second = _ref(conn, "operator", "O1"), _ref(conn, "machine", "M1"), _ref(conn, "machine", "M2")
    before = dict(conn.execute("SELECT * FROM OperatorMachine WHERE machine_id='M1'").fetchone())
    _execute(conn, svc.preview(person, [_row(first, "旧等级", "非主操"), _row(second, "expert", "yes")]))
    assert dict(conn.execute("SELECT * FROM OperatorMachine WHERE machine_id='M1'").fetchone()) == before
    _execute(conn, svc.preview(person, [_row(first, "旧等级", "yes"), _row(second, "expert", "no")]))
    now = dict(conn.execute("SELECT * FROM OperatorMachine WHERE machine_id='M1'").fetchone())
    assert now == {**before, "is_primary": "yes"}
    _execute(conn, svc.preview(person, [_row(first, "beginner", "yes"), _row(second, "expert", "no")]))
    assert dict(conn.execute("SELECT * FROM OperatorMachine WHERE machine_id='M1'").fetchone()) == {**before, "is_primary": "yes", "skill_level": "beginner"}


def test_preview_rechecks_machine_and_full_permission_set(qualification_conn):
    conn = qualification_conn
    svc = WorkbenchOperatorMachinePermissions(conn)
    person, machine = _ref(conn, "operator", "O1"), _ref(conn, "machine", "M1")
    preview = svc.preview(person, [_row(machine)])
    conn.execute("UPDATE Machines SET name='Changed' WHERE machine_id='M1'")
    conn.commit()
    with pytest.raises(WorkbenchCommandRejected, match="预检"):
        _execute(conn, preview)
    assert not table_rows(conn, "OperatorMachine")
    preview = svc.preview(person, [])
    OperatorMachineService(conn).add_link("O1", "M1")
    with pytest.raises(WorkbenchCommandRejected):
        _execute(conn, preview)
    assert len(table_rows(conn, "OperatorMachine")) == 1
    assert not table_rows(conn, "WorkbenchCommandReceipts")


def test_failure_after_unlink_rolls_back_all_permissions_and_receipt(qualification_conn, monkeypatch):
    conn = qualification_conn
    register_case(conn, True, 1, ["TURN"])
    insert_row(conn, "Machines", {"machine_id": "M2", "name": "second", "op_type_id": "TURN"})
    conn.commit()
    svc = WorkbenchOperatorMachinePermissions(conn)
    preview = svc.preview(_ref(conn, "operator", "O1"), [_row(_ref(conn, "machine", "M2"))])
    before = table_rows(conn, "OperatorMachine")
    def fail(*args, **kwargs):
        assert not table_rows(conn, "OperatorMachine")
        raise RuntimeError("injected after unlink")
    monkeypatch.setattr(svc.domain, "add_link", fail)
    with pytest.raises(WorkbenchCommandUncertain):
        _execute(conn, preview, svc)
    assert table_rows(conn, "OperatorMachine") == before
    assert not table_rows(conn, "WorkbenchCommandReceipts")


def test_permission_removal_does_not_rewrite_saved_plan_or_started_operation(qualification_conn):
    conn = qualification_conn
    seed_protected_plan(conn, "processing")
    protected = {name: table_rows(conn, name) for name in ("Schedule", "ScheduleHistory", "BatchOperations", "OperationExecutionEvents")}
    svc = WorkbenchOperatorMachinePermissions(conn)
    _execute(conn, svc.preview(_ref(conn, "operator", "O1"), []))
    assert {name: table_rows(conn, name) for name in protected} == protected
    with pytest.raises(OperatorQualificationError):
        OperatorQualificationService(conn).require(operator_id="O1", op_type_id="TURN", machine_id="M1")


def _api_setup(client):
    skill, _ = _create(client, "op_type", "PERM-T", fields={"category": "internal"})
    person, _ = _create(client, "operator", "PERM-O", relationships={"skill_refs": [skill]})
    first, _ = _create(client, "machine", "PERM-M1", relationships={"op_type_ref": skill})
    second, _ = _create(client, "machine", "PERM-M2", relationships={"op_type_ref": skill})
    return person, first, second


def _preview(client, person, rows, token=None):
    return client.post(BASE + "operator/" + person + "/machine-permissions/preview", json={
        "machine_permissions": rows, "write_token": token or _detail(client, "operator", person)["write_context"]["write_token"]})


def test_api_roundtrip_changes_preserves_skills_and_replays_without_preview_store(app_client):
    person, first, second = _api_setup(app_client)
    before = _detail(app_client, "operator", person)
    response = _preview(app_client, person, [_row(first, "expert", "yes"), _row(second)])
    assert response.status_code == 200, response.get_data(as_text=True)
    preview = response.get_json()["data"]
    assert preview["write_context"]["write_token"] == preview["preview_ref"]
    assert preview["write_context"]["expires_at"] == preview["expires_at"]
    assert preview["summary"]["new"] == 2
    assert _detail(app_client, "operator", person)["relationships"]["machine_permissions"] == []
    body = {"request_key": "permissions-api-000001", "write_token": preview["write_context"]["write_token"],
            "input": {"preview_ref": preview["preview_ref"]}}
    url = BASE + "operator/" + person + "/machine-permissions/confirm"
    another = _preview(app_client, person, [_row(first)]).get_json()["data"]
    crossed = app_client.post(url, json={**body, "write_token": another["write_context"]["write_token"]})
    assert crossed.status_code == 409 and crossed.get_json()["error"]["code"] == "stale_write"
    assert _detail(app_client, "operator", person)["relationships"]["machine_permissions"] == []
    assert app_client.post(url, json=body).status_code == 200
    after = _detail(app_client, "operator", person)
    assert len(after["relationships"]["machine_permissions"]) == 2
    assert after["relationships"]["skill_refs"] == before["relationships"]["skill_refs"]
    assert _command(app_client, "operator", person, "update", {"label": "New name"}, key="permissions-name-000001").status_code == 200
    assert _detail(app_client, "operator", person)["relationships"]["machine_permissions"] == after["relationships"]["machine_permissions"]
    app_client.application.extensions["workbench_resource_action_contexts_v1"].clear()
    replay = app_client.post(url, json=body)
    assert replay.status_code == 200 and replay.get_json()["replayed"] is True


@pytest.mark.parametrize("invalid", ["duplicate", "two-primary", "unknown-skill", "boolean-primary"])
def test_api_rejects_invalid_new_values_and_ambiguous_sets(app_client, invalid):
    person, first, second = _api_setup(app_client)
    rows = {"duplicate": [_row(first), _row(first)], "two-primary": [_row(first, primary="yes"), _row(second, primary="yes")],
            "unknown-skill": [_row(first, "unknown")], "boolean-primary": [_row(first, primary=True)]}[invalid]
    response = _preview(app_client, person, rows)
    assert response.status_code == 422, response.get_data(as_text=True)
    assert response.get_json()["committed"] is False
    assert _detail(app_client, "operator", person)["relationships"]["machine_permissions"] == []


def test_stale_detail_token_cannot_remove_new_hidden_link(app_client):
    person, first, _ = _api_setup(app_client)
    token = _detail(app_client, "operator", person)["write_context"]["write_token"]
    with sqlite3.connect(app_client.application.config["DATABASE_PATH"]) as conn:
        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('PERM-O','PERM-M1')")
    response = _preview(app_client, person, [], token)
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "stale_write"
    assert _detail(app_client, "operator", person)["relationships"]["machine_permissions"][0]["machine_ref"] == first
