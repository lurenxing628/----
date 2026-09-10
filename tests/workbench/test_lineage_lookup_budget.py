"""The original 100m budget, exact v27 semantics and one additive lookup index."""

import sqlite3

import pytest

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.migrations import v28
from core.infrastructure.workbench_lineage_lookup_schema import (
    LINEAGE_LOOKUP_INDEX,
    install_lineage_lookup,
    lineage_lookup_contract_issues,
    lineage_lookup_objects,
)
from core.infrastructure.workbench_template_lineage_schema import template_lineage_contract_issues
from core.models.workbench_calibration import CalibrationQuery
from core.services.scheduler.batch_service import BatchService
from core.services.workbench.calibration import WorkbenchCalibrationService
from core.services.workbench.template_lineage import TemplateLineageWriter
from core.services.workbench.template_lineage_query import TemplateLineageQuery
from tests.workbench.execution_ledger_support import NOW
from tests.workbench.lineage_lookup_budget_support import (
    ORIGINAL_FAILURE_STEPS,
    ORIGINAL_VM_BUDGET,
    born_program,
    born_select,
    load_v27,
    measured_sql,
    replay_writes,
    schema_rows,
    typed_rows,
)
from tests.workbench.lineage_lookup_budget_support import v27_fixture as _v27_fixture
from tests.workbench.plan_identity_support import dynamic_scale, seed_plans


def test_original_v27_regression_is_retained(v27_conn):
    elapsed, steps = dynamic_scale(v27_conn)
    assert steps > ORIGINAL_VM_BUDGET
    if sqlite3.sqlite_version == "3.35.5":
        assert steps == ORIGINAL_FAILURE_STEPS
    print({"v27_original_seconds": elapsed, "steps_upper": steps, "unchanged_budget": ORIGINAL_VM_BUDGET})


def test_original_unmodified_test_passes_with_only_additive_ddl(schema_conn):
    from tests.workbench.test_plan_persistent_identity import (
        test_ten_thousand_dynamic_versions_and_distinct_operations_avoid_quadratic_writes as original,
    )

    schema_conn.execute("BEGIN")
    v28.run(schema_conn)
    schema_conn.commit()
    original(schema_conn)


def test_five_to_ten_thousand_writes_are_near_linear(v27_conn):
    second = sqlite3.connect(":memory:")
    second.row_factory = sqlite3.Row
    second.execute("PRAGMA foreign_keys=ON")
    try:
        load_v27(second)
        results = []
        for conn, count in ((v27_conn, 5000), (second, 10000)):
            conn.execute("BEGIN")
            v28.run(conn)
            conn.commit()
            elapsed, steps = dynamic_scale(conn, count)
            assert steps < ORIGINAL_VM_BUDGET
            assert conn.execute("SELECT count(*) FROM WorkbenchTaskRefs").fetchone()[0] == count * 3
            assert conn.execute("SELECT count(*) FROM WorkbenchTemplateLineageEvents").fetchone()[0] == count + 1
            results.append(steps)
            print({"indexed_operations": count, "seconds": elapsed, "steps_upper": steps})
        assert results[0] * 1.8 < results[1] < results[0] * 2.2
    finally:
        second.close()


def test_explain_uses_exact_expression_index_in_original_trigger(v27_conn):
    conn = v27_conn
    sql = "EXPLAIN QUERY PLAN " + born_select()
    before = [row[3] for row in conn.execute(sql, ("a" * 48, "1"))]
    assert any("SCAN" in row and "BatchOperations" in row for row in before)
    conn.execute("BEGIN")
    v28.run(conn)
    after = [row[3] for row in conn.execute(sql, ("a" * 48, "1"))]
    assert any("USING INDEX " + LINEAGE_LOOKUP_INDEX in row and "<expr>=?" in row for row in after)
    assert not any("SCAN" in row and "BatchOperations" in row for row in after)
    root = conn.execute("SELECT rootpage FROM sqlite_master WHERE name=?", (LINEAGE_LOOKUP_INDEX,)).fetchone()[0]
    program = born_program(conn)
    cursors = [row[2] for row in program if row[1] == "OpenRead" and row[3] == root and row[4] == 0]
    assert cursors and any(row[1] == "SeekGE" and row[2] in cursors for row in program)
    assert not any(row[1] == "Rewind" and row[2] in cursors for row in program)
    print({"born_before": before, "born_after": after, "trigger_index_root": root})


