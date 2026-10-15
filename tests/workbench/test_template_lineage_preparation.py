"""Fixed source preparation, historical copy eligibility and streamed evidence limits."""

import json

import pytest

from core.infrastructure.batch_external_context_schema import install as install_external_contexts
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.scheduler import template_lineage_query
from core.services.scheduler.template_lineage import TemplateLineageWriter
from core.services.workbench.batch.facts import BatchFacts
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository
from tests.workbench.template_lineage_support import create, lineage, origin
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage_case  # noqa: F401


def test_batch_copies_prepare_raw_sources_once_and_reuse_across_targets(lineage_case, monkeypatch, record_property):
    case, trace = lineage_case, []
    conn = case.conn
    with TransactionManager(conn).transaction():
        install_external_contexts(conn)
        conn.execute("UPDATE PartOperations SET unit_hours=NULL,op_type_name=? WHERE id=?", (b"Turning\x00", case.template_id))
        conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours,ext_days) "
                     "VALUES ('P1',2,'T1','Turning','internal',NULL,0,?)", (b"raw\x00",))
        conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) "
                     "VALUES ('P1',3,'T1','External','external',0,0)")
    # These old per-id paths must not be called after the raw batch rows have been captured.
    def per_id_read(*_):
        raise AssertionError("Source row was already captured.")

    monkeypatch.setattr(WorkbenchTemplateLineageRepository, "template", per_id_read)
    monkeypatch.setattr(WorkbenchTemplateLineageRepository, "instance", per_id_read)
    conn.set_trace_callback(trace.append)
    try:
        create(case, "PREP-SOURCE")
        case.batch_service.copy_batch("PREP-SOURCE", "PREP-LEGACY")
    finally:
        conn.set_trace_callback(None)
    selects = [sql for sql in trace if sql.lstrip().upper().startswith("SELECT")]
    assert sum("WHERE o.part_no=" in sql for sql in selects) == 1
    assert sum("WHERE o.batch_id='PREP-SOURCE'" in sql for sql in selects) == 1
    assert sum(" AS _lineage_bytes FROM WorkbenchTemplateLineageOrigins" in sql for sql in selects) == 1
    assert sum(" AS _lineage_bytes FROM WorkbenchTemplateLineageEvents" in sql for sql in selects) == 1
    assert sum("e.event_id AS birth_event_id" in sql for sql in selects) == 6
    assert not any("SUM(" in sql.upper() or "FROM WorkbenchProductionReports" in sql or
                   "FROM WorkbenchExecutionLegacyFacts" in sql or "FROM OperationExecutionEvents" in sql for sql in selects)
    original = [tuple(row) for row in conn.execute("SELECT seq,op_type_name,setup_hours,unit_hours,ext_days FROM BatchOperations "
                                                  "WHERE batch_id='PREP-SOURCE' ORDER BY seq")]
    assert original[0][1] == b"Turning\x00" and original[0][3] is None
    assert original[1][2] is None and original[1][4] == b"raw\x00"
    assert [tuple(row) for row in conn.execute("SELECT seq,op_type_name,setup_hours,unit_hours,ext_days FROM BatchOperations "
                                              "WHERE batch_id='PREP-LEGACY' ORDER BY seq")] == original
    before = {name: [tuple(row) for row in conn.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]
              for name in ("Batches", "BatchOperations", "WorkbenchEntityRefs", "WorkbenchPlanSourceRefs",
                           "WorkbenchTemplateLineageOrigins", "WorkbenchTemplateLineageEvents", "BatchExternalContexts")}
    insert, inserted = WorkbenchTemplateLineageRepository.insert_instance, []

    def fail_second(repo, payload):
        inserted.append(payload)
        if len(inserted) == 2:
            raise RuntimeError("Actual second instance insert failed.")
        return insert(repo, payload)

    with monkeypatch.context() as failure:
        failure.setattr(WorkbenchTemplateLineageRepository, "insert_instance", fail_second)
        with pytest.raises(RuntimeError, match="Actual second"):
            case.batch_service.copy_batch("PREP-SOURCE", "PREP-ROLLBACK")
    assert len(inserted) == 2
    assert {name: [tuple(row) for row in conn.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]
            for name in before} == before
    conn.execute("UPDATE BatchExternalContexts SET origin='migration_v33' WHERE operation_id IN "
                 "(SELECT id FROM BatchOperations WHERE batch_id='PREP-SOURCE')")
    conn.commit()
    facts = BatchFacts(conn).load()
    source_rows = [row for row in facts["BatchOperations"] if row["batch_id"] == "PREP-SOURCE"]
    trace.clear()
    with TransactionManager(conn).transaction():
        writer = TemplateLineageWriter(conn)
        conn.set_trace_callback(trace.append)
        try:
            prepared = writer.prepare_instances(source_rows, facts=facts)
            for code in ("PREP-FIRST", "PREP-SECOND"):
                conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES (?,'P1',10)", (code,))
                for row in prepared:
                    writer.copy_prepared_instance(code, row)
        finally:
            conn.set_trace_callback(None)
    selects = [sql for sql in trace if sql.lstrip().upper().startswith("SELECT")]
    assert not any("FROM WorkbenchPlanSourceRefs r" in sql or "FROM WorkbenchEntityRefs r" in sql or
                   "FROM BatchExternalContexts" in sql for sql in selects)
    assert sum(" AS _lineage_bytes FROM WorkbenchTemplateLineageEvents" in sql for sql in selects) == 1
    assert sum("e.event_id AS birth_event_id" in sql for sql in selects) == 6
    contexts = [dict(row) for row in conn.execute("SELECT c.* FROM BatchExternalContexts c JOIN BatchOperations o "
                                                "ON o.id=c.operation_id WHERE o.batch_id LIKE 'PREP-%' ORDER BY o.id")]
    assert len(contexts) == 4
    assert all({key: value for key, value in row.items() if key not in ('operation_id', 'origin')} ==
               {key: value for key, value in contexts[0].items() if key not in ('operation_id', 'origin')} for row in contexts)
    assert [row['origin'] for row in contexts] == ['migration_v33', 'instance_copy', 'migration_v33', 'migration_v33']
    record_property("lineage_two_targets_source_event_reads", 1)


