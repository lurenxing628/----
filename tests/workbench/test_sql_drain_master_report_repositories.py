"""合同测试：SQL 排水批次 C（批次/工艺/现场/报表/看板/外协/系统簇）新增的仓储方法。

锁定每个方法的 SQL 语义（返回形状、排序、白名单、上限参数），服务层不再持 conn 直接读写这些表。
夹具用 conftest 的 schema_conn（:memory: + 全量 schema.sql，FK ON，Row）。"""

from __future__ import annotations

import hashlib
import sqlite3

import pytest

from core.services.workbench.master.overview_facts import RELATIONS, SOURCES, WORKFLOW
from data.repositories.workbench_batch_facts_repo import BATCH_FACT_TABLES, WorkbenchBatchFactsRepository
from data.repositories.workbench_dashboard_source_repo import latest_outsourcing_fact_rows, unknown_source_rows
from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository
from data.repositories.workbench_field_query_repo import WorkbenchFieldQueryRepository
from data.repositories.workbench_master_query_repo import (
    LEGACY_ENTITY_KINDS,
    MASTER_OVERVIEW_TABLES,
    WorkbenchMasterQueryRepository,
)
from data.repositories.workbench_outsourcing_repo import WorkbenchOutsourcingRepository
from data.repositories.workbench_preflight_facts_repo import PREFLIGHT_TABLES, WorkbenchPreflightFactsRepository
from data.repositories.workbench_process_hours_repo import WorkbenchProcessHoursRepository
from data.repositories.workbench_process_part_facts_repo import WorkbenchProcessPartFactsRepository
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository
from data.repositories.workbench_report_facts_repo import WorkbenchReportFactsRepository
from data.repositories.workbench_report_validation_repo import WorkbenchReportValidationRepository
from data.repositories.workbench_system_maintenance_repo import WorkbenchSystemMaintenanceRepository
from tests.workbench.process_query_support import ref_for, seed_process


def _seed_resources(conn):
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','车床','PROC-IN')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','张三')")
    conn.commit()


def _hex48(seed):
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:48]


def _receipt(conn, seed, action):
    """写一条满足 CHECK 约束的命令回执，返回 request_key。"""
    key = ("request-key-" + seed).ljust(16, "0")
    conn.execute("INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_hash,outcome_json) VALUES (?,?,?,?,?,?)",
                 (key, hashlib.md5(key.encode("utf-8")).hexdigest(), action, "ctx", hashlib.sha256(key.encode("utf-8")).hexdigest(), "{}"))
    return key


def _batch_operation(conn, seq, source="internal"):
    cursor = conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source) VALUES (?,?,?,?,?)",
                          ("OP" + str(seq), "PROC-B", seq, "车削", source))
    return cursor.lastrowid


def _template_identity(conn, kind, key):
    row = conn.execute("SELECT ref,revision FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? AND active=1", (kind, key)).fetchone()
    return row["ref"], row["revision"]


# ---------------- 批次事实 ----------------

def test_batch_facts_whole_tables_and_batch_row(schema_conn) -> None:
    seed_process(schema_conn)
    repo = WorkbenchBatchFactsRepository(schema_conn)
    tables = repo.whole_tables()
    assert tuple(tables) == BATCH_FACT_TABLES
    assert [row["part_no"] for row in tables["Parts"]] == ["PROC-001", "PROC-002", "PROC-003", "PROC-004", "PROC-%_"], "rowid 序"
    assert tables["Batches"][0]["batch_id"] == "PROC-B" and tables["Schedule"] == []
    assert repo.batch_row("PROC-B")["part_no"] == "PROC-001"
    assert repo.batch_row("NOPE") is None


def test_execution_schema_version_row_and_execution_receipts(schema_conn) -> None:
    repo = WorkbenchExecutionRepository(schema_conn)
    assert repo.schema_version_row() == {"version": 0}
    assert repo.has_execution_receipts() is False
    _receipt(schema_conn, "k1", "outsourcing.confirm")
    assert repo.has_execution_receipts() is False, "只认 execution.* 动作"
    _receipt(schema_conn, "k2", "execution.report")
    assert repo.has_execution_receipts() is True
    schema_conn.execute("DELETE FROM SchemaVersion")
    assert repo.schema_version_row() is None


