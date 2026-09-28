"""v33 preserves existing plans and labels the upgrade-time external context honestly."""

import pytest

from core.errors import ValidationError
from core.infrastructure.batch_external_context_schema import contract_issues, objects
from core.infrastructure.migrations.v33 import run
from core.services.scheduler.run.schedule_input_builder import build_algo_operations
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.batch.facts import BatchFacts
from core.services.workbench.batch.projection import BatchProjection
from tests.workbench.process_query_support import seed_process


def old_database(conn):
    for name in ("batch_external_context_created", "batch_external_context_source_changed"):
        conn.execute("DROP TRIGGER " + name)
    conn.execute("DROP TABLE BatchExternalContexts")
    conn.execute("UPDATE SchemaVersion SET version=32")
    seed_process(conn)
    conn.execute("""INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,
        supplier_id,ext_days) VALUES('OLD-20','PROC-B',20,'PROC-EX','热处理','external','PROC-S',3.25)""")
    op_id = conn.execute("SELECT id FROM BatchOperations WHERE op_code='OLD-20'").fetchone()[0]
    conn.execute("INSERT INTO Schedule(op_id,start_time,end_time,version) VALUES(?,?,?,1)",
                 (op_id, "2026-10-01 08:00:00", "2026-10-08 02:00:00"))
    conn.commit()
    return op_id


def test_upgrade_matches_new_schema_preserves_rows_and_captures_current_context(schema_conn):
    conn = schema_conn
    expected = {row[0]: row[1] for row in conn.execute("SELECT name,sql FROM sqlite_master") if row[0] in objects()}
    old_database(conn)
    before = {name: [tuple(row) for row in conn.execute("SELECT * FROM " + name)]
              for name in ("BatchOperations", "Schedule", "PartOperations", "ExternalGroups")}
    run(conn)
    assert contract_issues(conn) == []
    actual = {row[0]: row[1] for row in conn.execute("SELECT name,sql FROM sqlite_master") if row[0] in objects()}
    assert actual == expected
    assert before == {name: [tuple(row) for row in conn.execute("SELECT * FROM " + name)] for name in before}
    row = dict(conn.execute("SELECT * FROM BatchExternalContexts").fetchone())
    assert row["origin"] == "migration_v33" and row["total_days"] == 6.75
    conn.execute("UPDATE ExternalGroups SET total_days=19")
    conn.commit()
    svc = ScheduleService(conn)
    assert build_algo_operations(svc, svc.op_repo.list_by_batch("PROC-B"), strict_mode=True)[0].ext_group_total_days == 6.75
    facts = BatchFacts(conn).load()
    batch = next(row for row in facts["Batches"] if row["batch_id"] == "PROC-B")
    operation = BatchProjection(facts).entity(batch)["operations"][0]
    assert "升级时" in operation["external_context_notice"]


@pytest.mark.parametrize("broken", ["UPDATE PartOperations SET status='deleted' WHERE seq=20",
                                    "UPDATE ExternalGroups SET total_days=NULL",
                                    "UPDATE ExternalGroups SET start_seq=21"])
def test_invalid_upgrade_context_is_preserved_but_not_guessed(schema_conn, broken):
    conn = schema_conn
    old_database(conn)
    conn.execute(broken)
    conn.commit()
    run(conn)
    assert conn.execute("SELECT origin FROM BatchExternalContexts").fetchone()[0] == "migration_v33"
    svc = ScheduleService(conn)
    with pytest.raises(ValidationError) as error:
        build_algo_operations(svc, svc.op_repo.list_by_batch("PROC-B"), strict_mode=False)
    assert error.value.field == "external_context"


def test_existing_partial_schema_is_rejected_without_repair(schema_conn):
    conn = schema_conn
    conn.execute("DROP TRIGGER batch_external_context_created")
    conn.commit()
    before = list(conn.execute("SELECT name,sql FROM sqlite_master"))
    with pytest.raises(RuntimeError, match="partial"):
        run(conn)
    assert list(conn.execute("SELECT name,sql FROM sqlite_master")) == before
