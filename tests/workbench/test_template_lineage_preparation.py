"""Fixed source preparation, 6-column lineage eligibility and zero post-lock split SQL."""

import json
from datetime import date

from core.infrastructure.transaction import TransactionManager
from core.services.scheduler import template_lineage_query
from core.services.scheduler.template_lineage import TemplateLineageWriter
from core.services.workbench.batch.facts import BatchFacts
from core.services.workbench.batch.scope import BatchFactScope
from tests.workbench.template_lineage_support import create, instance_for, lineage, origin
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage_case  # noqa: F401


def test_batch_copies_prepare_raw_sources_once_and_reuse_across_targets(lineage_case, record_property):
    case, trace = lineage_case, []
    conn = case.conn
    with TransactionManager(conn).transaction():
        conn.execute("UPDATE PartOperations SET unit_hours=NULL,op_type_name=? WHERE id=?", ("Turning-A", case.template_id))
        conn.execute(
            "INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours,ext_days) "
            "VALUES ('P1',2,'T1','Turning','internal',NULL,0,1.5)"
        )
        conn.execute(
            "INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) "
            "VALUES ('P1',3,'T1','External','external',0,0)"
        )
    create(case, "PREP-SOURCE")
    original = [
        tuple(row)
        for row in conn.execute(
            "SELECT seq,op_type_name,setup_hours,unit_hours,ext_days FROM BatchOperations "
            "WHERE batch_id='PREP-SOURCE' ORDER BY seq"
        )
    ]
    assert original[0][1] == "Turning-A" and original[0][3] is None
    assert original[1][2] is None and original[1][4] == 1.5
    conn.execute(
        "UPDATE BatchExternalContexts SET origin='instance_copy' WHERE operation_id IN "
        "(SELECT id FROM BatchOperations WHERE batch_id='PREP-SOURCE')"
    )
    conn.commit()
    facts = BatchFactScope(BatchFacts(conn, material_day=date.today().isoformat())).load()
    source_rows = [row for row in facts["BatchOperations"] if row["batch_id"] == "PREP-SOURCE"]
    trace.clear()
    with TransactionManager(conn).transaction():
        writer = TemplateLineageWriter(conn)
        conn.set_trace_callback(trace.append)
        try:
            prepared = writer.prepare_instances(source_rows, facts=facts, complete_facts=True)
            for code in ("PREP-FIRST", "PREP-SECOND"):
                conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES (?,'P1',10)", (code,))
                for row in prepared:
                    writer.copy_prepared_instance(code, row)
        finally:
            conn.set_trace_callback(None)
    selects = [sql for sql in trace if sql.lstrip().upper().startswith("SELECT")]
    assert not any(
        "FROM WorkbenchEntityRefs r" in sql or "FROM BatchExternalContexts" in sql
        for sql in selects
    )
    assert sum("FROM WorkbenchTemplateLineageOrigins" in sql for sql in selects) == 1
    assert not any("WorkbenchTemplateLineageEvents" in sql or "birth_event_id" in sql for sql in trace)
    contexts = [
        dict(row)
        for row in conn.execute(
            "SELECT c.* FROM BatchExternalContexts c JOIN BatchOperations o "
            "ON o.id=c.operation_id WHERE o.batch_id LIKE 'PREP-%' ORDER BY o.id"
        )
    ]
    assert len(contexts) == 3
    assert all(
        {key: value for key, value in row.items() if key not in ("operation_id", "origin")}
        == {key: value for key, value in contexts[0].items() if key not in ("operation_id", "origin")}
        for row in contexts
    )
    assert [row["origin"] for row in contexts] == ["instance_copy", "instance_copy", "instance_copy"]
    record_property("lineage_two_targets_origin_reads", 1)


