"""Indexed history ordering and foreign-key lookups preserve saved business facts."""

import json
import logging
import sqlite3
from datetime import datetime

import pytest

from core.errors import AppError, ErrorCode
from core.infrastructure import database
from core.infrastructure.efficiency_indexes_schema import ADDED, contract_issues
from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION, current_schema_contract_issues
from core.infrastructure.schema_structure import SchemaStructure
from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandOutcome
from core.models.workbench_run_history import RunHistoryScope
from core.services.workbench.facts.production_capture import ProductionFactsCapture, validate_production_archive
from data.repositories.batch_operation_repo import BatchOperationRepository
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository
from data.repositories.workbench_run_query_repo import WorkbenchRunHistoryQueryRepository
from tests._support.production_facts_dump import production_facts


@pytest.fixture
def indexed_db(tmp_path):
    path = str(tmp_path / "efficiency-indexes.sqlite")
    database.ensure_schema(path, logging.getLogger(__name__))
    conn = database.get_connection(path)
    try:
        yield path, conn
    finally:
        conn.close()


def _run(
    conn,
    number,
    accepted,
    *,
    time=None,
    revisions_json='{"revisions":{"parts":1},"schema":[]}',
    conditions_archive_json='{"synthetic":"saved input"}',
):
    """Use real journal tables and triggers; timestamps deliberately retain their original precision."""
    ref, request_key = f"{number:048x}", f"efficiency-run-{number:04d}"
    WorkbenchCommandRepository(conn).insert(
        request_key=request_key, receipt_ref=f"{number:032x}", action="scheduling.run", context_ref="input-" + ref,
        input_json=content_text({"input_ref": "input-" + ref}, json_input=True),
        outcome=WorkbenchCommandOutcome("committed", {"run_ref": ref}))
    conn.execute(
        """INSERT INTO WorkbenchRunJobs(
            run_ref, request_key, input_ref, normalized_input_json,
            revisions_json, conditions_archive_json, execution_json, baseline_json,
            accepted_at, state, stage
        ) VALUES (?, ?, ?, ?, ?, ?, '[]', '{}', ?, 'queued', 'queued')""",
        (
            ref,
            request_key,
            "input-" + ref,
            content_text({"saved": number}),
            revisions_json,
            conditions_archive_json,
            accepted,
        ),
    )
    if time is not None:
        executor_ref = f"{number + 100:048x}"
        receipt_ref = f"{number + 200:048x}"
        conn.execute(
            "UPDATE WorkbenchRunJobs SET state='running', stage='computing', executor_ref=?, started_at=? "
            "WHERE run_ref=?",
            (executor_ref, time, ref),
        )
        conn.execute(
            "INSERT INTO WorkbenchRunReceipts(receipt_ref, run_ref, state, result_json, recorded_at) "
            "VALUES (?, ?, 'complete', '{\"state\":\"complete\",\"candidates\":[],\"error\":null}', ?)",
            (receipt_ref, ref, time),
        )
        conn.execute(
            "UPDATE WorkbenchRunJobs SET state='complete', stage='finished', finished_at=?, error_json='null' "
            "WHERE run_ref=?",
            (time, ref),
        )
    return ref