# ---------------- 现场 ----------------

def test_field_query_resource_index_latest_version_and_batch_part_names(schema_conn) -> None:
    seed_process(schema_conn)
    _seed_resources(schema_conn)
    repo = WorkbenchFieldQueryRepository(schema_conn)
    rows = {(row["kind"], row["entity_key"]): row for row in repo.active_resource_index_rows()}
    assert set(rows) == {("machine", "M1"), ("operator", "O1")}
    assert rows[("machine", "M1")]["label"] == "车床" and rows[("operator", "O1")]["label"] == "张三"
    assert rows[("machine", "M1")]["ref"] == ref_for(schema_conn, "machine", "M1")
    schema_conn.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE kind='operator'")
    assert [row["kind"] for row in repo.active_resource_index_rows()] == ["machine"], "只取 active=1"

    assert repo.latest_schedule_version() is None
    schema_conn.executemany("INSERT INTO ScheduleHistory(version,strategy) VALUES (?,?)", [(3, "s"), (7, "s"), (5, "s")])
    assert repo.latest_schedule_version() == 7

    assert repo.batch_part_names() == {"PROC-B": "轴套"}


# ---------------- 基础资料 ----------------

def test_master_overview_whitelist_matches_service_derivation() -> None:
    derived = tuple(dict.fromkeys(table for values in SOURCES.values() for table in values)) + RELATIONS + WORKFLOW + ("WorkbenchEntityRefs",)
    assert MASTER_OVERVIEW_TABLES == derived


def test_master_overview_tables_reads_present_tables_by_description(schema_conn) -> None:
    seed_process(schema_conn)
    repo = WorkbenchMasterQueryRepository(schema_conn)
    tables, present = repo.overview_tables()
    assert tuple(tables) == MASTER_OVERVIEW_TABLES and set(MASTER_OVERVIEW_TABLES) <= present
    assert [row["part_no"] for row in tables["Parts"]][:2] == ["PROC-001", "PROC-002"]
    schema_conn.row_factory = None
    tables_plain, _ = WorkbenchMasterQueryRepository(schema_conn).overview_tables()
    assert tables_plain["Parts"] == tables["Parts"], "行 dict 按游标列名构造，不依赖 row_factory"
    schema_conn.row_factory = sqlite3.Row
    schema_conn.execute("DROP TABLE WorkCalendar")
    tables, present = repo.overview_tables()
    assert "WorkCalendar" not in tables and "WorkCalendar" not in present


def test_master_legacy_entity_row_uses_fixed_sql_per_kind(schema_conn) -> None:
    seed_process(schema_conn)
    _seed_resources(schema_conn)
    repo = WorkbenchMasterQueryRepository(schema_conn)
    assert set(LEGACY_ENTITY_KINDS) == {"machine", "operator", "op_type", "part", "supplier", "batch"}
    assert repo.legacy_entity_row("part", "PROC-001")["part_name"] == "轴套"
    assert repo.legacy_entity_row("op_type", "PROC-IN")["category"] == "internal"
    assert repo.legacy_entity_row("machine", "M1")["name"] == "车床"
    assert repo.legacy_entity_row("operator", "O1")["name"] == "张三"
    assert repo.legacy_entity_row("supplier", "PROC-S")["name"] == "热处理厂"
    assert repo.legacy_entity_row("batch", "PROC-B")["quantity"] == 17
    assert repo.legacy_entity_row("part", "NOPE") is None
    with pytest.raises(ValueError):
        repo.legacy_entity_row("Parts", "PROC-001")


# ---------------- 预检 ----------------

