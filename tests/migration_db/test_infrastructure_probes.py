"""合同测试：SQL 排水第二批新增的基础设施探针——连接守卫（query_only / foreign_keys / data_version / database_list /
快照元数据）、sqlite_master 自省（对象名、表名、DDL、有序清单、列名）、只读快照连接与隔离内存库 DDL 解析。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.connection_guards import (
    connection_snapshot_metadata,
    data_version,
    database_list,
    foreign_keys_enabled,
    is_query_only,
    main_database_path,
    query_only,
)
from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.schema_probe import (
    object_names,
    object_sql,
    object_sql_map,
    schema_objects,
    table_columns,
    table_exists,
    table_names,
    user_table_count,
)
from core.infrastructure.snapshot_connection import ddl_columns, open_readonly_immutable
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def test_query_only_guard_restores_previous_state(mem_conn) -> None:
    assert not is_query_only(mem_conn)
    with query_only(mem_conn):
        assert is_query_only(mem_conn)
        with pytest.raises(sqlite3.OperationalError):
            mem_conn.execute("CREATE TABLE t(x)")
    assert not is_query_only(mem_conn)
    mem_conn.execute("PRAGMA query_only=ON")
    with query_only(mem_conn):
        assert is_query_only(mem_conn)
    assert is_query_only(mem_conn), "进入前已是 ON 的连接退出后保持 ON"


def test_foreign_keys_and_data_version_and_database_list(mem_conn) -> None:
    assert foreign_keys_enabled(mem_conn)
    mem_conn.execute("PRAGMA foreign_keys = OFF")
    assert not foreign_keys_enabled(mem_conn)
    assert isinstance(data_version(mem_conn), int)
    rows = database_list(mem_conn)
    assert rows and rows[0][1] == "main"
    assert main_database_path(mem_conn) == ""
    main_dv, main_sv, temp_sv, qo = connection_snapshot_metadata(mem_conn)
    assert all(isinstance(value, int) for value in (main_dv, main_sv, temp_sv, qo))
    assert qo == 0


def test_main_database_path_for_file_database(tmp_path: Path) -> None:
    db_path = tmp_path / "probe.db"
    conn = get_connection(str(db_path))
    try:
        assert Path(main_database_path(conn)).resolve() == db_path.resolve()
    finally:
        conn.close()


def test_schema_probes_on_full_schema(schema_conn) -> None:
    names = object_names(schema_conn)
    tables = table_names(schema_conn)
    assert "Parts" in tables and "Parts" in names
    assert any(name.startswith("idx_") for name in names), "索引名也在对象名集合里"
    assert "idx_wb_process_confirmation_operation" not in tables
    assert user_table_count(schema_conn) == len({name for name in tables if not name.startswith("sqlite_")})
    assert table_exists(schema_conn, "WorkbenchCalibrationAdoptions")
    assert not table_exists(schema_conn, "NoSuchTable")
    assert "AUTOINCREMENT" in (object_sql(schema_conn, "ScheduleVersionSeq") or "").upper()
    assert object_sql(schema_conn, "NoSuchTable") is None
    subset = object_sql_map(schema_conn, ["Parts", "NoSuchTable"])
    assert set(subset) == {"Parts"} and "CREATE TABLE" in subset["Parts"]
    objects = schema_objects(schema_conn)
    assert objects == sorted(objects, key=lambda item: (item[0], item[1]))
    assert all(len(item) == 4 for item in objects)
    excluded = schema_objects(schema_conn, exclude_tbl_names=["Parts"])
    assert all(item[2] != "Parts" for item in excluded)
    assert "part_no" in table_columns(schema_conn, "Parts")


def test_ddl_columns_restricted_and_unrestricted() -> None:
    ddl = "CREATE TABLE Widgets (id INTEGER PRIMARY KEY, name TEXT NOT NULL, note TEXT)"
    assert ddl_columns(ddl, "Widgets") == ["id", "name", "note"]
    assert ddl_columns(ddl, "Widgets", restricted=True) == ["id", "name", "note"]
    with pytest.raises(ValueError):
        ddl_columns("CREATE TABLE Other (id INTEGER)", "Widgets", restricted=True)
    with pytest.raises(ValueError):
        ddl_columns("INSERT INTO Widgets VALUES (1)", "Widgets", restricted=True)
    with pytest.raises(ValueError):
        ddl_columns("not sql at all", "Widgets")
    with pytest.raises(ValueError):
        ddl_columns(None, "Widgets")  # type: ignore[arg-type]


def test_readonly_immutable_snapshot_and_scheduling_run_admitted(tmp_path: Path) -> None:
    db_path = tmp_path / "snapshot.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    conn = get_connection(str(db_path))
    try:
        conn.execute(
            "INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_hash,outcome_json)"
            " VALUES ('r'||substr('0000000000000000',1,15),'a'||substr('00000000000000000000000000000000',1,31),"
            "'scheduling.run','ctx','" + "a" * 64 + "','{}')"
        )
        request_key = conn.execute("SELECT request_key FROM WorkbenchCommandReceipts").fetchone()[0]
        conn.execute(
            "INSERT INTO WorkbenchRunJobs(run_ref,request_key,input_ref,normalized_input_json,facts_hash,facts_json,"
            "execution_json,baseline_json,accepted_at,state,stage) VALUES (?,?,'in','{}','h','{}','{}','{}','t0','queued','queued')",
            ("b" * 48, request_key),
        )
        conn.commit()
    finally:
        conn.close()
    with open_readonly_immutable(str(db_path)) as snapshot:
        assert WorkbenchRunRepository(snapshot).scheduling_run_admitted(request_key)
        assert not WorkbenchRunRepository(snapshot).scheduling_run_admitted("missing")
        with pytest.raises(sqlite3.OperationalError):
            snapshot.execute("DELETE FROM WorkbenchRunJobs")