def test_copy_eligibility_uses_the_source_event_at_birth_after_change_back_withdrawal_and_replacement(lineage_case):
    case, conn = lineage_case, lineage_case.conn
    source_id = create(case, "HISTORY-SOURCE")
    source = case.lineage_repo.instance(source_id)

    def copy(code):
        with TransactionManager(conn).transaction():
            conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES (?,'P1',10)", (code,))
            return TemplateLineageWriter(conn).copy_instance(code, source_id)

    early_first, early_second = copy("HISTORY-EARLY-1"), copy("HISTORY-EARLY-2")
    with TransactionManager(conn).transaction():
        conn.execute("UPDATE BatchOperations SET setup_hours=2 WHERE id=?", (source_id,))
        conn.execute("UPDATE BatchOperations SET setup_hours=0 WHERE id=?", (source_id,))
    changed_id = copy("HISTORY-CHANGED")
    assert origin(case, changed_id)["source_eligible"] == 0
    with TransactionManager(conn).transaction():
        assert TemplateLineageWriter(conn).withdraw(source["operation_ref"], "historical fixture")
    withdrawn_id = copy("HISTORY-WITHDRAWN")
    assert origin(case, withdrawn_id)["source_eligible"] == 0
    with TransactionManager(conn).transaction():
        conn.execute("DELETE FROM BatchOperations WHERE id=?", (source_id,))
        conn.execute("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) "
                     "VALUES (?,'HISTORY-SOURCE_01','HISTORY-SOURCE',1,'T1','Turning','internal',0,1)", (source_id,))
    replacement = case.lineage_repo.instance(source_id)
    assert replacement["operation_ref"] != source["operation_ref"]
    replaced_id = copy("HISTORY-REPLACED")
    assert not case.lineage_repo.origins([case.lineage_repo.instance(replaced_id)["operation_ref"]])
    for operation_id in (early_first, early_second):
        facts = lineage(case, operation_id)
        ref = case.lineage_repo.instance(operation_id)["operation_ref"]
        assert not facts["problems"][ref]
        assert [row["code"] for row in facts["problems"][source["operation_ref"]]] == [
            "template_lineage_withdrawn", "template_instance_retired", "template_instance_modified"]
        assert set(facts) == {"available", "origins", "events", "current", "templates", "lineages", "problems"}
        assert "_prepared" not in json.dumps(facts, default=lambda value: value.__dict__)


def test_streamed_event_budget_uses_remaining_limit_across_real_chunks(lineage_case, monkeypatch):
    case, conn = lineage_case, lineage_case.conn
    first_id, second_id = create(case, "LIMIT-FIRST"), create(case, "LIMIT-SECOND")
    first = case.lineage_repo.instance(first_id)
    second = case.lineage_repo.instance(second_id)
    with TransactionManager(conn).transaction():
        conn.execute("UPDATE BatchOperations SET setup_hours=2 WHERE id=?", (first_id,))
    refs = [first["operation_ref"]] + ["absent-" + str(index) for index in range(299)] + [second["operation_ref"]]
    trace = []
    monkeypatch.setattr(template_lineage_query, "MAX_EVENTS", 2)
    conn.set_trace_callback(trace.append)
    try:
        with pytest.raises(WorkbenchCommandRejected) as rejected:
            template_lineage_query.read_events(case.lineage_repo, refs)
    finally:
        conn.set_trace_callback(None)
    assert rejected.value.code == "query_too_large" and rejected.value.status == 413
    queries = [sql for sql in trace if "FROM WorkbenchTemplateLineageEvents" in sql]
    assert len(queries) == 2 and queries[0].endswith("LIMIT 3") and queries[1].endswith("LIMIT 1")
    assert all("SUM(" not in sql.upper() for sql in queries)