@pytest.mark.parametrize("field", ("accepted_at", "started_at", "finished_at"))
@pytest.mark.parametrize("order", ("asc", "desc"))
def test_history_uses_expression_index_with_mixed_precision_nulls_and_page_ties(indexed_db, field, order):
    _path, conn = indexed_db
    values = ((1, "2026-10-17T08:00:00.1"), (9, "2026-10-17T08:00:00.100000"),
              (3, "2026-10-17T08:00:00.10"), (8, "2026-10-17T08:00:00"),
              (4, "2026-10-17T08:00:00.000000"), (6, "2026-10-17T08:00:00.09"),
              (2, "2026-10-17T08:00:01"), (7, None), (5, None))
    recorded = []
    for number, time in values:
        accepted = time if time is not None else "2026-10-17T08:00:02"
        ref = _run(conn, number, accepted, time=time)
        recorded.append((ref, accepted if field == "accepted_at" else time))
    conn.commit()
    present = sorted(((ref, datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%f" if "." in time else "%Y-%m-%dT%H:%M:%S"))
                      for ref, time in recorded if time is not None),
                     key=lambda row: (row[1], row[0]), reverse=order == "desc")
    absent = sorted((ref for ref, time in recorded if time is None), reverse=order == "desc")
    expected = [ref for ref, _time in present] + absent

    statements = []
    conn.set_trace_callback(statements.append)
    repo, actual = WorkbenchRunHistoryQueryRepository(conn), []
    try:
        for page in range(1, 4):
            rows = repo.list_jobs(RunHistoryScope(sort=field, order=order, page=page, size=3))
            actual.extend(row["run_ref"] for row in rows)
    finally:
        conn.set_trace_callback(None)
    assert actual == expected

    query = next(sql for sql in statements if "FROM (SELECT j.run_ref" in sql)
    plan = [row[3] for row in conn.execute("EXPLAIN QUERY PLAN " + query)]
    source = next(index for index, detail in enumerate(plan) if "WorkbenchRunJobs" in detail)
    subquery = next(index for index, detail in enumerate(plan) if "SCAN SUBQUERY" in detail or "SCAN j" == detail)
    assert "idx_wb_run_" + field[:-3] + "_sort" in plan[source]
    assert not any("TEMP B-TREE" in detail for detail in plan[source:subquery])


def _operations(conn):
    conn.executescript("""INSERT INTO Parts(part_no,part_name) VALUES ('P','Part');
        INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('DELETE','P',1),('KEEP','P',1);
        INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name)
            VALUES (1,'DELETE-1','DELETE',1,'Turning'),(2,'KEEP-1','KEEP',1,'Turning');
        INSERT INTO Materials(material_id,name) VALUES ('MAT','Material');
        INSERT INTO BatchMaterials(id,batch_id,material_id,required_qty) VALUES (1,'KEEP','MAT',1);
        INSERT INTO BatchMaterialStages(requirement_id,operation_id) VALUES (1,2);""")
    conn.commit()


def test_operation_deletion_searches_child_key_and_keeps_foreign_key_actions(indexed_db):
    _path, conn = indexed_db
    _operations(conn)
    plan = [row[3] for row in conn.execute(
        "EXPLAIN QUERY PLAN DELETE FROM BatchOperations WHERE batch_id=?", ("DELETE",))]
    related = [detail for detail in plan if "BatchMaterialStages" in detail]
    assert related and all("SEARCH" in detail and "idx_material_stage_operation" in detail for detail in related)

    repo = BatchOperationRepository(conn)
    repo.delete_by_batch("DELETE")
    assert [tuple(row) for row in conn.execute("SELECT * FROM BatchMaterialStages")] == [(1, 2)]
    with pytest.raises(AppError) as rejected:
        repo.delete_by_batch("KEEP")
    assert rejected.value.code == ErrorCode.DB_INTEGRITY_ERROR
    assert isinstance(rejected.value.cause, sqlite3.IntegrityError)
    assert conn.execute("SELECT id FROM BatchOperations").fetchone()[0] == 2
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_declared_efficiency_indexes_contract_and_archive_projection(indexed_db):
    _path, conn = indexed_db
    _operations(conn)
    before = production_facts(conn)
    capture = ProductionFactsCapture(conn)
    revisions_record = capture.revisions_record()
    revisions_text = content_text(revisions_record)
    scoped_archive = capture.scoped_archive(())
    scoped_text = content_text(scoped_archive)
    ref = _run(
        conn,
        1,
        "2026-10-17T08:00:00",
        time="2026-10-17T08:01:00.100000",
        revisions_json=revisions_text,
        conditions_archive_json=scoped_text,
    )
    conn.execute(
        """INSERT INTO WorkbenchHistoryEntries(
            entry_ref, timeline, source_kind, state, run_ref, request_key,
            selection_json, times_json, evidence_gaps_json, objective_json
        ) VALUES (?, 'run', 'run', 'complete', ?, 'efficiency-history-0001', '{}', '{}', '[]', '{}')""",
        ("run:" + ref, ref),
    )
    conn.commit()

    assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == CURRENT_SCHEMA_VERSION
    assert contract_issues(SchemaStructure(conn)) == current_schema_contract_issues(
        conn, schema_version=CURRENT_SCHEMA_VERSION) == []
    indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert set(ADDED) <= indexes
    assert "idx_wb_lineage_operation_id_text" not in indexes
    assert {"idx_part_operations_ext_group", "idx_part_operations_part_status"} <= indexes
    assert {"idx_batches_part_no", "idx_external_groups_supplier", "idx_batch_quantity_splits_source"} <= indexes
    assert {
        "idx_wb_outsourcing_receipts_batch",
        "idx_wb_outsourcing_receipts_awaiting",
        "idx_wb_outsourcing_receipts_returned",
        "idx_wb_outsourcing_external_ops",
    } <= indexes
    assert {"idx_schedule_version_page", "idx_schedule_version_span", "idx_schedule_operation_ref_version"} <= indexes
    assert {
        "idx_wb_run_op_cat_batch",
        "idx_wb_run_side_ops_alloc",
        "idx_wb_history_timeline_order",
        "idx_wb_history_run_ref",
        "idx_wb_exec_reports_active_op",
        "idx_wb_exec_reports_active_machine",
        "idx_wb_exec_reports_active_operator",
    } <= indexes
    assert tuple(
        conn.execute(
            "SELECT revisions_json, conditions_archive_json FROM WorkbenchRunJobs WHERE run_ref=?",
            (ref,),
        ).fetchone()
    ) == (revisions_text, scoped_text)
    fresh = ProductionFactsCapture(conn)
    stored_scoped = json.loads(scoped_text)
    validate_production_archive(stored_scoped)
    assert fresh.matches_admitted(stored_scoped)
    assert fresh.matches_recorded(revisions_record)
    # 写入运行账簿与历史目录后生产事实逐字不变：运行与历史目录本身不是生产事实。
    assert production_facts(conn) == before


def test_scoped_process_operations_use_ext_group_index_and_split_identity_triggers(indexed_db):
    _path, conn = indexed_db
    conn.executescript(
        """
        INSERT INTO Parts(part_no, part_name) VALUES ('P1', 'Part 1'), ('P2', 'Part 2'), ('OTHER', 'Other');
        INSERT INTO ExternalGroups(group_id, part_no, start_seq, end_seq, merge_mode)
            VALUES ('G1', 'P1', 2, 2, 'merged');
        INSERT INTO PartOperations(part_no, seq, op_type_name, source, ext_group_id, status) VALUES
            ('P1', 1, 'Turning', 'internal', NULL, 'active'),
            ('P1', 2, 'HeatTreat', 'external', 'G1', 'deleted'),
            ('P2', 1, 'HeatTreat', 'external', 'G1', 'deleted'),
            ('OTHER', 1, 'Milling', 'internal', NULL, 'active');
        """
    )
    conn.commit()
    part_ref = conn.execute(
        "SELECT ref FROM WorkbenchEntityRefs WHERE kind='part' AND entity_key='P1' AND active=1"
    ).fetchone()[0]

    statements = []
    conn.set_trace_callback(statements.append)
    try:
        rows = WorkbenchProcessQueryRepository(conn, part_ref=part_ref).operations()
    finally:
        conn.set_trace_callback(None)
    assert [(row["part_no"], row["seq"], row["status"]) for row in rows] == [
        ("P1", 1, "active"),
        ("P1", 2, "deleted"),
        ("P2", 1, "deleted"),
    ]
    ops_sql = next(sql for sql in statements if "scoped_ops ON scoped_ops.id=o.id" in sql)
    plan = [row[3] for row in conn.execute("EXPLAIN QUERY PLAN " + ops_sql)]
    assert any("idx_part_operations_part" in detail for detail in plan)
    assert any("idx_part_operations_ext_group" in detail for detail in plan)
    assert not any(detail.startswith("SCAN PartOperations") or detail.startswith("SCAN o ") for detail in plan)

    # 新实体的编号或别名撞上遗留的有效编号：遗留编号只停用一次（版本只加 1），新实体拿到唯一有效编号。
    def stale(number, kind, key, alternate):
        ref = f"{number:048x}"
        conn.execute("INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key) VALUES (?, ?, ?, ?)",
                     (ref, kind, key, alternate))
        return ref

    def deactivated_once(ref, kind, alternate):
        assert tuple(conn.execute("SELECT active, revision FROM WorkbenchEntityRefs WHERE ref=?", (ref,)).fetchone()) == (0, 2)
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchEntityRefs WHERE kind=? AND alternate_key=? AND active=1",
                            (kind, alternate)).fetchone()[0] == 1

    named = (("op_type", "OpTypes", "op_type_id", ""), ("resource_team", "ResourceTeams", "team_id", ""),
             ("machine_group", "WorkbenchMachineGroups", "group_id", ""),
             ("shift_profile", "WorkbenchShiftProfiles", "profile_id", ", anchor_date, cycle_days"))
    for number, (kind, table, key, extra) in enumerate(named, 1):
        values = ", '2026-01-01', 7" if extra else ""
        ref = stale(number, kind, "STALE", "dup")
        conn.execute(f"INSERT INTO {table}({key}, name{extra}) VALUES ('NEW', 'dup'{values})")
        deactivated_once(ref, kind, "dup")
        ref = stale(number + 10, kind, "RENAMED", "renamed")  # 编号和别名都撞上同一条遗留编号
        conn.execute(f"UPDATE {table} SET {key}='RENAMED', name='renamed' WHERE {key}='NEW'")
        deactivated_once(ref, kind, "renamed")
    ref = stale(20, "template_operation", "STALE", "P2:9")
    conn.execute("INSERT INTO PartOperations(part_no, seq, op_type_name, source, status) VALUES ('P2', 9, 'Milling', 'internal', 'active')")
    deactivated_once(ref, "template_operation", "P2:9")