def test_copy_eligibility_freezes_at_birth_after_change_back_replacement_and_multi_reason_accumulation(lineage_case):
    case, conn = lineage_case, lineage_case.conn
    source_id = create(case, "HISTORY-SOURCE")
    source = instance_for(case, source_id)

    def copy_from(op_id, code):
        with TransactionManager(conn).transaction():
            conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES (?,'P1',10)", (code,))
            writer = TemplateLineageWriter(conn)
            prepared = writer.prepare_instances(
                [{"id": op_id}],
                facts=BatchFactScope(BatchFacts(conn, material_day=date.today().isoformat())).load(),
                complete_facts=True,
            )[0]
            return writer.copy_prepared_instance(code, prepared)

    early_first, early_second = copy_from(source_id, "HISTORY-EARLY-1"), copy_from(source_id, "HISTORY-EARLY-2")
    with TransactionManager(conn).transaction():
        conn.execute("UPDATE BatchOperations SET setup_hours=2 WHERE id=?", (source_id,))
        conn.execute("UPDATE BatchOperations SET setup_hours=0 WHERE id=?", (source_id,))
    assert origin(case, source_id)["instance_modified"] == 1
    changed_id = copy_from(source_id, "HISTORY-CHANGED")
    changed_ref = instance_for(case, changed_id)["operation_ref"]
    assert origin(case, changed_id)["source_eligible"] == 0
    assert origin(case, changed_id)["instance_modified"] == 0

    # Mutate and retire the unqualified copy to verify all 3 disqualification reasons coexist independently.
    with TransactionManager(conn).transaction():
        conn.execute("UPDATE BatchOperations SET unit_hours=5 WHERE id=?", (changed_id,))
        conn.execute("DELETE FROM BatchOperations WHERE id=?", (changed_id,))

    with TransactionManager(conn).transaction():
        conn.execute("DELETE FROM BatchOperations WHERE id=?", (source_id,))
        conn.execute(
            "INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) "
            "VALUES (?,'HISTORY-SOURCE_01','HISTORY-SOURCE',1,'T1','Turning','internal',0,1)",
            (source_id,),
        )
    replacement = instance_for(case, source_id)
    assert replacement["operation_ref"] != source["operation_ref"]
    replaced_id = copy_from(source_id, "HISTORY-REPLACED")
    assert not case.lineage_repo.origin_rows([instance_for(case, replaced_id)["operation_ref"]])

    for operation_id in (early_first, early_second):
        facts = lineage(case, operation_id)
        ref = instance_for(case, operation_id)["operation_ref"]
        assert not facts["problems"][ref]
        assert set(facts) == {"origins", "problems"}
        assert "_prepared" not in json.dumps(facts)

    combined = template_lineage_query.TemplateLineageQuery(conn).read([source["operation_ref"], changed_ref])
    assert [row["code"] for row in combined["problems"][source["operation_ref"]]] == [
        "template_instance_retired",
        "template_instance_modified",
    ]
    assert [row["code"] for row in combined["problems"][changed_ref]] == [
        "template_copy_source_unqualified",
        "template_instance_retired",
        "template_instance_modified",
    ]


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


def test_single_split_captures_lineage_in_same_snapshot_with_zero_post_lock_sql(lineage_case):
    case, conn = lineage_case, lineage_case.conn
    ancestor_op_id = create(case, "SPLIT-ANCESTOR", quantity=10)
    with TransactionManager(conn).transaction():
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('SPLIT-GEN2','P1',6)")
        writer = TemplateLineageWriter(conn)
        gen1_prepared = writer.prepare_instances(
            [{"id": ancestor_op_id}],
            facts=BatchFactScope(BatchFacts(conn, material_day=date.today().isoformat())).load(),
            complete_facts=True,
        )[0]
        gen2_op_id = writer.copy_prepared_instance("SPLIT-GEN2", gen1_prepared)
    gen2_ref = instance_for(case, gen2_op_id)["operation_ref"]
    gen2_batch_ref = conn.execute(
        "SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND entity_key='SPLIT-GEN2' AND active=1"
    ).fetchone()[0]

    reader = BatchFacts(conn, material_day=date.today().isoformat())
    with reader.detached_read_snapshot(mode="single_split", target_ref=gen2_batch_ref) as split_scope:
        conn.execute("UPDATE Batches SET quantity=99 WHERE batch_id='SPLIT-ANCESTOR'")
        conn.commit()
        trace = []
        conn.set_trace_callback(trace.append)
        try:
            facts = split_scope.load()
            source_ops = [row for row in facts["BatchOperations"] if row["batch_id"] == "SPLIT-GEN2"]
            captured_lineage = template_lineage_query.TemplateLineageQuery(conn).read_captured(
                facts["template_lineage_capture"]
            )
            prepared = TemplateLineageWriter(conn).prepare_instances(
                source_ops, facts=facts, complete_facts=False
            )
        finally:
            conn.set_trace_callback(None)
        assert trace == []
        assert captured_lineage["problems"][gen2_ref] == []
        assert len(prepared) == 1 and prepared[0].source_eligible is True
