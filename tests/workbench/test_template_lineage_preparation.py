"""Fixed source preparation, historical copy eligibility and streamed evidence limits."""

import json

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.scheduler import template_lineage_query
from core.services.scheduler.template_lineage import TemplateLineageWriter
from core.services.workbench.batch.facts import BatchFacts
from tests.workbench.template_lineage_support import create, instance_for, lineage, origin
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage_case  # noqa: F401


def test_batch_copies_prepare_raw_sources_once_and_reuse_across_targets(lineage_case, record_property):
    case, trace = lineage_case, []
    conn = case.conn
    with TransactionManager(conn).transaction():
        conn.execute("UPDATE PartOperations SET unit_hours=NULL,op_type_name=? WHERE id=?", ("Turning-A", case.template_id))
        conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours,ext_days) "
                     "VALUES ('P1',2,'T1','Turning','internal',NULL,0,0)")
        conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) "
                     "VALUES ('P1',3,'T1','External','external',0,0)")
    create(case, "PREP-SOURCE")
    original = [tuple(row) for row in conn.execute("SELECT seq,op_type_name,setup_hours,unit_hours,ext_days FROM BatchOperations "
                                                  "WHERE batch_id='PREP-SOURCE' ORDER BY seq")]
    assert original[0][1] == "Turning-A" and original[0][3] is None
    assert original[1][2] is None and original[1][4] == 0
    conn.execute("UPDATE BatchExternalContexts SET origin='instance_copy' WHERE operation_id IN "
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
    assert len(contexts) == 3
    assert all({key: value for key, value in row.items() if key not in ('operation_id', 'origin')} ==
               {key: value for key, value in contexts[0].items() if key not in ('operation_id', 'origin')} for row in contexts)
    assert [row['origin'] for row in contexts] == ['instance_copy', 'instance_copy', 'instance_copy']
    record_property("lineage_two_targets_source_event_reads", 1)


def test_copy_eligibility_uses_the_source_event_at_birth_after_change_back_withdrawal_and_replacement(lineage_case):
    case, conn = lineage_case, lineage_case.conn
    source_id = create(case, "HISTORY-SOURCE")
    source = instance_for(case, source_id)

    def copy(code):
        with TransactionManager(conn).transaction():
            conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES (?,'P1',10)", (code,))
            writer = TemplateLineageWriter(conn)
            prepared = writer.prepare_instances([{"id": source_id}], facts=BatchFacts(conn).load())[0]
            return writer.copy_prepared_instance(code, prepared)

    early_first, early_second = copy("HISTORY-EARLY-1"), copy("HISTORY-EARLY-2")
    with TransactionManager(conn).transaction():
        conn.execute("UPDATE BatchOperations SET setup_hours=2 WHERE id=?", (source_id,))
        conn.execute("UPDATE BatchOperations SET setup_hours=0 WHERE id=?", (source_id,))
    changed_id = copy("HISTORY-CHANGED")
    assert origin(case, changed_id)["source_eligible"] == 0
    with TransactionManager(conn).transaction():
        conn.execute("DELETE FROM BatchOperations WHERE id=?", (source_id,))
        conn.execute("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) "
                     "VALUES (?,'HISTORY-SOURCE_01','HISTORY-SOURCE',1,'T1','Turning','internal',0,1)", (source_id,))
    replacement = instance_for(case, source_id)
    assert replacement["operation_ref"] != source["operation_ref"]
    replaced_id = copy("HISTORY-REPLACED")
    assert not list(case.lineage_repo.origin_rows([instance_for(case, replaced_id)["operation_ref"]]))
    for operation_id in (early_first, early_second):
        facts = lineage(case, operation_id)
        ref = instance_for(case, operation_id)["operation_ref"]
        assert not facts["problems"][ref]
        assert [row["code"] for row in facts["problems"][source["operation_ref"]]] == [
            "template_instance_retired", "template_instance_modified"]
        assert set(facts) == {"available", "origins", "events", "current", "templates", "lineages", "problems"}
        assert "_prepared" not in json.dumps(facts, default=lambda value: value.__dict__)


def test_streamed_event_budget_uses_remaining_limit_across_real_chunks(lineage_case, monkeypatch):
    case, conn = lineage_case, lineage_case.conn
    first_id, second_id = create(case, "LIMIT-FIRST"), create(case, "LIMIT-SECOND")
    first = instance_for(case, first_id)
    second = instance_for(case, second_id)
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


def test_calibration_merges_and_sorts_duplicate_exclusion_reasons_across_bound_and_unbound(lineage_case):
    from tests.workbench.template_lineage_support import calibration

    case, conn = lineage_case, lineage_case.conn
    create(case, "BOUND-UNREPORTED")
    with TransactionManager(conn).transaction():
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('UNBOUND-UNREPORTED','P1',10)")
        conn.execute(
            "INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) "
            "VALUES ('UNBOUND_01','UNBOUND-UNREPORTED',1,'T1','Turning','internal',0,1)"
        )
    conn.commit()
    result = calibration(case)
    reasons = result["rows"][0]["exclusion_reasons"]
    codes = [row["code"] for row in reasons]
    assert codes == sorted(set(codes))
    by_code = {row["code"]: row["count"] for row in reasons}
    assert by_code["production_reports_missing"] == 3
