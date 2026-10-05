"""Kind scopes ignore unrelated collections while retaining real row prerequisites."""

import pytest

from core.models.workbench_resource_query import ResourcePageRequest
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from tests.workbench.batch_support import batch_database, detail
from tests.workbench.resource_metrics_support import measured_read, metrics_database
from tests.workbench.resource_table_support import table_database

_batch_fixture, _metrics_fixture, _table_fixture = batch_database, metrics_database, table_database


def test_machine_snapshot_ignores_unrelated_collections_and_summary_remains_live(metrics_conn):
    reader = WorkbenchResourceQueryService(metrics_conn, "machine")

    def capture():
        with reader.read_snapshot() as fingerprint:
            return fingerprint, reader.page(ResourcePageRequest("machine")), reader.create_snapshot()

    with measured_read(metrics_conn) as measured:
        before = capture()
    assert not any("FROM Materials" in sql or "FROM Parts" in sql for sql in measured["statements"])
    metrics_conn.execute("INSERT INTO Materials(material_id,name) VALUES ('UNRELATED','Unrelated material')")
    metrics_conn.execute("UPDATE Operators SET name='Changed unrelated operator' WHERE operator_id='OK'")
    metrics_conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('UNRELATED','Unrelated part')")
    metrics_conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('UNRELATED','UNRELATED',1)")
    metrics_conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name) "
                         "VALUES ('UNRELATED-01','UNRELATED',1,'A','Type A')")
    metrics_conn.commit()
    assert capture() == before
    assert reader.summary()["material"] == 1
    assert reader.summary()["part"] == 1
    metrics_conn.execute("UPDATE WorkbenchMachineGroups SET name='Changed visible group' WHERE group_id='G1'")
    metrics_conn.commit()
    assert capture()[0] != before[0]


@pytest.mark.parametrize("statement", [
    "UPDATE Machines SET name='Changed authorized machine' WHERE machine_id='A1'",
    "UPDATE WorkbenchShiftPatternDays SET shift_end='08:15' WHERE profile_id='H1'",
])
def test_operator_snapshot_keeps_authorized_machine_and_shift_pattern_dependencies(table_conn, statement):
    reader = WorkbenchResourceQueryService(table_conn, "operator")
    with reader.read_snapshot() as before:
        pass
    table_conn.execute(statement)
    table_conn.commit()
    with reader.read_snapshot() as after:
        assert after != before


def test_batch_qualification_uses_shared_rules_and_keeps_invalid_source_visible(batch_client):
    conn = batch_client.batch_conn
    conn.execute("UPDATE BatchOperations SET machine_id='M1',operator_id='O1' WHERE batch_id='FREE-001'")
    conn.execute("DELETE FROM OperatorSkill WHERE operator_id='O1'")
    conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,skills_declared) VALUES ('O1',1)")
    conn.commit()
    operation = detail(batch_client)["data"]["operations"][0]
    assert any("未登记本工种资格" in item["message"] for item in operation["issues"])
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('EXTBAD','External work','external')")
    conn.execute("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('O1','EXTBAD')")
    conn.commit()
    operation = detail(batch_client)["data"]["operations"][0]
    assert any(item["code"] == "operator_qualification_invalid" for item in operation["issues"])