def test_preflight_tables_and_read_whole_table_whitelist(schema_conn) -> None:
    seed_process(schema_conn)
    repo = WorkbenchPreflightFactsRepository(schema_conn)
    tables = repo.preflight_tables()
    assert tuple(tables) == PREFLIGHT_TABLES
    assert tables["Batches"][0]["batch_id"] == "PROC-B" and isinstance(tables["Parts"][0], dict)

    raw = repo.read_whole_table("Parts")
    expected = [tuple(row) for row in schema_conn.execute("SELECT * FROM Parts ORDER BY rowid")]
    assert raw == expected and all(type(row) is tuple for row in raw)
    with pytest.raises(ValueError):
        repo.read_whole_table("NoSuchTable")
    with pytest.raises(ValueError):
        repo.read_whole_table('Parts" WHERE 1; --')
    schema_conn.execute('CREATE TABLE "odd""name"(x)')
    schema_conn.execute('INSERT INTO "odd""name" VALUES (1)')
    assert WorkbenchPreflightFactsRepository(schema_conn).read_whole_table('odd"name') == [(1,)], "表名在仓储内引号化"


# ---------------- 工艺：工时文件写入 ----------------

def test_process_hours_guarded_updates(schema_conn) -> None:
    seed_process(schema_conn)
    repo = WorkbenchProcessHoursRepository(schema_conn)
    op20 = schema_conn.execute("SELECT id FROM PartOperations WHERE part_no='PROC-001' AND seq=20").fetchone()["id"]
    ref, revision = _template_identity(schema_conn, "template_operation", str(op20))
    assert repo.update_operation_hours(op20, {"setup_hours": 1.5, "ext_days": 4.0}, ref=ref, revision=revision) == 1
    row = schema_conn.execute("SELECT setup_hours,ext_days FROM PartOperations WHERE id=?", (op20,)).fetchone()
    assert (row["setup_hours"], row["ext_days"]) == (1.5, 4.0)
    ref, revision = _template_identity(schema_conn, "template_operation", str(op20))
    assert repo.update_operation_hours(op20, {"unit_hours": 9}, ref=ref, revision=revision + 1) == 0, "修订不符不写"
    assert schema_conn.execute("SELECT unit_hours FROM PartOperations WHERE id=?", (op20,)).fetchone()["unit_hours"] == 0
    with pytest.raises(ValueError):
        repo.update_operation_hours(op20, {"part_no": "X"}, ref=ref, revision=revision)
    with pytest.raises(ValueError):
        repo.update_operation_hours(op20, {}, ref=ref, revision=revision)

    gref, grevision = _template_identity(schema_conn, "template_external_group", "PROC-G")
    assert repo.update_group_cycle("PROC-G", {"total_days": 9.5}, ref=gref, revision=grevision) == 1
    assert schema_conn.execute("SELECT total_days FROM ExternalGroups WHERE group_id='PROC-G'").fetchone()[0] == 9.5
    assert repo.update_group_cycle("PROC-G", {"total_days": 1}, ref="stale-ref", revision=grevision) == 0
    with pytest.raises(ValueError):
        repo.update_group_cycle("PROC-G", {"remark": "x"}, ref=gref, revision=grevision)


# ---------------- 工艺：零件动作事实 ----------------

