"""新建库与 DDL 模块基线库结构一致，且低版本库阻断启动。"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION, MigrationContractError
from tests._support.paths import REPO_ROOT
from tools.generate_schema_sql import build_baseline_database, generate_schema_text

SCHEMA_PATH = REPO_ROOT / "schema.sql"

_WS_RE = re.compile(r"\s+")
_IF_NOT_EXISTS_RE = re.compile(r"\bIF\s+NOT\s+EXISTS\b", re.IGNORECASE)
_CHECK_RE = re.compile(r"\bCHECK\s*\(", re.IGNORECASE)


def test_identical_schema_text_is_normalized_once_but_changed_ddl_is_not_reused(monkeypatch):
    from core.infrastructure import workbench_metadata_schema as schema

    original, calls = schema._strip_line_comments, []
    schema._normalized_sql.cache_clear()

    def strip(sql):
        calls.append(sql)
        return original(sql)

    monkeypatch.setattr(schema, "_strip_line_comments", strip)
    first = "CREATE TABLE sample (value TEXT DEFAULT '--keep') -- ignore\n;"
    changed = first.replace("'--keep'", "'--changed'")
    assert schema.canonical_sql(first) == schema.canonical_sql(first)
    assert schema.canonical_sql(changed) != schema.canonical_sql(first)
    assert calls == [first, changed]


def _normalize_sql(sql: Any) -> str:
    text = str(sql or "")
    text = _IF_NOT_EXISTS_RE.sub("", text)
    text = text.replace('"', "").replace("`", "").replace("[", "").replace("]", "")
    text = _WS_RE.sub(" ", text).strip().rstrip(";").strip()
    return text


def _normalize_default(value: Any) -> str:
    if value is None:
        return "<none>"
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = "'" + text[1:-1] + "'"
    return text.upper() if text.upper() in ("CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME", "NULL") else text


def _extract_checks(create_sql: str) -> List[str]:
    """从 CREATE TABLE 文本里抽出所有 CHECK(...) 子句（按括号配平），规范化后排序。"""
    text = _normalize_sql(create_sql)
    checks: List[str] = []
    for match in _CHECK_RE.finditer(text):
        start = match.end()
        depth = 1
        index = start
        while index < len(text) and depth > 0:
            if text[index] == "(":
                depth += 1
            elif text[index] == ")":
                depth -= 1
            index += 1
        checks.append(_WS_RE.sub(" ", text[start:index - 1]).strip().upper())
    return sorted(checks)


def _user_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _table_facets(conn: sqlite3.Connection, table: str) -> Dict[str, Any]:
    quoted = '"' + table.replace('"', '""') + '"'
    columns = [
        (str(row[1]), str(row[2] or "").upper(), int(row[3]), _normalize_default(row[4]), int(row[5]))
        for row in conn.execute(f"PRAGMA table_info({quoted})").fetchall()
    ]
    foreign_keys = sorted(
        (str(row[2]), str(row[3]), str(row[4] or ""), str(row[5] or "").upper(), str(row[6] or "").upper())
        for row in conn.execute(f"PRAGMA foreign_key_list({quoted})").fetchall()
    )
    indexes: Dict[str, Tuple[Any, ...]] = {}
    for row in conn.execute(f"PRAGMA index_list({quoted})").fetchall():
        index_name, unique, origin, partial = str(row[1]), int(row[2]), str(row[3]), int(row[4])
        if origin == "pk":
            continue
        index_columns = tuple(str(col[2]) for col in conn.execute(f'PRAGMA index_info("{index_name}")').fetchall())
        if origin == "c":
            sql_row = conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (index_name,)).fetchone()
            key = index_name
            definition = _normalize_sql(sql_row[0] if sql_row else "")
        else:
            key = f"<auto-{origin}>:" + ",".join(index_columns)
            definition = ""
        indexes[key] = (unique, index_columns, partial, definition)
    create_row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return {
        "columns": columns,
        "foreign_keys": foreign_keys,
        "indexes": indexes,
        "checks": _extract_checks(str(create_row[0]) if create_row else ""),
    }


def _objects(conn: sqlite3.Connection, kind: str) -> Dict[str, str]:
    rows = conn.execute("SELECT name, sql FROM sqlite_master WHERE type=? ORDER BY name", (kind,)).fetchall()
    return {str(row[0]): _normalize_sql(row[1]) for row in rows}


def snapshot_structure(conn: sqlite3.Connection) -> Dict[str, Any]:
    return {
        "tables": {name: _table_facets(conn, name) for name in _user_tables(conn)},
        "triggers": _objects(conn, "trigger"),
        "views": _objects(conn, "view"),
    }


def diff_structures(fresh: Dict[str, Any], baseline: Dict[str, Any]) -> List[str]:
    diffs: List[str] = []
    fresh_tables, baseline_tables = fresh["tables"], baseline["tables"]
    for name in sorted(set(fresh_tables) - set(baseline_tables)):
        diffs.append(f"表 {name}：新库有、基线库没有")
    for name in sorted(set(baseline_tables) - set(fresh_tables)):
        diffs.append(f"表 {name}：基线库有、新库没有（schema.sql 漏表）")
    for name in sorted(set(fresh_tables) & set(baseline_tables)):
        left, right = fresh_tables[name], baseline_tables[name]
        left_cols = {col[0]: col for col in left["columns"]}
        right_cols = {col[0]: col for col in right["columns"]}
        for col in sorted(set(left_cols) - set(right_cols)):
            diffs.append(f"表 {name} 列 {col}：新库有、基线库没有")
        for col in sorted(set(right_cols) - set(left_cols)):
            diffs.append(f"表 {name} 列 {col}：基线库有、新库没有")
        for col in sorted(set(left_cols) & set(right_cols)):
            if left_cols[col] != right_cols[col]:
                diffs.append(f"表 {name} 列 {col}：定义不同 新库={left_cols[col]} 基线库={right_cols[col]}")
        if left["foreign_keys"] != right["foreign_keys"]:
            diffs.append(f"表 {name}：外键不同 新库={left['foreign_keys']} 基线库={right['foreign_keys']}")
        for key in sorted(set(left["indexes"]) - set(right["indexes"])):
            diffs.append(f"表 {name} 索引 {key}：新库有、基线库没有")
        for key in sorted(set(right["indexes"]) - set(left["indexes"])):
            diffs.append(f"表 {name} 索引 {key}：基线库有、新库没有")
        for key in sorted(set(left["indexes"]) & set(right["indexes"])):
            if left["indexes"][key] != right["indexes"][key]:
                diffs.append(f"表 {name} 索引 {key}：定义不同 新库={left['indexes'][key]} 基线库={right['indexes'][key]}")
        if left["checks"] != right["checks"]:
            diffs.append(f"表 {name}：CHECK 约束不同 新库={left['checks']} 基线库={right['checks']}")
    for kind in ("triggers", "views"):
        left_objs, right_objs = fresh[kind], baseline[kind]
        for name in sorted(set(left_objs) - set(right_objs)):
            diffs.append(f"{kind[:-1]} {name}：新库有、基线库没有")
        for name in sorted(set(right_objs) - set(left_objs)):
            diffs.append(f"{kind[:-1]} {name}：基线库有、新库没有")
        for name in sorted(set(left_objs) & set(right_objs)):
            if left_objs[name] != right_objs[name]:
                diffs.append(f"{kind[:-1]} {name}：定义不同\n    新库={left_objs[name]}\n    基线库={right_objs[name]}")
    return diffs


def build_fresh_database(tmp_path: Path) -> Path:
    db_path = tmp_path / "fresh.db"
    ensure_schema(str(db_path), logging.getLogger(__name__), schema_path=str(SCHEMA_PATH))
    return db_path


def _version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()[0])


def test_fresh_schema_matches_ddl_baseline_and_generated_schema_text(tmp_path: Path) -> None:
    assert generate_schema_text() == SCHEMA_PATH.read_text(encoding="utf-8")
    fresh_path = build_fresh_database(tmp_path)
    baseline_path = build_baseline_database(tmp_path)
    fresh_conn = get_connection(str(fresh_path))
    baseline_conn = get_connection(str(baseline_path))
    try:
        assert _version(fresh_conn) == CURRENT_SCHEMA_VERSION
        assert _version(baseline_conn) == CURRENT_SCHEMA_VERSION
        diffs = diff_structures(snapshot_structure(fresh_conn), snapshot_structure(baseline_conn))
    finally:
        fresh_conn.close()
        baseline_conn.close()
    assert not diffs, (
        f"schema.sql 新库与 DDL 模块基线库结构不一致，共 {len(diffs)} 项：\n"
        + "\n".join(f"  - {item}" for item in diffs)
    )


@pytest.mark.parametrize("outdated_version", [4, 43, 45, 46, 47, 48, 49])
def test_outdated_schema_version_is_rejected_without_silent_migration(tmp_path: Path, outdated_version: int) -> None:
    db_path = build_fresh_database(tmp_path / f"v{outdated_version}")
    conn = get_connection(str(db_path))
    try:
        conn.execute("UPDATE SchemaVersion SET version = ? WHERE id = 1", (outdated_version,))
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(MigrationContractError, match=f"SchemaVersion={outdated_version}"):
        ensure_schema(str(db_path), logging.getLogger(__name__), schema_path=str(SCHEMA_PATH))


@pytest.mark.parametrize("full_data", [False, True], ids=["startup", "restore"])
def test_newer_schema_version_is_rejected_before_any_write(tmp_path: Path, full_data: bool) -> None:
    """新版本程序写过的库（或新版本的备份）：普通启动与恢复校验都拒绝，库内容一字不动。"""
    db_path = build_fresh_database(tmp_path)
    newer = CURRENT_SCHEMA_VERSION + 1
    conn = get_connection(str(db_path))
    try:
        conn.execute("UPDATE SchemaVersion SET version = ? WHERE id = 1", (newer,))
        conn.commit()
        before = list(conn.iterdump())
    finally:
        conn.close()

    with pytest.raises(MigrationContractError, match=f"SchemaVersion={newer} 高于当前程序支持版本"):
        ensure_schema(str(db_path), logging.getLogger(__name__), schema_path=str(SCHEMA_PATH), full_data=full_data)
    conn = get_connection(str(db_path))
    try:
        assert list(conn.iterdump()) == before
    finally:
        conn.close()


@pytest.mark.parametrize("stored_version", [CURRENT_SCHEMA_VERSION + 0.4, str(CURRENT_SCHEMA_VERSION).encode("ascii")])
def test_non_integer_schema_version_is_rejected_instead_of_truncated(tmp_path: Path, stored_version: Any) -> None:
    db_path = build_fresh_database(tmp_path)
    conn = get_connection(str(db_path))
    try:
        conn.execute("UPDATE SchemaVersion SET version = ? WHERE id = 1", (stored_version,))
        conn.commit()
        assert conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()[0] == stored_version
    finally:
        conn.close()

    with pytest.raises(MigrationContractError, match="数据库版本号不是整数"):
        ensure_schema(str(db_path), logging.getLogger(__name__), schema_path=str(SCHEMA_PATH))


@pytest.mark.parametrize("full_data", [False, True], ids=["startup", "restore"])
def test_current_version_db_missing_declared_core_check_is_rejected_at_boundary(tmp_path: Path, full_data: bool) -> None:
    db_path = build_fresh_database(tmp_path)
    ensure_schema(str(db_path), logging.getLogger(__name__), schema_path=str(SCHEMA_PATH), full_data=full_data)
    conn = get_connection(str(db_path))
    try:
        # 列一个不少，只是丢了声明里的 CHECK / NOT NULL / 主键；只比列集合时这种库能冒充当前版本。
        conn.executescript(
            """
            CREATE TABLE WorkCalendar_unchecked AS SELECT * FROM WorkCalendar;
            DROP TABLE WorkCalendar;
            ALTER TABLE WorkCalendar_unchecked RENAME TO WorkCalendar;
            """
        )
    finally:
        conn.close()

    with pytest.raises(MigrationContractError, match="bad_core_schema: WorkCalendar"):
        ensure_schema(str(db_path), logging.getLogger(__name__), schema_path=str(SCHEMA_PATH), full_data=full_data)


def test_sqlite_below_release_runtime_is_rejected_once_at_import() -> None:
    import os
    import subprocess
    import sys

    code = (
        "import sqlite3\n"
        "sqlite3.sqlite_version_info, sqlite3.sqlite_version = (3, 35, 4), '3.35.4'\n"
        "import core.infrastructure.database\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code], cwd=str(REPO_ROOT), capture_output=True, encoding="utf-8", timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert completed.returncode != 0
    assert "当前 SQLite 版本 3.35.4 低于本程序要求的 3.35.5" in completed.stderr


def test_unversioned_non_empty_legacy_db_is_rejected_with_zero_writes(tmp_path: Path) -> None:
    db_path = tmp_path / "unversioned_legacy.db"
    conn = get_connection(str(db_path))
    try:
        conn.execute("CREATE TABLE Operators (operator_id TEXT PRIMARY KEY, name TEXT NOT NULL)")
        conn.execute("INSERT INTO Operators (operator_id, name) VALUES ('OP1', '张三')")
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(MigrationContractError, match="SchemaVersion=0"):
        ensure_schema(str(db_path), logging.getLogger(__name__), schema_path=str(SCHEMA_PATH))

    conn = get_connection(str(db_path))
    try:
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert tables == ["Operators"]
        assert "SchemaVersion" not in tables
    finally:
        conn.close()


@pytest.mark.parametrize("action,source_kind", [
    ("scheduling.candidate.adopt", "candidate_adoption"),
    ("trial.scenario.adopt", "trial_adoption"),
])
def test_history_entry_bind_adoption_receipt_trigger_binds_committed_receipt(
    tmp_path: Path, action: str, source_kind: str
) -> None:
    import json

    db_path = build_fresh_database(tmp_path)
    conn = get_connection(str(db_path))
    request_key = "adopt-req-" + source_kind
    receipt_ref = "a" * 32
    committed_at = "2026-10-18T09:30:00Z"
    try:
        conn.execute("BEGIN")
        conn.execute(
            """
            INSERT INTO WorkbenchHistoryEntries(
                entry_ref, timeline, source_kind, state, occurred_at, occurred_day, occurred_us,
                request_key, selection_json, times_json, evidence_gaps_json, objective_json
            ) VALUES (?, 'official', ?, 'committed', NULL, NULL, 100, ?, '{}', '{"adopted_at":"2026-10-18T17:30:00"}', '[]', '{}')
            """,
            ("pending:" + request_key, source_kind, request_key),
        )
        conn.execute(
            """
            INSERT INTO WorkbenchCommandReceipts(
                request_key, receipt_ref, action, context_ref, outcome_json, input_json, committed_at_utc
            ) VALUES (?, ?, ?, 'ctx', '{"result":"committed"}', '{}', ?)
            """,
            (request_key, receipt_ref, action, committed_at),
        )
        conn.commit()
        row = dict(
            conn.execute(
                "SELECT entry_ref, receipt_ref, occurred_at, occurred_day, times_json "
                "FROM WorkbenchHistoryEntries WHERE request_key=?",
                (request_key,),
            ).fetchone()
        )
    finally:
        conn.close()

    assert row["entry_ref"] == "adoption:" + receipt_ref
    assert row["receipt_ref"] == receipt_ref
    assert row["occurred_at"] == committed_at
    assert row["occurred_day"] == "2026-10-18"
    assert json.loads(row["times_json"]) == {
        "adopted_at": "2026-10-18T17:30:00",
        "committed_at_utc": committed_at,
    }


def test_run_side_resources_enforces_view_check_and_immutability_triggers(tmp_path: Path) -> None:
    db_path = build_fresh_database(tmp_path)
    conn = get_connection(str(db_path))
    run_ref = "b" * 48
    request_key = "req-side-resources-0001"
    try:
        conn.execute(
            """INSERT INTO WorkbenchCommandReceipts(
                request_key, receipt_ref, action, context_ref, outcome_json, input_json, committed_at_utc
            ) VALUES (?, ?, 'scheduling.run', 'in-side-res', '{"result":"committed"}', '{}', '2026-10-18T08:00:00Z')""",
            (request_key, "c" * 32),
        )
        conn.execute(
            """INSERT INTO WorkbenchRunJobs(
                run_ref, request_key, input_ref, normalized_input_json,
                revisions_json, conditions_archive_json, execution_json, baseline_json,
                accepted_at, state, stage
            ) VALUES (?, ?, 'in-side-res', '{}', '{}', '{}', '[]', '{}', '2026-10-18T08:00:00', 'queued', 'queued')""",
            (run_ref, request_key),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO WorkbenchRunSideResources(run_ref, side_key, resource_view, payload_json) VALUES (?, 'official', 'invalid_view', '{}')",
                (run_ref,),
            )
        conn.execute(
            "INSERT INTO WorkbenchRunSideResources(run_ref, side_key, resource_view, payload_json) VALUES (?, 'official', 'selected_batches', '{}')",
            (run_ref,),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError, match="run read model is permanent"):
            conn.execute("UPDATE WorkbenchRunSideResources SET payload_json='{\"x\":1}' WHERE run_ref=?", (run_ref,))
        with pytest.raises(sqlite3.IntegrityError, match="run read model is permanent"):
            conn.execute("DELETE FROM WorkbenchRunSideResources WHERE run_ref=?", (run_ref,))
    finally:
        conn.close()


def test_v48_execution_report_identity_trigger_and_unified_dashboard_external_item(tmp_path: Path) -> None:
    from tests.workbench.plan_catalog_support import ensure_history_head

    db_path = build_fresh_database(tmp_path)
    conn = get_connection(str(db_path))
    report_ref = "2" * 48
    task_ref = "3" * 48
    outsourcing_ref = "4" * 48
    try:
        conn.executescript(
            """
            INSERT INTO Parts(part_no, part_name) VALUES ('P1', 'Part 1');
            INSERT INTO Batches(batch_id, part_no, quantity) VALUES ('B1', 'P1', 10);
            INSERT INTO BatchOperations(id, op_code, batch_id, seq, op_type_name, source)
                VALUES (1, 'B1-10', 'B1', 10, 'Turning', 'internal');
            INSERT INTO Suppliers(supplier_id, name) VALUES ('S1', 'Supplier 1');
            """
        )
        op_ref = conn.execute(
            "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key='1' AND active=1"
        ).fetchone()[0]
        batch_ref = conn.execute(
            "SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND entity_key='B1' AND active=1"
        ).fetchone()[0]
        supplier_ref = conn.execute(
            "SELECT ref FROM WorkbenchEntityRefs WHERE kind='supplier' AND entity_key='S1' AND active=1"
        ).fetchone()[0]
        ensure_history_head(conn, 1, strategy="EDD", schedule_time="2026-10-18T08:00:00")
        plan_ref = conn.execute("SELECT plan_ref FROM ScheduleHistory WHERE version=1").fetchone()[0]
        clock_before = conn.execute("SELECT revision FROM WorkbenchExecutionLedgerClock WHERE singleton=1").fetchone()[0]
        conn.execute(
            """INSERT INTO WorkbenchProductionReports(
                report_ref, report_no, operation_ref, recorded_against_task_ref,
                recorded_against_plan_ref, source, recorded_at,
                current_revision_ref, revision_count, voided, completed_quantity, remark,
                current_local_operator, current_declared_operator
            ) VALUES (?, 'RPT-0001', ?, ?, ?, 'manual', '2026-10-18T09:00:00', ?, 1, 0, 5, 'initial', 'op1', 'op1')""",
            (report_ref, op_ref, task_ref, plan_ref, "5" * 48),
        )
        clock_after_insert = conn.execute("SELECT revision FROM WorkbenchExecutionLedgerClock WHERE singleton=1").fetchone()[0]
        assert clock_after_insert == clock_before + 1

        # 允许更新当前有效修订镜像列，且自身 UPDATE 不额外推进时钟（由 Revisions/Voids 插入触发器推进）
        conn.execute(
            "UPDATE WorkbenchProductionReports SET revision_count=2, completed_quantity=8, remark='corrected' WHERE report_ref=?",
            (report_ref,),
        )
        assert conn.execute("SELECT revision FROM WorkbenchExecutionLedgerClock WHERE singleton=1").fetchone()[0] == clock_after_insert

        # 永久身份列不可变，且禁止删除
        with pytest.raises(sqlite3.IntegrityError, match="execution report identity is immutable"):
            conn.execute("UPDATE WorkbenchProductionReports SET report_no='RPT-0002' WHERE report_ref=?", (report_ref,))
        with pytest.raises(sqlite3.IntegrityError, match="execution ledger is append-only"):
            conn.execute("DELETE FROM WorkbenchProductionReports WHERE report_ref=?", (report_ref,))

        # 外协登记（17 列内联最新事实）自动在统一 WorkbenchDashboardItems 生成 category='external' 条目
        conn.execute(
            """INSERT INTO WorkbenchOutsourcingReceipts(
                outsourcing_ref, target_kind, batch_ref, supplier_ref, origin_json, identity_json, created_at,
                latest_fact_ref, history_count, sent, planned, returned, confirmed_state,
                declared_operator, local_operator, reason, recorded_at
            ) VALUES (
                ?, 'single', ?, ?, '{}', '{}', '2026-10-18T09:00:00',
                ?, 1, '2026-10-18T09:00:00', '2026-10-20T09:00:00', NULL, 'in_transit',
                'op1', 'op1', 'initial send', '2026-10-18T09:00:00'
            )""",
            (outsourcing_ref, batch_ref, supplier_ref, "6" * 48),
        )
        ext_item = conn.execute(
            "SELECT category, batch_ref, task_ref, outsourcing_ref FROM WorkbenchDashboardItems WHERE outsourcing_ref=?",
            (outsourcing_ref,),
        ).fetchone()
        assert tuple(ext_item) == ("external", None, None, outsourcing_ref)
        dashboard_history_cols = {row[1] for row in conn.execute("PRAGMA table_info(WorkbenchDashboardHistory)").fetchall()}
        assert "source_facts_json" not in dashboard_history_cols
        outsourcing_facts_cols = {row[1] for row in conn.execute("PRAGMA table_info(WorkbenchOutsourcingFacts)").fetchall()}
        assert "source_facts_json" not in outsourcing_facts_cols
        lineage_cols = [row[1] for row in conn.execute("PRAGMA table_info(WorkbenchTemplateLineageOrigins)").fetchall()]
        assert lineage_cols == [
            "lineage_ref", "operation_ref", "template_operation_ref",
            "template_revision", "source_eligible", "instance_modified",
        ]
        user_tables = set(_user_tables(conn))
        assert "OperationExecutionStates" in user_tables
        assert not (user_tables & {
            "WorkbenchDashboardExternalItems",
            "WorkbenchDashboardExternalStates",
            "WorkbenchDashboardExternalHistory",
            "WorkbenchProcessWorkflow",
            "WorkbenchProcessOperationConfirmations",
            "WorkbenchTemplateLineageEvents",
            "WorkbenchOutsourcingOperationOrigins",
            "WorkbenchOutsourcingSourceConfirmations",
        })
    finally:
        conn.close()


def test_v49_inline_confirmations_lineage_flip_and_outsourcing_receipt_guards(tmp_path: Path) -> None:
    db_path = build_fresh_database(tmp_path)
    conn = get_connection(str(db_path))
    try:
        conn.executescript(
            """
            INSERT INTO Parts(part_no, part_name) VALUES ('P1', 'Part 1');
            INSERT INTO PartOperations(id, part_no, seq, op_type_name, source) VALUES (10, 'P1', 10, 'Turning', 'internal');
            INSERT INTO Batches(batch_id, part_no, quantity) VALUES ('B1', 'P1', 5);
            INSERT INTO BatchOperations(id, op_code, batch_id, seq, op_type_name, source)
                VALUES (20, 'B1-10', 'B1', 10, 'Turning', 'internal');
            """
        )
        part_rev_before = conn.execute(
            "SELECT revision FROM WorkbenchEntityRefs WHERE kind='part' AND entity_key='P1' AND active=1"
        ).fetchone()[0]
        tmpl_ref, tmpl_rev_before = conn.execute(
            "SELECT ref, revision FROM WorkbenchEntityRefs WHERE kind='template_operation' AND entity_key='10' AND active=1"
        ).fetchone()
        op_ref = conn.execute(
            "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key='20' AND active=1"
        ).fetchone()[0]

        # 单调前置 CHECK 约束
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE Parts SET route_confirmed_at='2026-10-18T10:00:00Z' WHERE part_no='P1'")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE Parts SET workflow_origin='managed', source_confirmed_at='2026-10-18T10:00:00Z' WHERE part_no='P1'")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE PartOperations SET hours_confirmed_at='2026-10-18T10:00:00Z' WHERE id=10")

        # 纯确认列更新不升 WorkbenchEntityRefs.revision，但推进 WorkbenchSourceRevisions
        src_rev_before = conn.execute("SELECT revision FROM WorkbenchSourceRevisions WHERE source_key='parts'").fetchone()[0]
        conn.execute(
            "UPDATE Parts SET workflow_origin='managed', route_confirmed_at='2026-10-18T10:00:00Z' WHERE part_no='P1'"
        )
        conn.execute(
            "UPDATE PartOperations SET source_confirmed_at='2026-10-18T10:01:00Z', hours_confirmed_at='2026-10-18T10:02:00Z' WHERE id=10"
        )
        assert conn.execute(
            "SELECT revision FROM WorkbenchEntityRefs WHERE kind='part' AND entity_key='P1' AND active=1"
        ).fetchone()[0] == part_rev_before
        assert conn.execute(
            "SELECT revision FROM WorkbenchEntityRefs WHERE ref=?", (tmpl_ref,)
        ).fetchone()[0] == tmpl_rev_before
        assert conn.execute("SELECT revision FROM WorkbenchSourceRevisions WHERE source_key='parts'").fetchone()[0] > src_rev_before

        # 6 列 Origins 与 0->1 单向翻转触发器
        lineage_ref = "7" * 48
        conn.execute(
            "INSERT INTO WorkbenchTemplateLineageOrigins(lineage_ref, operation_ref, template_operation_ref, template_revision, source_eligible) "
            "VALUES (?, ?, ?, 1, 1)",
            (lineage_ref, op_ref, tmpl_ref),
        )
        assert conn.execute("SELECT instance_modified FROM WorkbenchTemplateLineageOrigins WHERE lineage_ref=?", (lineage_ref,)).fetchone()[0] == 0
        conn.execute("UPDATE BatchOperations SET unit_hours=2.5 WHERE id=20")
        assert conn.execute("SELECT instance_modified FROM WorkbenchTemplateLineageOrigins WHERE lineage_ref=?", (lineage_ref,)).fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError, match="template lineage is append-only"):
            conn.execute("UPDATE WorkbenchTemplateLineageOrigins SET instance_modified=0 WHERE lineage_ref=?", (lineage_ref,))
    finally:
        conn.close()
