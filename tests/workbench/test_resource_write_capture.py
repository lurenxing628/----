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
    identity_for,
    resource_database,  # noqa: F401
)


def test_single_update_reads_a_bounded_number_of_rows_and_keeps_name_uniqueness(resource_conn, monkeypatch):
    conn = resource_conn
    conn.executemany("INSERT INTO Machines(machine_id,name) VALUES(?,?)", [(f"UNRELATED-{i}", f"machine {i}") for i in range(401)])
    conn.executemany("INSERT INTO Operators(operator_id,name) VALUES(?,?)", [(f"UNRELATED-{i}", f"operator {i}") for i in range(401)])
    conn.commit()
    identity = identity_for(conn, "machine")
    assert identity is not None
    reader = WorkbenchResourceQueryService(conn, "machine")
    normalized = reader.domain.normalize_input("update", {"label": "changed"})
    reads, original = [], BaseRepository.fetchall

    def captured(repo, sql, params=None):
        rows = original(repo, sql, params)
        reads.append((sql, len(rows)))
        return rows

    monkeypatch.setattr(BaseRepository, "fetchall", captured)
    with TransactionManager(conn).transaction():
        preparation = reader.preparation_for("update", normalized, ref=identity.ref)
        checked = preparation.state("machine", preparation.current("machine", identity).entity_key)
        outcome = reader.domain.apply_prepared(reader.domain.prepare("update", normalized, checked, preparation))
    assert outcome.result == "committed"
    assert sum(amount for _sql, amount in reads) < 20
    assert not any("FROM Operators" in sql for sql, _amount in reads)
    assert not any("FROM Machines ORDER BY" in sql or "kind IN (" in sql for sql, _amount in reads)
    reads.clear()
    with TransactionManager(conn).transaction():
        assert reader.detail(identity.ref).identity.entity_key == identity.entity_key
    assert sum("FROM WorkbenchEntityRefs WHERE active=1 AND ref IN (" in sql for sql, _amount in reads) == 1
    with TransactionManager(conn).transaction(), pytest.raises(BusinessError):
        reader = WorkbenchResourceQueryService(conn, "op_type")
        identity = identity_for(conn, "op_type")
        assert identity is not None
        normalized = reader.domain.normalize_input("update", {"label": "OT2"})
        preparation = reader.preparation_for("update", normalized, ref=identity.ref)
        checked = preparation.state("op_type", preparation.current("op_type", identity).entity_key)
        reader.domain.apply_prepared(reader.domain.prepare("update", normalized, checked, preparation))


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
    assert identity is not None and external is not None
    normalized = reader.domain.normalize_input("update", {"relationships": {"op_type_refs": [external.ref]}})
    with TransactionManager(conn).transaction(), pytest.raises(WorkbenchCommandRejected) as error:
        preparation = reader.preparation_for("update", normalized, ref=identity.ref)
        checked = preparation.state("machine", preparation.current("machine", identity).entity_key)
        reader.domain.apply_prepared(reader.domain.prepare("update", normalized, checked, preparation))
    assert error.value.code == "constraint_conflict"


