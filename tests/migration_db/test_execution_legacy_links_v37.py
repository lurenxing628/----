"""v36 history survives the backed-up v37 upgrade and failed migration rollback."""

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.database import ensure_schema
from core.infrastructure.material_stages_schema import objects as material_objects
from core.infrastructure.migration_state import current_schema_contract_issues, set_schema_version
from core.infrastructure.migrations import v32, v37
from core.infrastructure.workbench_execution_ledger_schema import (
    execution_ledger_contract_issues,
    execution_ledger_migration_contract_issues,
    execution_ledger_objects,
    install_execution_ledger,
)
from core.models.workbench_command import WorkbenchCommandOutcome
from core.services.workbench.commands import WorkbenchCommandService
from data.repositories.workbench_execution_report_repo import WorkbenchExecutionReportRepository, new_ref
from tests.workbench.execution_ledger_migration_support import connect, snapshot, without_version
from tests.workbench.execution_ledger_support import START, LedgerCase
from tests.workbench.flexible_migration_support import assert_migrated_legacy_ddl

# Freeze the changed v36 tables independently of the current DDL builder.
_OLD_REPORTS = """CREATE TABLE WorkbenchProductionReports (
    report_ref TEXT NOT NULL CHECK(length(report_ref) = 48 AND report_ref NOT GLOB '*[^0-9a-f]*') PRIMARY KEY,
    report_no TEXT NOT NULL UNIQUE CHECK(length(report_no) BETWEEN 1 AND 64),
    operation_ref TEXT NOT NULL, recorded_against_task_ref TEXT NOT NULL,
    recorded_against_plan_ref TEXT NOT NULL, source TEXT NOT NULL CHECK(source IN ('manual', 'excel')),
    legacy_fact_ref TEXT UNIQUE, recorded_at TEXT NOT NULL,
    FOREIGN KEY(operation_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
    FOREIGN KEY(recorded_against_task_ref) REFERENCES WorkbenchTaskRefs(ref),
    FOREIGN KEY(recorded_against_plan_ref) REFERENCES WorkbenchPlanSourceRefs(ref),
    FOREIGN KEY(legacy_fact_ref) REFERENCES WorkbenchExecutionLegacyFacts(legacy_fact_ref))"""
_OLD_REVIEWS = """CREATE TABLE BatchMaterialReviews (
    requirement_id INTEGER PRIMARY KEY REFERENCES BatchMaterials(id) ON DELETE CASCADE,
    batch_quantity INTEGER NOT NULL CHECK(batch_quantity >= 0))"""


def _ddl(sql):
    kind = "TABLE" if sql.startswith("CREATE TABLE") else "INDEX" if sql.startswith("CREATE INDEX") else "TRIGGER"
    return sql.replace("CREATE " + kind, "CREATE " + kind + " IF NOT EXISTS", 1) + ";\n"


def _old_schema():
    text = (Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8")
    ledger, materials = execution_ledger_objects(), material_objects()
    for before, after in ((ledger["WorkbenchProductionReports"], _OLD_REPORTS), (materials["BatchMaterialReviews"], _OLD_REVIEWS)):
        assert _ddl(before) in text
        text = text.replace(_ddl(before), _ddl(after))
    for sql in (ledger["idx_wb_execution_reports_legacy"], ledger["wb_execution_legacy_link_active_unique"],
                materials["wb_material_quantity_basis"]):
        assert _ddl(sql) in text
        text = text.replace(_ddl(sql), "")
    return text


def _persist(case, row, key, *, void=False):
    repo = WorkbenchExecutionReportRepository(case.conn)
    def mutate(_):
        if void:
            repo.append_void(row, request_key=key)
        else:
            repo.append(row, request_key=key)
        return WorkbenchCommandOutcome("committed", {"report_ref": row["report_ref"]})
    return WorkbenchCommandService(case.conn).execute(request_key=key, action="execution.fixture",
        context_ref=row["report_ref"], normalized_input=row, guard=lambda: None, mutate=mutate)


@pytest.fixture
def old_case(tmp_path):
    conn = connect(tmp_path / "v36-with-report-history.sqlite")
    conn.executescript(_old_schema())
    set_schema_version(conn, 36)
    conn.executescript("""INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning');
        INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1');
        INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator');
        INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1');
        INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part');
        INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B1','P1',10);
        INSERT INTO Materials(material_id,name) VALUES ('MAT1','Material');
        INSERT INTO BatchMaterials(id,batch_id,material_id,required_qty,available_qty,ready_status)
            VALUES (1,'B1','MAT1',10,10,'yes');
        INSERT INTO BatchMaterialReviews VALUES (1,10);""")
    case = LedgerCase(conn)
    case.op_id = case.op()
    case.plan(1, [case.op_id])
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=10)
    task = case.task(1, case.op_id)
    operation = conn.execute("SELECT r.operation_ref FROM WorkbenchTaskRefs t JOIN WorkbenchPlanSourceRefs r ON r.ref=t.row_ref WHERE t.ref=?", (task,)).fetchone()[0]
    link = conn.execute("SELECT legacy_fact_ref FROM WorkbenchExecutionLegacyFacts WHERE event_type='finish'").fetchone()[0]
    row = dict(report_ref=new_ref(), report_no="original-legacy-supplement", operation_ref=operation,
        recorded_against_task_ref=task, recorded_against_plan_ref=case.plan_ref(1), source="manual",
        legacy_fact_ref=link, recorded_at=START, revision_ref=new_ref(), sequence=1, previous_revision_ref=None,
        action="create", values=case.values(10), reason="Original supplement", local_operator="original-user",
        declared_operator="foreman", revision_at=START)
    _persist(case, row, "old-v36-report-create-0001")
    revised = dict(row, sequence=2, revision_ref=new_ref(), previous_revision_ref=row["revision_ref"],
        action="correct", reason="Original correction", values=case.values(10, effective_processing_hours=1))
    _persist(case, revised, "old-v36-report-correct-0001")
    _persist(case, dict(void_fact_ref=new_ref(), report_ref=row["report_ref"], original_revision_ref=revised["revision_ref"],
        reason="Original withdrawal", local_operator="original-user", declared_operator="foreman", recorded_at=START),
        "old-v36-report-void-0001", void=True)
    case.legacy_ref = link
    try:
        yield case
    finally:
        conn.close()


