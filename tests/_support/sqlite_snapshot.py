"""Read-only SQLite snapshots shared by independent regression domains."""

from core.infrastructure.workbench_metadata_schema import _canonical_sql


def schema_snapshot(conn):
    """{对象名: (type, tbl_name, 规范化 DDL)}；DDL 走生产的 _canonical_sql（去注释、压空白、CREATE TABLE 列/约束排序），
    这样由 schema.sql 新建的库与从冻结历史 fixture 升级上来的库可以按结构而非文本排版比较。"""
    return {
        row[0]: (row[1], row[2], _canonical_sql(row[3] or ""))
        for row in conn.execute("SELECT name, type, tbl_name, sql FROM sqlite_master")
    }


def table_rows(conn, table):
    return [tuple(row) for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid')]


def stored_state(conn):
    names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    return schema_snapshot(conn), {name: table_rows(conn, name) for name in names}