@pytest.mark.parametrize("installer", [install_lineage_lookup, v28.run])
def test_caller_transaction_rollback_and_idempotence(v27_conn, installer):
    conn = v27_conn
    before = schema_rows(conn), typed_rows(conn), conn.total_changes
    with pytest.raises(RuntimeError, match="caller"):
        installer(conn)
    assert (schema_rows(conn), typed_rows(conn), conn.total_changes) == before
    conn.execute("BEGIN")
    installer(conn)
    assert conn.in_transaction and not lineage_lookup_contract_issues(conn)
    conn.rollback()
    assert (schema_rows(conn), typed_rows(conn), conn.total_changes) == before
    conn.execute("BEGIN")
    installer(conn)
    conn.commit()
    conn.execute("PRAGMA query_only=ON")
    conn.execute("BEGIN")
    before = schema_rows(conn), typed_rows(conn), conn.total_changes
    installer(conn)
    assert conn.in_transaction
    assert (schema_rows(conn), typed_rows(conn), conn.total_changes) == before
    conn.rollback()


@pytest.mark.parametrize("ddl", [
    "CREATE INDEX {name} ON BatchOperations(id)",
    "CREATE INDEX {name} ON BatchOperations(CAST(id AS INTEGER))",
    "CREATE UNIQUE INDEX {name} ON BatchOperations(CAST(id AS TEXT))",
    "CREATE INDEX {name} ON BatchOperations(CAST(id AS TEXT)) WHERE id>0",
    "CREATE INDEX {name} ON PartOperations(CAST(id AS TEXT))",
    "CREATE TABLE {name}(id INTEGER)",
])
def test_same_name_different_ddl_is_rejected_without_repair(v27_conn, ddl):
    conn = v27_conn
    conn.execute(ddl.format(name=LINEAGE_LOOKUP_INDEX))
    conn.commit()
    before = schema_rows(conn), typed_rows(conn), conn.total_changes
    conn.execute("BEGIN")
    assert lineage_lookup_contract_issues(conn) == ["invalid_lineage_lookup:" + LINEAGE_LOOKUP_INDEX]
    with pytest.raises(RuntimeError, match="invalid_lineage_lookup"):
        v28.run(conn)
    assert conn.in_transaction
    conn.rollback()
    assert (schema_rows(conn), typed_rows(conn), conn.total_changes) == before


def test_damaged_v27_is_not_silently_repaired(v27_conn):
    conn = v27_conn
    conn.execute("DROP TRIGGER wb_lineage_operation_born")
    before = schema_rows(conn), typed_rows(conn)
    conn.execute("BEGIN")
    with pytest.raises(RuntimeError, match="missing_template_lineage"):
        v28.run(conn)
    assert (schema_rows(conn), typed_rows(conn)) == before
    assert lineage_lookup_contract_issues(conn) == ["missing_lineage_lookup:" + LINEAGE_LOOKUP_INDEX]
    conn.rollback()


def test_existing_typed_rows_refs_origins_events_and_version_are_untouched(v27_conn):
    conn = v27_conn
    seed_plans(conn)
    conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,setup_hours,unit_hours) "
                 "VALUES ('CAT-P',1,?,NULL,1.25)", (sqlite3.Binary(b"original\x00\xff"),))
    conn.commit()
    BatchService(conn).create_batch_from_template("COPIED", "CAT-P", 2)
    conn.commit()
    before, ddl, changes = typed_rows(conn), schema_rows(conn), conn.total_changes
    assert before["WorkbenchTemplateLineageOrigins"] and before["WorkbenchTemplateLineageEvents"]
    assert before["WorkbenchTaskRefs"] and before["WorkbenchPlanSourceRefs"]
    conn.execute("BEGIN")
    with measured_sql(conn) as stats:
        assert v28.run(conn) == MigrationOutcome.APPLIED
    assert conn.in_transaction and conn.total_changes == changes
    conn.commit()
    assert typed_rows(conn) == before
    assert [row for row in schema_rows(conn) if row[1] != LINEAGE_LOOKUP_INDEX] == ddl
    assert not template_lineage_contract_issues(conn) and not lineage_lookup_contract_issues(conn)
    assert conn.execute("SELECT version FROM SchemaVersion").fetchone()[0] == 27
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    assert [sql for sql in stats["statements"] if not sql.lstrip().upper().startswith("SELECT")] == list(lineage_lookup_objects().values())