def _new_supplement(case):
    return case.command("create", case.task(1, case.op_id),
        case.values(10, legacy_fact_ref=case.legacy_ref, reason="Rechecked original hours"))


def test_real_v36_upgrade_preserves_every_value_type_clock_and_receipt(old_case, tmp_path):
    case = old_case
    before = snapshot(case.conn)
    path = case.conn.execute("PRAGMA database_list").fetchone()[2]
    backup_dir = tmp_path / "backups"
    ensure_schema(path, backup_dir=str(backup_dir))
    assert case.conn.execute("SELECT version FROM SchemaVersion").fetchone()[0] == 37
    assert without_version(snapshot(case.conn)) == without_version(before)
    assert current_schema_contract_issues(case.conn) == []
    assert case.conn.execute("PRAGMA foreign_key_check").fetchall() == []
    backups = list(backup_dir.glob("*.db"))
    assert len(backups) == 1
    with sqlite3.connect(str(backups[0])) as saved:
        assert snapshot(saved) == before
    saved = _new_supplement(case)
    projected = case.ledger.get_task(case.task(1, case.op_id))
    assert projected.known_completed_quantity == 10 and projected.data_quality == "complete"
    assert len(projected.reports) == 1 and len(projected.voided_reports) == 1
    assert projected.reports[0].report_ref == saved["data"]["rows"][0]["report_ref"]


def test_v37_is_idempotent_and_material_review_trigger_preserves_existing_basis(old_case):
    case = old_case
    v37.run(case.conn)
    before = list(case.conn.iterdump())
    v37.run(case.conn)
    assert list(case.conn.iterdump()) == before
    case.conn.execute("UPDATE Batches SET quantity=12 WHERE batch_id='B1'")
    assert case.conn.execute("SELECT batch_quantity FROM BatchMaterialReviews WHERE requirement_id=1").fetchone()[0] == 10
    assert case.conn.execute("SELECT ready_status FROM Batches WHERE batch_id='B1'").fetchone()[0] == "no"
    case.conn.rollback()


def test_v37_failure_after_report_rebuild_rolls_back_all_schema_history_and_clock(old_case, monkeypatch):
    case = old_case
    before = list(case.conn.iterdump())
    def fail(_):
        raise RuntimeError("injected before material review migration")
    monkeypatch.setattr(v37, "_migrate_material_reviews", fail)
    with pytest.raises(RuntimeError, match="injected"):
        v37.run(case.conn)
    assert list(case.conn.iterdump()) == before
    assert case.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert case.conn.execute("SELECT count(*) FROM sqlite_temp_master").fetchone()[0] == 0


def test_v37_rejects_missing_report_history_contract_without_partial_changes(old_case):
    case = old_case
    case.conn.execute("DROP TRIGGER wb_execution_voids_no_delete")
    case.conn.commit()
    before = list(case.conn.iterdump())
    with pytest.raises(RuntimeError, match="incomplete execution"):
        v37.run(case.conn)
    assert list(case.conn.iterdump()) == before