def test_process_part_facts_rows(schema_conn) -> None:
    seed_process(schema_conn)
    repo = WorkbenchProcessPartFactsRepository(schema_conn)
    part_ref = ref_for(schema_conn, "part", "PROC-001")
    assert repo.part("PROC-001")["part_name"] == "轴套" and repo.part("NOPE") is None
    assert repo.identity(part_ref)["kind"] == "part" and repo.identity("nope") is None
    assert [row["seq"] for row in repo.operations("PROC-001")] == [10, 20, 30]
    assert [row["group_id"] for row in repo.groups("PROC-001")] == ["PROC-G"]
    assert [row["batch_id"] for row in repo.batches("PROC-001")] == ["PROC-B"]
    assert repo.foreign_group_members("PROC-001") == []
    schema_conn.execute("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,ext_group_id,status)
        VALUES ('PROC-002',10,'PROC-EX','热处理','external','PROC-G','active')""")
    foreign = repo.foreign_group_members("PROC-001")
    assert [(row["part_no"], row["seq"]) for row in foreign] == [("PROC-002", 10)]
    identities = repo.template_identities("PROC-001")
    assert sorted(row["kind"] for row in identities) == ["template_external_group"] + ["template_operation"] * 3
    assert [row["ref"] for row in identities] == sorted(row["ref"] for row in identities), "ORDER BY ref"
    assert repo.workflow(part_ref) == [] and repo.confirmations(part_ref) == []
    schema_conn.execute("INSERT INTO WorkbenchProcessWorkflow(part_ref) VALUES (?)", (part_ref,))
    op_refs = sorted(row["ref"] for row in identities if row["kind"] == "template_operation")
    signature, confirmed_at = hashlib.sha256(b"sig").hexdigest(), "2026-01-01T00:00:00"
    schema_conn.executemany("INSERT INTO WorkbenchProcessOperationConfirmations(part_ref,operation_ref,stage,signature,confirmed_at) VALUES (?,?,?,?,?)",
                            [(part_ref, op_refs[1], "source", signature, confirmed_at), (part_ref, op_refs[0], "source", signature, confirmed_at),
                             (part_ref, op_refs[0], "hours", signature, confirmed_at)])
    assert repo.workflow(part_ref)[0]["part_ref"] == part_ref
    assert [(row["operation_ref"], row["stage"]) for row in repo.confirmations(part_ref)] == [
        (op_refs[0], "hours"), (op_refs[0], "source"), (op_refs[1], "source")]


def test_process_query_template_and_reference_rows(schema_conn) -> None:
    seed_process(schema_conn)
    repo = WorkbenchProcessQueryRepository(schema_conn)
    assert repo.part_by_no("PROC-001")["remark"] == "旧备注必须保留" and repo.part_by_no("NOPE") is None
    operations = repo.template_operations_with_refs("PROC-001")
    assert [row["seq"] for row in operations] == [10, 20, 30] and all(row["ref"] for row in operations)
    assert repo.template_operations_with_refs("PROC-004")[0]["status"] == "deleted", "停用工序也在快照里"
    groups = repo.template_groups_with_refs("PROC-001")
    assert [row["group_id"] for row in groups] == ["PROC-G"] and groups[0]["ref"] == ref_for(schema_conn, "template_external_group", "PROC-G")
    assert repo.foreign_group_use_exists("PROC-001") is False
    schema_conn.execute("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,ext_group_id,status)
        VALUES ('PROC-002',10,'PROC-EX','热处理','external','PROC-G','active')""")
    assert repo.foreign_group_use_exists("PROC-001") is True

    types = {row["op_type_id"]: row for row in repo.op_type_reference_rows()}
    assert types["PROC-EX"] == {"op_type_id": "PROC-EX", "name": "热处理", "category": "external"}
    assert repo.supplier_reference_rows() == [{"supplier_id": "PROC-S", "name": "热处理厂"}]
    assert {row["op_type_id"]: row["category"] for row in repo.op_type_categories()} == {"PROC-IN": "internal", "PROC-Q": "internal", "PROC-EX": "external"}
    assert repo.supplier_status_rows() == [{"supplier_id": "PROC-S", "status": "active", "inactive_reason": None}]
    schema_conn.execute("INSERT INTO WorkbenchSupplierProfiles(supplier_id,inactive_reason) VALUES ('PROC-S','disabled')")
    assert repo.supplier_status_rows()[0]["inactive_reason"] == "disabled"


# ---------------- 报表 ----------------

