"""Thousands of real operations with constant read counts and linear preview size."""

import time

import pytest

from core.models.workbench_resource_action import ResourceActionPreview
from core.services.workbench.process_file_hours import ProcessHoursFileOperations
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from tests.workbench.process_file_hours_support import (
    apply,
    confirmations,
    decoded,
    hours_database,
    part_ref,
    snapshot,
)
from tests.workbench.process_workflow_support import confirm_all


def seed_scale(conn, count, merged):
    conn.execute("INSERT INTO Parts(part_no,part_name,route_raw,route_parsed) VALUES('BIG','large','original route','yes')")
    if merged:
        conn.execute("""INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id,remark)
            VALUES('BIG-G','BIG',1,?,'merged',8.5,'S','retained large group')""", (count,))
    fields = ("TE", "coating", "external", "S", "BIG-G", 2.5) if merged else ("TI", "turning", "internal", None, None, None)
    conn.executemany("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_group_id,
        ext_days,setup_hours,unit_hours,private_legacy) VALUES('BIG',?,?,?,?,?,?,?,0.5,1.25,?)""",
                     [(seq,) + fields + (b"scale\x00\xff",) for seq in range(1, count + 1)])
    conn.commit()
    confirm_all(conn, "BIG", person="scale reviewer")


@pytest.mark.parametrize("merged", (False, True))
def test_4000_operations_2000_rows_have_bounded_queries_and_preserve_unmentioned_facts(hours_conn, merged):
    seed_scale(hours_conn, 4000, merged)
    source = decoded(*[{"business_code": "BIG", "sequence": seq,
                        **({"group_total_days": 11.25} if merged else {"unit_hours": 2.25})}
                       for seq in range(1, 2001)])
    statements = []
    before, stamps = snapshot(hours_conn), confirmations(hours_conn)
    service = ProcessHoursFileOperations(hours_conn)
    started = time.perf_counter()
    hours_conn.set_trace_callback(statements.append)
    try:
        facts = WorkbenchProcessQueryService(hours_conn).facts()
        read_count = sum(sql.lstrip().upper().startswith("SELECT") for sql in statements)
        statements.clear()
        rows, extra = service.preview_rows(source, facts)
        preview_reads = sum(sql.lstrip().upper().startswith("SELECT") for sql in statements)
        assert 0 < preview_reads <= 15
        size = len(ResourceActionPreview.build("process.hours.import", {}, rows).document.encode("utf-8"))
        smaller, _ = service.preview_rows(source[:1000], facts)
        smaller_size = len(ResourceActionPreview.build("process.hours.import", {}, smaller).document.encode("utf-8"))
        assert size < smaller_size * 2.1 and size < 8 * 1024 * 1024
        statements.clear()
        results, refs = apply(hours_conn, rows)
        apply_reads = sum(sql.lstrip().upper().startswith("SELECT") for sql in statements)
    finally:
        hours_conn.set_trace_callback(None)
    elapsed = time.perf_counter() - started
    assert read_count < 50 and 0 < apply_reads <= 25
    assert len(results) == 2000 and all(row["result"] == "committed" for row in results)
    assert refs == [part_ref(hours_conn, "BIG")] and extra["affected_groups"] == []
    assert confirmations(hours_conn) == stamps
    after = snapshot(hours_conn)
    allowed = {"WorkbenchEntityRefs", "ExternalGroups" if merged else "PartOperations"}
    for table in before[1]:
        if table not in allowed:
            assert before[1][table] == after[1][table], table
    if not merged:
        columns = [row[1] for row in hours_conn.execute("PRAGMA table_info(PartOperations)")]
        for old, new in zip(before[1]["PartOperations"], after[1]["PartOperations"]):
            old, new = dict(zip(columns, old)), dict(zip(columns, new))
            assert new == ({**old, "unit_hours": 2.25} if old["part_no"] == "BIG" and old["seq"] <= 2000 else old)
    print(f"hours-scale merged={merged} operations=4000 rows=2000 facts_selects={read_count} preview_selects={preview_reads} "
          f"apply_selects={apply_reads} document_bytes={size} elapsed_seconds={elapsed:.3f}")