def _frozen_case(path, version):
    conn = connect(path)
    fixture = Path(__file__).resolve().parents[1] / "workbench" / "fixtures" / f"schema-v{version}.sql"
    conn.executescript(fixture.read_text(encoding="utf-8"))
    set_schema_version(conn, version)
    conn.executescript("""INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning');
        INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1');
        INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator');
        INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1');
        INSERT INTO Parts(part_no,part_name) VALUES ('P1','Original part');
        INSERT INTO Batches(batch_id,part_no,quantity,remark) VALUES ('B1','P1',10,'original batch note');""")
    conn.execute("UPDATE Parts SET remark=? WHERE part_no='P1'", (sqlite3.Binary(b"\x00original-v25-v31\xff"),))
    case = LedgerCase(conn)
    case.op_id = case.op()
    case.plan(1, [case.op_id])
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=10)
    task = case.task(1, case.op_id)
    row = dict(report_ref=new_ref(), report_no="old-version-supplement",
        operation_ref=conn.execute("SELECT operation_ref FROM WorkbenchPlanSourceRefs WHERE kind='schedule_row' AND ref=(SELECT row_ref FROM WorkbenchTaskRefs WHERE ref=?)", (task,)).fetchone()[0],
        recorded_against_task_ref=task, recorded_against_plan_ref=case.plan_ref(1), source="manual",
        legacy_fact_ref=conn.execute("SELECT legacy_fact_ref FROM WorkbenchExecutionLegacyFacts WHERE event_type='finish'").fetchone()[0],
        recorded_at=START, revision_ref=new_ref(), sequence=1, previous_revision_ref=None, action="create",
        values=case.values(10), reason="Original historical supplement", local_operator="original-user",
        declared_operator="foreman", revision_at=START)
    _persist(case, row, f"frozen-v{version}-report-create-0001")
    return case


@pytest.mark.parametrize("version", range(25, 32))
def test_frozen_v25_to_v31_upgrade_preserves_original_history_and_backup(tmp_path, version):
    path = tmp_path / f"frozen-v{version}.sqlite"
    case = _frozen_case(path, version)
    try:
        before = snapshot(case.conn)
        # A historical install may inspect this shape, while runtime remains strict.
        assert execution_ledger_contract_issues(case.conn)
        assert execution_ledger_migration_contract_issues(case.conn) == []
        if version == 25:
            case.conn.execute("BEGIN")
            install_execution_ledger(case.conn)
            case.conn.commit()
            assert snapshot(case.conn) == before
        backup_dir = tmp_path / "backups"
        ensure_schema(str(path), backup_dir=str(backup_dir))
        assert current_schema_contract_issues(case.conn) == []
        after = snapshot(case.conn)
        for table, rows in before.items():
            if table != "SchemaVersion":
                assert after[table] == rows, table
        assert case.conn.execute("SELECT version FROM SchemaVersion").fetchone()[0] == 37
        assert case.conn.execute("PRAGMA foreign_key_check").fetchall() == []
        backups = list(backup_dir.glob("*.db"))
        assert len(backups) == 1
        with sqlite3.connect(str(backups[0])) as saved:
            assert snapshot(saved) == before
        projected = case.ledger.get_task(case.task(1, case.op_id))
        assert projected.known_completed_quantity == 10 and projected.data_quality == "complete"
    finally:
        case.conn.close()


@pytest.mark.parametrize("version", [28, 31])
def test_historical_installer_rejects_partial_ledger_without_repairing_it(tmp_path, version):
    path = tmp_path / f"incomplete-v{version}.sqlite"
    case = _frozen_case(path, version)
    try:
        case.conn.execute("DROP TRIGGER wb_execution_reports_no_delete")
        case.conn.commit()
        before = list(case.conn.iterdump())
        assert execution_ledger_migration_contract_issues(case.conn)
        with pytest.raises(RuntimeError, match="calibration adoption|prerequisites"):
            ensure_schema(str(path), backup_dir=str(tmp_path / "backups"))
        assert list(case.conn.iterdump()) == before
        assert case.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        case.conn.close()


