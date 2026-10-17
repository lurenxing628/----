"""Resource commands capture their targets and relations without whole-table reads."""

import pytest

from core.errors import BusinessError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.resource.operator_machine_permissions import WorkbenchOperatorMachinePermissions
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from data.repositories.base_repo import BaseRepository
from tests.workbench.identity_metadata_support import insert_row
from tests.workbench.resource_entity_support import (
    create_catalog,
    identity_for,
    resource_database,  # noqa: F401
    resource_service,
)


@pytest.mark.parametrize("kind,code", (("op_type", "OT1"), ("machine", "M1"), ("operator", "O1"),
                                      ("supplier", "S1"), ("machine_group", "G1"), ("shift_profile", "SHIFT1")))
def test_scoped_resource_states_preserve_the_complete_existing_write_contract(resource_conn, kind, code):
    conn = resource_conn
    group, shift = create_catalog(conn, "machine_group"), create_catalog(conn, "shift_profile")
    conn.execute("INSERT INTO WorkbenchMachineGroupMembers(machine_id,group_id) VALUES('M1','G1')")
    conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id,skills_declared) VALUES('O1','SHIFT1',1)")
    conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES('M1','OT2')")
    conn.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES('S1','EXT')")
    conn.commit()
    identity = identity_for(conn, kind, code)
    reader = WorkbenchResourceQueryService(conn, kind)
    with TransactionManager(conn).transaction():
        expected = reader.domain.snapshot(identity)
        preparation = reader.preparation(refs=[identity.ref])
        assert preparation.state(kind, code) == expected
        assert preparation.identity(kind, identity.ref) == identity
    assert group.ref and shift.ref


def test_single_update_reads_a_bounded_number_of_rows_and_keeps_name_uniqueness(resource_conn, monkeypatch):
    conn = resource_conn
    conn.executemany("INSERT INTO Machines(machine_id,name) VALUES(?,?)", [(f"UNRELATED-{i}", f"machine {i}") for i in range(401)])
    conn.executemany("INSERT INTO Operators(operator_id,name) VALUES(?,?)", [(f"UNRELATED-{i}", f"operator {i}") for i in range(401)])
    conn.commit()
    identity = identity_for(conn, "machine")
    reads, original = [], BaseRepository.fetchall

    def captured(repo, sql, params=None):
        rows = original(repo, sql, params)
        reads.append((sql, len(rows)))
        return rows

    monkeypatch.setattr(BaseRepository, "fetchall", captured)
    with TransactionManager(conn).transaction():
        outcome = resource_service(conn, "machine").apply("update", {"label": "changed"}, identity)
    assert outcome.result == "committed"
    assert sum(amount for _sql, amount in reads) < 20
    assert not any("FROM Operators" in sql for sql, _amount in reads)
    assert not any("FROM Machines ORDER BY" in sql or "kind IN (" in sql for sql, _amount in reads)
    with TransactionManager(conn).transaction(), pytest.raises(BusinessError):
        resource_service(conn, "op_type").apply("update", {"label": "OT2"}, identity_for(conn, "op_type"))


def test_scoped_preparation_batches_selected_refs_and_rechecks_in_the_next_transaction(resource_conn):
    conn = resource_conn
    conn.executemany("INSERT INTO Machines(machine_id,name) VALUES(?,?)", [(f"SELECTED-{i}", f"machine {i}") for i in range(401)])
    conn.commit()
    refs = [row[0] for row in conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='machine' AND entity_key LIKE 'SELECTED-%'")]
    reader = WorkbenchResourceQueryService(conn, "machine")
    with TransactionManager(conn).transaction():
        preparation = reader.preparation(refs=refs)
        assert len(preparation.facts.raw_lookup("machine", "machine_id")) == 401
        old = preparation.identity("machine", refs[0])
    conn.execute("UPDATE Machines SET name='changed' WHERE machine_id=?", (old.entity_key,))
    conn.commit()
    with TransactionManager(conn).transaction(), pytest.raises(WorkbenchCommandRejected) as error:
        reader.preparation(refs=[old.ref]).current("machine", old)
    assert error.value.code == "stale_write"


def test_selected_relationships_keep_category_and_deleted_identity_rejections(resource_conn):
    conn = resource_conn
    reader = WorkbenchResourceQueryService(conn, "machine")
    identity, external = identity_for(conn, "machine"), identity_for(conn, "op_type", "EXT")
    with TransactionManager(conn).transaction(), pytest.raises(WorkbenchCommandRejected) as error:
        reader.domain.apply("update", {"relationships": {"op_type_refs": [external.ref]}}, identity)
    assert error.value.code == "constraint_conflict"
    conn.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE ref=?", (identity.ref,))
    conn.commit()
    with TransactionManager(conn).transaction(), pytest.raises(WorkbenchCommandRejected) as error:
        reader.domain.apply("update", {"label": "changed"}, identity)
    assert error.value.code == "entity_not_found"


@pytest.mark.parametrize("replace", (False, True))
def test_permission_capture_includes_complete_old_machine_states_before_removal(resource_conn, replace):
    conn = resource_conn
    for code in ("OLD-MAIN", "OLD-CAP", "NEW-TYPE"):
        insert_row(conn, "OpTypes", {"op_type_id": code, "name": code, "category": "internal"})
    conn.execute("UPDATE Machines SET op_type_id='OLD-MAIN' WHERE machine_id='M1'")
    insert_row(conn, "MachineOpTypes", {"machine_id": "M1", "op_type_id": "OLD-CAP"})
    insert_row(conn, "WorkbenchMachineGroups", {"group_id": "OLD-GROUP", "name": "old machine group"})
    insert_row(conn, "WorkbenchMachineGroupMembers", {"machine_id": "M1", "group_id": "OLD-GROUP"})
    insert_row(conn, "Machines", {"machine_id": "M2", "name": "replacement", "op_type_id": "NEW-TYPE"})
    conn.commit()
    operator = identity_for(conn, "operator")
    service = WorkbenchOperatorMachinePermissions(conn)
    reader = WorkbenchResourceQueryService(conn, "operator")
    desired = ([{"machine_ref": identity_for(conn, "machine", "M2").ref, "skill_level": "normal", "is_primary": "yes"}]
               if replace else [])
    with TransactionManager(conn).transaction():
        expected = service.preview(operator.ref, desired, preparation=reader.preparation())
        actual = service.preview(operator.ref, desired)
        assert actual.as_dict() == expected.as_dict()
    with TransactionManager(conn).transaction():
        result = service.confirm(actual)
    assert result.result == "committed"
    assert [tuple(row) for row in conn.execute("SELECT machine_id FROM OperatorMachine WHERE operator_id='O1'")] == (
        [("M2",)] if replace else [])
