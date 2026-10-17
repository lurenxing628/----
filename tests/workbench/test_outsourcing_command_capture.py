"""Shipment commands capture their target once while preserving source rules."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.outsourcing_support import outsourcing_case as _outsourcing_case  # noqa: F401


def _read_queries(conn, action):
    statements = []
    conn.set_trace_callback(statements.append)
    try:
        result = action()
    finally:
        conn.set_trace_callback(None)
    return result, [sql for sql in statements if sql.lstrip().startswith(("SELECT", "WITH"))]


def test_member_growth_keeps_preview_and_confirmation_reads_bounded(outsourcing_case):
    case, conn = outsourcing_case, outsourcing_case.conn
    conn.executemany("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                     "VALUES (?,'XB1',?,'XT1','Heat treatment','external','XS1',2)",
                     [("XO" + str(index), index) for index in range(4, 201)])
    conn.commit()
    refs = [row[0] for row in conn.execute("SELECT r.ref FROM WorkbenchPlanSourceRefs r JOIN BatchOperations o "
        "ON r.source_key=CAST(o.id AS TEXT) WHERE r.kind='operation' AND r.active=1 ORDER BY o.seq,o.id")]
    payload = case.payload(merged=True)
    small = {**payload, "target": {**payload["target"], "operation_refs": refs[:3]}}
    large = {**payload, "target": {**payload["target"], "operation_refs": refs}}
    case.preview(small)
    _, small_reads = _read_queries(conn, lambda: case.preview(small))
    preview, large_reads = _read_queries(conn, lambda: case.preview(large))
    assert len(large_reads) == len(small_reads)
    assert len(preview["target"]["operations"]) == 200
    result, confirmation_reads = _read_queries(conn, lambda: case.confirm(preview))
    assert len(confirmation_reads) < 40
    ref = result["data"]["outsourcing_ref"]
    assert conn.execute("SELECT count(*) FROM WorkbenchOutsourcingMembers WHERE outsourcing_ref=?", (ref,)).fetchone()[0] == 200
    assert result["data"]["target"] == preview["target"]


def test_new_registration_keeps_shared_piece_continuity_rule(outsourcing_case):
    case = outsourcing_case
    case.conn.execute("UPDATE BatchOperations SET piece_id='A' WHERE op_code IN ('XO1','XO3')")
    case.conn.commit()
    payload = case.payload(merged=True)
    payload["target"]["operation_refs"] = [case.operation_ref("XO1"), case.operation_ref("XO3")]
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        case.preview(payload)
    assert rejected.value.code == "constraint_conflict"
    assert case.conn.execute("SELECT count(*) FROM WorkbenchOutsourcingReceipts").fetchone()[0] == 0


def test_registered_members_do_not_reapply_new_shipment_continuity(outsourcing_case):
    case = outsourcing_case
    first = case.confirm(case.preview(case.payload(merged=True)))
    case.conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source) "
                      "VALUES ('ADDED-BETWEEN','XB1',1.5,'XT1','Added route step','internal')")
    case.conn.commit()
    payload = {"outsourcing_ref": first["data"]["outsourcing_ref"],
               "declared_operator": "Inspector", "reason": "Current return check"}
    preview, reads = _read_queries(case.conn, lambda: case.preview(payload))
    assert not any("ORDER BY seq,id" in sql for sql in reads)
    assert case.confirm(preview)["result"] == "committed"
    assert case.detail(payload["outsourcing_ref"])["history_count"] == 2


def test_confirmation_captures_changed_source_again(outsourcing_case):
    case = outsourcing_case
    preview = case.preview(case.payload(merged=True))
    case.conn.execute("UPDATE BatchOperations SET op_type_name='Revised operation' WHERE op_code='XO1'")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        case.confirm(preview)
    assert rejected.value.code == "stale_write"
    assert case.conn.execute("SELECT count(*) FROM WorkbenchOutsourcingReceipts").fetchone()[0] == 0