def test_old_upgrade_failure_after_preflight_restores_original_database_backup(tmp_path, monkeypatch):
    path = tmp_path / "v31-failed-real-upgrade.sqlite"
    case = _frozen_case(path, 31)
    before = snapshot(case.conn)
    case.conn.close()
    original = v37._migrate_material_reviews
    calls = 0
    def fail_on_real_upgrade(conn):
        nonlocal calls
        calls += 1
        original(conn)
        if calls == 2:
            raise RuntimeError("injected after successful preflight and real report rebuild")
    monkeypatch.setattr(v37, "_migrate_material_reviews", fail_on_real_upgrade)
    backup_dir = tmp_path / "backups"
    with pytest.raises(RuntimeError, match="injected"):
        ensure_schema(str(path), backup_dir=str(backup_dir))
    assert calls == 2
    with connect(path) as restored:
        assert snapshot(restored) == before
        assert restored.execute("PRAGMA foreign_key_check").fetchall() == []
        assert restored.execute("SELECT version FROM SchemaVersion").fetchone()[0] == 31
    backups = list(backup_dir.glob("*.db"))
    assert len(backups) == 1
    with sqlite3.connect(str(backups[0])) as saved:
        assert snapshot(saved) == before


def _add_mixed_ledger_objects(conn, shape):
    declared = execution_ledger_objects()
    if shape in ("index", "both"):
        conn.execute(declared["idx_wb_execution_reports_legacy"])
    if shape in ("bad_trigger", "both"):
        conn.execute("""CREATE TRIGGER wb_execution_legacy_link_active_unique
            BEFORE INSERT ON WorkbenchProductionReports BEGIN SELECT 1; END""")
    if shape == "current_trigger":
        conn.execute(declared["wb_execution_legacy_link_active_unique"])
    conn.commit()


@pytest.mark.parametrize("shape", ["index", "bad_trigger", "both", "current_trigger"])
def test_old_ledger_with_v37_objects_is_not_a_valid_historical_migration_contract(tmp_path, shape):
    path = tmp_path / "mixed-v31.sqlite"
    case = _frozen_case(path, 31)
    try:
        _add_mixed_ledger_objects(case.conn, shape)
        before = list(case.conn.iterdump())
        assert execution_ledger_contract_issues(case.conn)
        legacy = execution_ledger_contract_issues(case.conn, legacy_link_unique=True)
        assert any(issue.startswith("unexpected_execution_ledger:") for issue in legacy)
        assert execution_ledger_migration_contract_issues(case.conn)
        # v32 must roll back its source-table install when the ledger is mixed.
        with pytest.raises(RuntimeError, match="prerequisites"):
            v32.run(case.conn)
        assert list(case.conn.iterdump()) == before
        with pytest.raises(RuntimeError, match="prerequisites"):
            ensure_schema(str(path), backup_dir=str(tmp_path / "backups"))
        assert list(case.conn.iterdump()) == before
        assert case.conn.execute("SELECT version FROM SchemaVersion").fetchone()[0] == 31
    finally:
        case.conn.close()


def test_v37_does_not_replace_unknown_active_link_trigger_on_old_report_schema(old_case):
    case = old_case
    _add_mixed_ledger_objects(case.conn, "both")
    before = list(case.conn.iterdump())
    with pytest.raises(RuntimeError, match="incomplete execution report history"):
        v37.run(case.conn)
    assert list(case.conn.iterdump()) == before
    assert case.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


@pytest.fixture
def ddl_proof_case(tmp_path):
    path = tmp_path / "v31-ddl-proof.sqlite"
    case = _frozen_case(path, 31)
    before = [tuple(row) for row in case.conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")]
    ensure_schema(str(path), backup_dir=str(tmp_path / "backups"))
    try:
        yield case.conn, before
    finally:
        case.conn.close()


def test_migration_ddl_proof_checks_declared_delta_and_preserves_all_stored_rows(ddl_proof_case):
    conn, before = ddl_proof_case
    original = snapshot(conn)
    assert_migrated_legacy_ddl(conn, before)
    assert snapshot(conn) == original


@pytest.mark.parametrize("damage", ["old_report", "old_index_missing", "old_other", "new_report_index"])
def test_migration_ddl_proof_rejects_changes_outside_the_declared_report_delta(ddl_proof_case, damage):
    conn, before = ddl_proof_case
    if damage == "old_report":
        before = [row[:3] + (row[3].replace("legacy_fact_ref TEXT UNIQUE", "legacy_fact_ref BLOB UNIQUE"),)
                  if row[1] == "WorkbenchProductionReports" else row for row in before]
    elif damage == "old_index_missing":
        before = [row for row in before if row[1] != "sqlite_autoindex_WorkbenchProductionReports_3"]
    elif damage == "old_other":
        before = [row[:3] + (row[3].replace("TEXT", "BLOB", 1),) if row[1] == "Parts" else row for row in before]
    else:
        conn.execute("CREATE INDEX unknown_report_index ON WorkbenchProductionReports(recorded_at)")
    original = list(conn.iterdump())
    with pytest.raises(AssertionError):
        assert_migrated_legacy_ddl(conn, before)
    assert list(conn.iterdump()) == original
