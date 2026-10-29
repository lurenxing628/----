"""Export fields consume captured resource rows without write-conflict reads."""

import re

import pytest

from core.services.workbench.resource.file_projection import flat_resource
from core.services.workbench.resource.metrics import WorkbenchResourceMetricsService
from core.services.workbench.resource.states import ResourceChangePreparation
from core.services.workbench.resource.table_facts import ResourceTableFacts
from data.repositories.workbench_resource_table_repo import WorkbenchResourceTableRepository
from tests.workbench.resource_entity_support import resource_database  # noqa: F401


def _preparation(conn):
    identities = WorkbenchResourceTableRepository(conn).identities()
    return ResourceChangePreparation(ResourceTableFacts(WorkbenchResourceMetricsService(conn), identities))


@pytest.fixture
def file_resource_conn(resource_conn):
    resource_conn.execute("INSERT INTO WorkbenchMachineGroups(group_id,name) VALUES ('G1','Group')")
    resource_conn.execute("INSERT INTO WorkbenchMachineGroupMembers(machine_id,group_id) VALUES ('M1','G1')")
    resource_conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M1','OT2')")
    resource_conn.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days) "
                          "VALUES ('SHIFT1','Shift','2026-09-09',1)")
    resource_conn.execute("UPDATE Operators SET status='inactive' WHERE operator_id='O1'")
    resource_conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id,skills_declared,inactive_reason) "
                          "VALUES ('O1','SHIFT1',1,'leave')")
    resource_conn.execute("UPDATE WorkbenchSupplierProfiles SET inactive_reason='pending_review' WHERE supplier_id='S1'")
    resource_conn.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('S1','EXT')")
    resource_conn.execute("INSERT INTO WorkbenchOpTypePolicies(op_type_id,default_merge_mode) VALUES ('EXT','merged')")
    resource_conn.commit()
    return resource_conn


@pytest.mark.parametrize("kind,code,expected", (
    ("op_type", "EXT", {"category": "external", "default_merge_mode": "merged"}),
    ("machine", "M1", {"status": "maintain", "team_code": "T1", "op_type_codes": ["OT1", "OT2"], "group_code": "G1"}),
    ("operator", "O1", {"status": "leave", "team_code": "T1", "skills_declared": True,
                        "skill_codes": ["OT1"], "shift_profile_code": "SHIFT1", "inactive_reason": "leave"}),
    ("supplier", "S1", {"status": "pending_review", "default_days": 3.25, "op_type_codes": ["EXT"]}),
))
def test_captured_file_projection_preserves_columns_without_dependency_reads(file_resource_conn, kind, code, expected):
    conn = file_resource_conn
    preparation = _preparation(conn)
    reads = []
    conn.set_trace_callback(reads.append)
    try:
        state = preparation.export_state(kind, code)
        authorizations = preparation.authorizations(kind, code) if kind in ("machine", "operator") else ()
        row = flat_resource(kind, preparation.identity_by_code(kind, code), state, authorizations)
    finally:
        conn.set_trace_callback(None)
    assert {field: row[field] for field in expected} == expected
    # 旧单工种列与旧状态别名已删除；供应商能力来自 WorkbenchSupplierOpTypes。
    assert not {"legacy_status", "op_type_code", "explicit_op_type_codes", "legacy_op_type_code"} & set(row)
    if kind in ("machine", "operator", "supplier"):
        assert row["created_at"] == "2020-02-03 12:05:06"
    if kind in ("machine", "operator"):
        assert row["machine_authorizations"] == [{"machine_code": "M1", "operator_code": "O1", "skill_level": "expert",
                                                  "is_primary": "yes", "created_at": "2020-02-03 12:05:06"}]
    if kind == "operator":
        assert row["skill_details"] == [{"op_type_code": "OT1", "skill_level": "normal", "is_primary": "no",
                                         "created_at": "2020-02-03 12:05:06"}]
    assert not any(re.search(r"\b(?:PartOperations|BatchOperations|ExternalGroups|Schedule|WorkbenchShiftPatternDays)\b",
                             query, re.IGNORECASE) for query in reads)