def test_report_facts_schedule_count_and_resource_names(schema_conn) -> None:
    seed_process(schema_conn)
    _seed_resources(schema_conn)
    repo = WorkbenchReportFactsRepository(schema_conn)
    assert repo.schedule_operation_count(1) == 0
    op_id = _batch_operation(schema_conn, 10)
    schema_conn.executemany("INSERT INTO Schedule(op_id,start_time,end_time,version) VALUES (?,?,?,?)", [
        (op_id, "2026-01-01 08:00:00", "2026-01-01 09:00:00", 1), (op_id, "2026-01-02 08:00:00", "2026-01-02 09:00:00", 2)])
    assert repo.schedule_operation_count(1) == 1 and repo.schedule_operation_count(2) == 1

    assert repo.resource_names("machine", ["M1", "M9"]) == {"M1": "车床"}
    assert repo.resource_names("operator", ["O1"]) == {"O1": "张三"}
    assert repo.resource_names("machine", []) == {}
    with pytest.raises(ValueError):
        repo.resource_names("batch", ["PROC-B"])
    schema_conn.executemany("INSERT INTO Machines(machine_id,name) VALUES (?,?)", [("MX" + str(i).zfill(3), "机" + str(i)) for i in range(450)])
    names = repo.resource_names("machine", ["MX" + str(i).zfill(3) for i in range(450)] + ["M1"])
    assert len(names) == 451 and names["MX449"] == "机449", "超过 400 个键分批查询"


def test_report_validation_rows(schema_conn) -> None:
    seed_process(schema_conn)
    _seed_resources(schema_conn)
    repo = WorkbenchReportValidationRepository(schema_conn)
    machine_ref, operator_ref = ref_for(schema_conn, "machine", "M1"), ref_for(schema_conn, "operator", "O1")
    rows = {row["ref"]: row for row in repo.entity_rows_with_machine_type([operator_ref, machine_ref, machine_ref])}
    assert set(rows) == {machine_ref, operator_ref}
    assert rows[machine_ref]["machine_type"] == "PROC-IN" and rows[operator_ref]["machine_type"] is None
    assert rows[machine_ref]["kind"] == "machine" and rows[machine_ref]["entity_key"] == "M1"
    assert repo.entity_rows_with_machine_type([]) == []

    ids = [_batch_operation(schema_conn, seq) for seq in (10, 20, 30)]
    successors = repo.successor_operation_rows("PROC-B", None, 10)
    assert [row["id"] for row in successors] == ids[1:]
    assert successors[0]["operation_ref"] == schema_conn.execute(
        "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=?", (str(ids[1]),)).fetchone()[0]
    assert repo.successor_operation_rows("PROC-B", "piece-x", 10) == [], "piece_id 用 IS 精确匹配"
    assert repo.successor_operation_rows("PROC-B", None, 30) == []

    key = _receipt(schema_conn, "adopt", "calibration.adopt")
    template_ref = ref_for(schema_conn, "template_operation", "1")
    schema_conn.execute("""INSERT INTO WorkbenchCalibrationAdoptions(adoption_ref,template_operation_ref,request_key,
        template_revision_before,template_revision_after,new_unit_hours,reason,declared_operator,confirmed,application_operator,
        adopted_at,generated_at,method_version,sample_count,evidence_json,template_before,template_after)
        VALUES (?,?,?,1,2,0.5,'r','op',1,'app','t','t','v1',5,'{"samples":[{"report_refs":["rep-1"]}]}','{}','{}')""",
        (_hex48("adopt-1"), template_ref, key))
    assert [row["adoption_ref"] for row in repo.calibration_adoptions_mentioning("rep-1")] == [_hex48("adopt-1")]
    assert set(repo.calibration_adoptions_mentioning("rep-1")[0]) == {"adoption_ref", "template_operation_ref", "evidence_json"}
    assert repo.calibration_adoptions_mentioning("rep-9") == []


# ---------------- 看板 / 外协 ----------------

def test_outsourcing_repo_clock_and_confirm_receipts(schema_conn) -> None:
    repo = WorkbenchOutsourcingRepository(schema_conn)
    assert repo.plan_identity_revision() == 1
    schema_conn.execute("UPDATE WorkbenchPlanIdentityClock SET revision=5 WHERE singleton=1")
    assert repo.plan_identity_revision() == 5
    assert repo.has_confirm_receipts() is False
    _receipt(schema_conn, "k1", "execution.report")
    assert repo.has_confirm_receipts() is False
    _receipt(schema_conn, "k2", "outsourcing.confirm")
    assert repo.has_confirm_receipts() is True


