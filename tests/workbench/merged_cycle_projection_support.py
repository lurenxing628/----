"""Current-schema SQLite fixtures and full-row oracles for merged cycle reads."""

import pytest

from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION, get_schema_version
from core.services.process.workflow_state import operation_confirmations, read_workflow
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from tests.workbench.process_query_support import ref_for, seed_process
from tests.workbench.process_stage_api_support import PART, StageAPI, seed_history


@pytest.fixture(name="merged_cycle_api")
def merged_cycle_application(app_client):
    api = StageAPI(app_client)
    with api.database() as conn:
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION
        seed_process(conn)
        seed_history(conn)
        conn.execute("UPDATE PartOperations SET ext_days=NULL WHERE part_no=? AND seq=20", (PART,))
        conn.execute("UPDATE ExternalGroups SET end_seq=25 WHERE group_id='PROC-G'")
        conn.execute("""INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id,remark)
            VALUES ('EM-G2',?,40,40,'merged',9.5,'PROC-S','second original group')""", (PART,))
        conn.executemany("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,
            ext_group_id,ext_days,setup_hours,unit_hours,private_stage_note)
            VALUES (?,?,'PROC-EX','Heat','external','PROC-S',?,NULL,0,0,'original member')""",
                         [(PART, 25, "PROC-G"), (PART, 40, "EM-G2")])
        conn.execute("UPDATE Parts SET route_raw='10车削20热处理25Heat30检验40Heat' WHERE part_no=?", (PART,))
    return api


def readonly_detail(api, code=PART):
    before = api.snapshot()
    with api.database() as conn:
        changes = conn.total_changes
        conn.execute("PRAGMA query_only=ON")
        reader = WorkbenchProcessQueryService(conn)
        with reader.read_snapshot():
            entity = reader.detail(ref_for(conn, code=code))
        assert entity["workflow"] == read_workflow(conn, code)
        confirmations = operation_confirmations(conn, code)
        for row in entity["operations"]:
            if row["status"] == "active":
                assert row["confirmation"] == confirmations[row["ref"]]
        assert conn.total_changes == changes
    http = api.detail(code)["data"]
    for name in ("operations", "external_groups", "workflow", "issues"):
        assert http[name] == entity[name]
    assert api.snapshot() == before
    return entity


def operation(entity, seq=20):
    return next(row for row in entity["operations"] if row["sequence"] == seq)


def issue_codes(row):
    return {item["code"] for item in row["issues"]}


def assert_group_cycle(entity, seq=20, total=6.75):
    row = operation(entity, seq)
    assert row["external_days"] is None
    assert not row["issues"], row["issues"]
    assert row["external_days_source"] == "group"
    group = next(item for item in entity["external_groups"] if item["ref"] == row["external_group_ref"])
    assert group["merge_mode"] == "merged" and group["total_days"] == total
    assert group["issues"] == []