def test_unchanged_relations_allow_remark_updates_and_preserve_undeclared_operator_skills(resource_conn):
    conn = resource_conn
    insert_row(conn, "WorkbenchSupplierOpTypes", {"supplier_id": "S1", "op_type_id": "OT1"})
    conn.commit()
    ot1 = identity_for(conn, "op_type", "OT1")
    ot2 = identity_for(conn, "op_type", "OT2")
    machine = identity_for(conn, "machine", "M1")
    operator = identity_for(conn, "operator", "O1")
    empty_op = identity_for(conn, "operator", "EMPTY")
    supplier = identity_for(conn, "supplier", "S1")
    assert (
        ot1 is not None
        and ot2 is not None
        and machine is not None
        and operator is not None
        and empty_op is not None
        and supplier is not None
    )

    # M1 and O1 reference OT1 in seed data and S1 is bound to it in WorkbenchSupplierOpTypes; flip OT1 to external
    # so the existing binding is mismatched for M1/O1, and back to internal so it is mismatched for S1.
    conn.execute("UPDATE OpTypes SET category='external' WHERE op_type_id='OT1'")
    conn.commit()
    for kind, target, relations in (
        ("machine", machine, {"op_type_refs": [ot1.ref]}),
        ("operator", operator, {"skill_refs": [ot1.ref]}),
    ):
        reader = WorkbenchResourceQueryService(conn, kind)
        normalized = reader.domain.normalize_input("update", {"fields": {"remark": "updated"}, "relationships": relations})
        with TransactionManager(conn).transaction():
            preparation = reader.preparation_for("update", normalized, ref=target.ref)
            checked = preparation.state(kind, preparation.current(kind, target).entity_key)
            outcome = reader.domain.apply_prepared(reader.domain.prepare("update", normalized, checked, preparation))
        assert outcome.result == "committed"

    conn.execute("UPDATE OpTypes SET category='internal' WHERE op_type_id='OT1'")
    conn.commit()
    supplier_reader = WorkbenchResourceQueryService(conn, "supplier")
    normalized = supplier_reader.domain.normalize_input(
        "update", {"fields": {"remark": "supplier-updated"}, "relationships": {"op_type_refs": [ot1.ref]}}
    )
    with TransactionManager(conn).transaction():
        preparation = supplier_reader.preparation_for("update", normalized, ref=supplier.ref)
        checked = preparation.state("supplier", preparation.current("supplier", supplier).entity_key)
        change = supplier_reader.domain.prepare("update", normalized, checked, preparation)
        assert change.identity is not None and change.identity.kind == "supplier"
        result = supplier_reader.domain.apply_prepared(change)
    assert result.result == "committed"
    assert result.data["entity_ref"] == supplier.ref

    # Adding a newly mismatched work type to supplier is still rejected.
    supplier = identity_for(conn, "supplier", "S1")
    assert supplier is not None
    normalized_bad = supplier_reader.domain.normalize_input(
        "update", {"relationships": {"op_type_refs": [ot1.ref, ot2.ref]}}
    )
    with TransactionManager(conn).transaction(), pytest.raises(WorkbenchCommandRejected) as error:
        preparation = supplier_reader.preparation_for("update", normalized_bad, ref=supplier.ref)
        checked = preparation.state("supplier", preparation.current("supplier", supplier).entity_key)
        supplier_reader.domain.prepare("update", normalized_bad, checked, preparation)
    assert error.value.code == "constraint_conflict"

    # Historical operator with skills_declared=0 and empty skills:
    # 1) Updating remark without skill_refs keeps skills_declared=0;
    # 2) Explicit empty skill_refs (e.g. file import "清除") declares skills_declared=1.
    op_reader = WorkbenchResourceQueryService(conn, "operator")
    normalized_op = op_reader.domain.normalize_input(
        "update", {"fields": {"remark": "keep-fallback"}}
    )
    with TransactionManager(conn).transaction():
        preparation = op_reader.preparation_for("update", normalized_op, ref=empty_op.ref)
        checked = preparation.state("operator", preparation.current("operator", empty_op).entity_key)
        outcome = op_reader.domain.apply_prepared(op_reader.domain.prepare("update", normalized_op, checked, preparation))
    assert outcome.result == "committed"
    profile_row = conn.execute(
        "SELECT skills_declared FROM WorkbenchOperatorProfiles WHERE operator_id='EMPTY'"
    ).fetchone()
    assert profile_row is None or profile_row[0] == 0

    empty_op = identity_for(conn, "operator", "EMPTY")
    assert empty_op is not None
    normalized_clear = op_reader.domain.normalize_input(
        "update", {"relationships": {"skill_refs": []}}
    )
    with TransactionManager(conn).transaction():
        preparation = op_reader.preparation_for("update", normalized_clear, ref=empty_op.ref)
        checked = preparation.state("operator", preparation.current("operator", empty_op).entity_key)
        clear_outcome = op_reader.domain.apply_prepared(op_reader.domain.prepare("update", normalized_clear, checked, preparation))
    assert clear_outcome.result == "committed"
    declared_row = conn.execute(
        "SELECT skills_declared FROM WorkbenchOperatorProfiles WHERE operator_id='EMPTY'"
    ).fetchone()
    assert declared_row is not None and declared_row[0] == 1


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
    insert_row(conn, "OperatorMachine", {"operator_id": "EMPTY", "machine_id": "M2", "skill_level": "normal", "is_primary": "no"})
    conn.commit()
    operator = identity_for(conn, "operator")
    replacement = identity_for(conn, "machine", "M2")
    assert operator is not None and replacement is not None
    service = WorkbenchOperatorMachinePermissions(conn)
    reader = WorkbenchResourceQueryService(conn, "operator")
    desired = ([{"machine_ref": replacement.ref, "skill_level": "normal", "is_primary": "yes"}]
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