def test_dashboard_source_latest_fact_and_unknown_sources(schema_conn) -> None:
    seed_process(schema_conn)
    outsourcing_ref = _hex48("os-1")
    assert latest_outsourcing_fact_rows(schema_conn, outsourcing_ref) == []
    ids = [_batch_operation(schema_conn, 10, "internal"), _batch_operation(schema_conn, 20, None), _batch_operation(schema_conn, 30, "bogus")]

    def operation_ref(op_id):
        return schema_conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=?", (str(op_id),)).fetchone()[0]

    batch_ref, supplier_ref = ref_for(schema_conn, "batch", "PROC-B"), ref_for(schema_conn, "supplier", "PROC-S")
    schema_conn.execute("""INSERT INTO WorkbenchOutsourcingReceipts(outsourcing_ref,target_kind,batch_ref,supplier_ref,origin_json,identity_json,created_at)
        VALUES (?,'single',?,?,'{}','{}','t')""", (outsourcing_ref, batch_ref, supplier_ref))
    schema_conn.execute("INSERT INTO WorkbenchOutsourcingMembers(operation_ref,outsourcing_ref) VALUES (?,?)", (operation_ref(ids[2]), outsourcing_ref))
    for sequence in (1, 2):
        key = _receipt(schema_conn, "os-" + str(sequence), "outsourcing.confirm")
        schema_conn.execute("""INSERT INTO WorkbenchOutsourcingFacts(fact_ref,outsourcing_ref,sequence,previous_fact_ref,sent,planned,returned,
            confirmed_state,declared_operator,local_operator,reason,recorded_at,before_json,source_facts_json,request_key)
            VALUES (?,?,?,?,'2026-01-01','2026-01-05',NULL,'awaiting_confirmation','a','b','r','2026-01-02','{}','{}',?)""",
            (_hex48("f-" + str(sequence)), outsourcing_ref, sequence, _hex48("f-1") if sequence == 2 else None, key))
    latest = latest_outsourcing_fact_rows(schema_conn, outsourcing_ref)
    assert [row["fact_ref"] for row in latest] == [_hex48("f-2")] and latest[0]["sequence"] == 2

    unknown = unknown_source_rows(schema_conn, 10)
    assert [row["business_code"] for row in unknown] == ["OP20", "OP30"]
    assert [row["source"] for row in unknown] == [None, "bogus"]
    assert all(row["batch_ref"] == batch_ref for row in unknown)
    assert [row["outsourcing_ref"] for row in unknown] == [None, outsourcing_ref], "带出已登记的外协编号"
    assert [row["operation_ref"] for row in unknown] == [operation_ref(ids[1]), operation_ref(ids[2])]
    assert len(unknown_source_rows(schema_conn, 1)) == 1, "LIMIT 由调用方传入"


# ---------------- 系统维护 ----------------

def test_system_maintenance_cleanup_audit_rows(schema_conn) -> None:
    repo = WorkbenchSystemMaintenanceRepository(schema_conn)
    assert repo.cleanup_audit_rows(5) == []
    schema_conn.executemany("INSERT INTO OperationLogs(log_level,module,action,detail,error_message) VALUES (?,?,?,?,?)", [
        ("INFO", "system", "cleanup", '{"removed_count":1}', None),
        ("INFO", "backup", "cleanup", "{}", None),
        ("ERROR", "system", "logs_cleanup", None, "boom"),
        ("INFO", "system", "restore", "{}", None),
    ])
    rows = repo.cleanup_audit_rows(5)
    assert [(row["action"], row["log_level"], row["error_message"]) for row in rows] == [("logs_cleanup", "ERROR", "boom"), ("cleanup", "INFO", None)]
    assert set(rows[0]) == {"id", "log_time", "log_level", "module", "action", "detail", "error_message"}
    assert [row["action"] for row in repo.cleanup_audit_rows(1)] == ["logs_cleanup"], "id 倒序取 limit 条"