def test_indexing_ten_thousand_old_operations_never_replays_birth(mem_conn):
    def old_rows(conn):
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('OLD-P','Old')")
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('OLD-B','OLD-P',1)")
        conn.executemany("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,setup_hours) "
                         "VALUES (?,'OLD-B',?,?,NULL)",
                         (("OLD-" + str(i), i, sqlite3.Binary(b"old\x00\xff")) for i in range(1, 10001)))

    conn = load_v27(mem_conn, seed_before_v27=old_rows)
    before, changes = typed_rows(conn), conn.total_changes
    assert len(before["BatchOperations"]) == 10000 and len(before["WorkbenchPlanSourceRefs"]) == 10000
    assert before["WorkbenchTemplateLineageOrigins"] == before["WorkbenchTemplateLineageEvents"] == []
    conn.execute("BEGIN")
    with measured_sql(conn) as stats:
        v28.run(conn)
    assert conn.in_transaction and conn.total_changes == changes
    conn.commit()
    assert typed_rows(conn) == before and stats["steps_upper"] < ORIGINAL_VM_BUDGET
    print({"old_operations": 10000, "migration_steps_upper": stats["steps_upper"], "replayed_births": 0})


@pytest.mark.parametrize("recursive", [0, 1])
def test_forward_birth_update_replace_retire_semantics_are_identical(v27_conn, recursive):
    conn = v27_conn
    second = sqlite3.connect(":memory:")
    second.row_factory = sqlite3.Row
    second.execute("PRAGMA foreign_keys=ON")
    try:
        conn.backup(second)
        second.execute("BEGIN")
        v28.run(second)
        second.commit()
        for target in (conn, second):
            target.execute("PRAGMA recursive_triggers=" + str(recursive))
            replay_writes(target)
        assert typed_rows(second) == typed_rows(conn)
        for key in ("1", "01", "+1", "1.0", " 1", b"1", None, "9223372036854775807", "-7"):
            assert list(map(tuple, conn.execute(born_select(), ("b" * 48, key)))) == list(map(tuple, second.execute(born_select(), ("b" * 48, key))))
    finally:
        second.close()


def test_five_thousand_real_sources_and_calibration_have_bounded_sql(v27_conn):
    conn = v27_conn
    conn.execute("BEGIN")
    v28.run(conn)
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('SCALE-P','Scale')")
    template_id = conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,source,unit_hours) "
                               "VALUES ('SCALE-P',1,'Scale','internal',1)").lastrowid
    writer = TemplateLineageWriter(conn)
    for number in range(5000):
        batch = "SCALE-" + str(number)
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES (?,'SCALE-P',1)", (batch,))
        writer.copy_template(batch, template_id)
    conn.commit()
    refs = [row[0] for row in conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1")]
    assert len(refs) == 5000
    before = typed_rows(conn), conn.total_changes
    conn.execute("PRAGMA query_only=ON")
    with measured_sql(conn) as stats:
        sources = TemplateLineageQuery(conn).read(refs)
        service = WorkbenchCalibrationService(conn, as_of=NOW)
        with service.read_snapshot():
            facts = service.read(CalibrationQuery())
    assert len(sources["events"]) == 5000 and sum(map(len, sources["events"].values())) == 5000
    assert len(sources["origins"]) == len(sources["lineages"]) == 5000
    assert not any(sources["problems"].values())
    assert facts["rows"][0]["candidate_count"] == 5000 and facts["rows"][0]["sample_count"] == 0
    assert stats["selects"] < 300 and stats["steps_upper"] < ORIGINAL_VM_BUDGET
    assert (typed_rows(conn), conn.total_changes) == before
    print({"real_sources": 5000, "selects": stats["selects"], "steps_upper": stats["steps_upper"]})
